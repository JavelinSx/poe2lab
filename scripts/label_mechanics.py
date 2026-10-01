"""Label the game's mechanics in its texts with Jev (TypeSafe's "System One" model, typed yes/no answers with
probabilities) - run by the developer after a game patch; players never need a key.

The regex in poe2lab/analysis/skills.py (MECHANICS) and poe2lab/analysis/tree.py (PACKAGE_MECHANICS) read the same
texts and misfire ("shockwave" as Shock, your own Stun Threshold as stunning enemies). Jev answers each question
about a text on its own:
- every gem and unique: whether it creates / uses each of the links' mechanics (the Skills tab, unique suggestions);
- every notable and keystone of the passive tree (--tree): whether it is about each mechanic of the tree's
  "mechanics together" packages;
- every gem stat PoB has no calculation for and every unique line it cannot read (--gaps): what it changes -
  damage, defence, resources and speed, or nothing measurable (the Profile's "what PoB does not count").
The result is data/mechanics_labels.json. Each label keeps a fingerprint of the text and the questions it answered,
so a run after a patch asks again only about what changed (and drops what the game no longer has).

The key comes from the POLZA_AI_API_KEY environment variable (polza.ai/jev) and is never printed.

  python scripts/label_mechanics.py --dry-run [--tree]        # what would be sent, no request
  python scripts/label_mechanics.py --sample [names...]       # a few gems, compared with the regex
  python scripts/label_mechanics.py --all [--tree] [--budget 40]   # what is new or changed, into the data file
  python scripts/label_mechanics.py --stamp                   # fingerprint labels made before fingerprints existed
"""
import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from poe2lab.analysis import skills  # noqa: E402
from poe2lab.analysis.skills import MECHANICS, mechanics_of  # noqa: E402
from poe2lab.analysis.tree import PACKAGE_MECHANICS  # noqa: E402
from poe2lab.engine import PobEngine  # noqa: E402
from poe2lab.engine.luahost import POB_COMMIT  # noqa: E402

URL = "https://polza.ai/api/v1/systemone"
MODEL = "jev-latest"
OUT = ROOT / "data" / "mechanics_labels.json"
SAMPLE_OUT = ROOT / "data" / "cache" / "mechanics_sample.json"
THRESHOLD = 0.5
KEEP = 0.1  # below this a probability is a plain no: not kept, so the data file stays small
WORKERS = 3
PER_MINUTE = 90
SAVE_EVERY = 50

# each links' mechanic as the game means it (English: the texts are English)
TERMS = {
    "impale": "Impale (a debuff that stores part of a hit's damage; a later attack hit consumes it and deals that "
              "damage again)",
    "ice_crystal": "Ice Crystals (objects on the ground that explode in cold damage when destroyed)",
    "freeze": "Freeze (the cold ailment that stops an enemy once its freeze buildup is full; Primed for Freeze is "
              "its first stage)",
    "shock": "Shock (the lightning ailment that makes the enemy take increased damage)",
    "ignite": "Ignite (the fire ailment that deals fire damage over time)",
    "bleed": "Bleeding (the physical damage over time ailment)",
    "poison": "Poison (the chaos damage over time ailment that stacks)",
    "frenzy": "Frenzy Charges",
    "power": "Power Charges",
    "endurance": "Endurance Charges",
    "rage": "Rage (the resource gained from hits and spent by some skills)",
    "infusion": "Elemental Infusions or Remnants (picked up to empower later skills)",
    "armour_break": "Armour Break (breaking down an enemy's armour; Fully Broken Armour)",
    "glory": "Glory (a resource some skills build up and spend)",
    "combo": "Combo (a counter built by successful strikes and spent by some skills)",
    "heavy_stun": "Heavy Stun or Stun buildup (an enemy is Heavy Stunned when its stun buildup is full)",
    "shapeshift": "Shapeshifting (turning into an animal form: bear, wolf, wyvern)",
}
assert set(TERMS) == {m.key for m in MECHANICS}, "a mechanic without its question"

# the tree packages' mechanics, short: a node's text is short, and so is what it can be about
TREE_TERMS = {
    "rage": "Rage", "frenzy": "Frenzy Charges", "power": "Power Charges", "endurance": "Endurance Charges",
    "crit": "Critical Hits", "ignite": "Ignite", "shock": "Shock on enemies", "freeze": "Freeze or Chill on enemies",
    "bleed": "Bleeding", "poison": "Poison",
    "stun": "stunning enemies (Stun buildup, Heavy Stun, Daze; not your own Stun Threshold)",
    "armour_break": "breaking enemies' Armour", "impale": "Impale", "combo": "Combo", "glory": "Glory",
    "exposure": "Exposure on enemies", "infusion": "Infusions or Remnants", "minion": "Minions", "totem": "Totems",
    "warcry": "Warcries", "shapeshift": "Shapeshifting (bear, wolf, wyvern)", "curse": "Curses", "herald": "Heralds",
    "block": "Block",
}
assert set(TREE_TERMS) == {k for k, _ in PACKAGE_MECHANICS}, "a tree mechanic without its question"

# where the regex is known to go wrong, and the build skills the links are about
SAMPLE = ["Glacial Cascade", "Tempest Bell", "Frozen Locus", "Ice Strike", "Freezing Mark", "Frost Bomb",
          "Herald of Ice", "Shockwave Totem", "Tempest Flurry", "Falling Thunder", "Killing Palm", "Whirling Assault",
          "Furious Slam", "Boneshatter", "Armour Breaker", "Fangs of Frost", "Lunar Assault", "Earthquake",
          "Infernal Cry", "Close Combat II", "Fist of War II", "Crystalline Shards", "Cold Attunement", "Embitter",
          "Impale", "Amor Mandragora", "Constricting Command", "Polcirkeln"]


def items(engine) -> list[dict]:
    """Every gem and unique with the text Jev reads and the fields the regex reads."""
    out = []
    for g in engine.gem_texts():
        kind = "support gem (its effects apply to the skills it supports)" if g["support"] else "active skill gem"
        out.append(g | {"kind": "gem", "label": kind})
    for u in engine.unique_catalog():
        out.append({"kind": "unique", "label": "unique item", "name": u["name"], "support": True,
                    "description": "", "lines": u["lines"], "stats": [], "types": [], "tags": []})
    seen = set()  # a name the game gives twice is labelled once (the analysis looks labels up by name)
    return [x for x in out if key_of(x) not in seen and not seen.add(key_of(x))]


def tree_items(engine) -> list[dict]:
    """Every notable and keystone of the main tree (ascendancies are not in the packages)."""
    seen, out = set(), []
    for n in engine.tree_graph()["nodes"]:
        if n["type"] in ("Notable", "Keystone") and not n["asc"] and n["name"] not in seen:
            seen.add(n["name"])
            out.append({"kind": "node", "label": f"passive skill ({n['type'].lower()})", "name": n["name"],
                        "lines": n["stats"]})
    return out


def gap_items(engine) -> list[dict]:
    """What "PoB does not count" can list: gem stats without a calculation (by stat id) and unique lines PoB cannot
    read (numbers as #, so a rolled item finds its line)."""
    from poe2lab.knowledge import gap_key
    out, seen = [], set()
    for s in engine.unmapped_stats():
        out.append({"kind": "stat", "name": s["stat"], "label": f"a stat of the skill gem {s['gem']}",
                    "lines": [x for x in (s["text"], f"{s['stat']} = {s['value']:g}") if x]})
    for u in sorted(engine.unique_catalog(), key=lambda u: u["name"]):  # the same unique names a line every time
        for line in u.get("unread", []):
            name = gap_key(line)
            if name not in seen:
                seen.add(name)
                out.append({"kind": "line", "name": name, "label": f"a line of the unique item {u['name']}",
                            "lines": [line]})
    return out


IMPACT = {"damage": "changes the damage the character deals",
          "defence": "changes the damage the character takes, avoids or recovers from",
          "resource": "changes mana, charges, Rage, cooldowns, durations, speed or area",
          "none": "changes nothing measurable (visuals, targeting, limits, how a skill is shown)"}


def key_of(item: dict) -> str:
    return f"{item['kind']}:{item['name']}"


def state(item: dict) -> str:
    parts = [f"{item['label']}: {item['name']}"]
    if item.get("description"):
        parts.append(item["description"])
    if item.get("types"):
        parts.append("Skill types: " + ", ".join(item["types"]))
    parts += [f"- {' '.join(l.split())}" for l in item["lines"]]
    if item.get("stats"):
        parts.append("Stat ids: " + ", ".join(item["stats"]))
    return "\n".join(parts)


def questions(item: dict) -> dict:
    """Gems and uniques: two questions per mechanic about what the text says; a mechanic the text does not name is
    a no (without that Jev lent resources like Combo or Glory to skills that never mention them). Tree nodes: one
    short question per mechanic."""
    if item["kind"] in ("stat", "line"):
        return {"impact": {"type": "choice", "instructions": "What does this line change for the character?",
                           "criteria": IMPACT}}
    if item["kind"] == "node":
        return {f"has_{key}": {"type": "noul", "instructions":
                               f"Does this passive make the character better with {term} (more of it, a stronger "
                               f"effect, or a bonus while using it)? No if it does not mention it."}
                for key, term in TREE_TERMS.items()}
    what = "this unique item" if item["kind"] == "unique" else "this gem"
    q = {}
    for key, term in TERMS.items():
        name = term.split(" (")[0]
        q[f"creates_{key}"] = {"type": "noul", "instructions":
                               f"Does the text say that {what} creates, inflicts, applies, grants or builds up "
                               f"{term}? Answer no if the text does not mention {name}; a damage type alone does "
                               f"not count."}
        q[f"uses_{key}"] = {"type": "noul", "instructions":
                            f"Does the text say that {what} consumes, spends or requires {term}, or has an effect "
                            f"that depends on it (such as more damage against enemies affected by it)? Answer no if "
                            f"the text does not mention {name}."}
    return q


def fingerprint(item: dict) -> str:
    """What a label answered: the text and the questions (a new wording asks again)."""
    raw = state(item) + json.dumps(questions(item), sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


_pace = threading.Lock()
_next = [0.0]


def _wait_turn():
    """At most PER_MINUTE requests a minute (polza.ai limits requests per minute)."""
    with _pace:
        now = time.monotonic()
        start = max(now, _next[0])
        _next[0] = start + 60 / PER_MINUTE
    time.sleep(max(0.0, start - now))


class Stop(Exception):
    """The service refused (no money left, a bad key): what is done is kept, the run can go on later."""


def ask(item: dict, key: str) -> dict:
    body = json.dumps({"model": MODEL, "state": state(item), "questions": questions(item)}).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "User-Agent": "poe2lab (https://github.com/JavelinSx/poe2lab)"})
    for attempt in range(6):
        _wait_turn()
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return json.load(res)
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt < 5:  # the minute's limit: wait it out
                time.sleep(20 * (attempt + 1))
                continue
            if err.code in (500, 502, 503) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise Stop(f"{item['name']}: HTTP {err.code} {err.read().decode('utf-8', 'replace')[:300]}") from None
        except urllib.error.URLError as err:
            if attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise Stop(f"{item['name']}: {err.reason}") from None


def labels(answer: dict) -> dict:
    """{"creates": {key: p}, "uses": {key: p}} for gems and uniques, {"has": {key: p}} for tree nodes."""
    out: dict = {}
    for q, a in answer["answers"].items():
        if a.get("type") == "choice" or "probabilities" in a and "noul" not in a:
            out[q] = {k: float(p) for k, p in a["probabilities"].items()}  # {"impact": {option: p}}
            continue
        side, key = q.split("_", 1)
        out.setdefault(side, {})[key] = float(a["noul"])
    return compact(out)


def compact(lab: dict) -> dict:
    return {side: ({k: round(p, 2) for k, p in probs.items() if p >= KEEP} if isinstance(probs, dict) else probs)
            for side, probs in lab.items()}


def regex(item: dict) -> dict:
    """What the regex reads in the text alone: no tags, so its generic rules (every attack builds Combo, every cold
    hit Freeze) stay out - they are rules of the game kept either way, not something to read in a text. The labels
    already made are left out too: the comparison is with the regex."""
    skills._labels = {}
    fields = {"description": " ".join([item.get("description", ""), *item["lines"]]) if item["kind"] == "unique"
              else item.get("description", ""), "stats": item["stats"], "types": item["types"], "tags": [],
              "support": item["support"]}
    return mechanics_of(fields)


def compare(item: dict, lab: dict) -> list[str]:
    """Where Jev and the regex differ (the regex's generic rules by damage type left out: Jev reads text only)."""
    rx = regex(item)
    out = []
    for side in ("creates", "uses"):
        jev = {k for k, p in lab[side].items() if p >= THRESHOLD}
        rxs = set(rx[side])
        for k in sorted(jev - rxs):
            out.append(f"+ {side} {k} (Jev {lab[side][k]:.2f}, regex no)")
        for k in sorted(rxs - jev):
            out.append(f"- {side} {k} (regex yes, Jev {lab[side].get(k, 0):.2f})")
    return out


def load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"meta": {}, "items": {}}


def save(done: dict, model: str | None):
    done["items"] = {k: compact(v) for k, v in sorted(done["items"].items())}
    done["meta"] = done.get("meta", {}) | {"model": model or done.get("meta", {}).get("model"),
                                           "date": date.today().isoformat(), "pob": POB_COMMIT,
                                           "threshold": THRESHOLD, "kept": KEEP}
    OUT.write_text(json.dumps({"meta": done["meta"], "items": done["items"]}, ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--sample", nargs="*")
    mode.add_argument("--all", action="store_true")
    mode.add_argument("--stamp", action="store_true")
    target = ap.add_mutually_exclusive_group()
    target.add_argument("--tree", action="store_true", help="the passive tree's notables instead of gems and uniques")
    target.add_argument("--gaps", action="store_true", help="what PoB does not count: its importance")
    ap.add_argument("--budget", type=float, help="stop once this many rubles are spent")
    args = ap.parse_args()

    engine = PobEngine()
    everything = tree_items(engine) if args.tree else gap_items(engine) if args.gaps else items(engine)
    kinds = {it["kind"] for it in everything}
    by_name = {}
    for it in everything:
        by_name.setdefault(it["name"], it)
    done = load()
    if args.dry_run:
        it = everything[0] if args.tree or args.gaps else by_name["Glacial Cascade"]
        todo = [x for x in everything if done["items"].get(key_of(x), {}).get("text") != fingerprint(x)]
        total = sum(len(state(x)) + sum(len(q["instructions"]) for q in questions(x).values()) for x in todo)
        print(state(it), "\n", json.dumps(next(iter(questions(it).values())), ensure_ascii=False), sep="")
        print(f"\n{len(todo)} of {len(everything)} to ask, ~{total // 4:,} input tokens, ~{total / 4 / 1e6 * 25:.0f} ₽ "
              f"(at ~25 ₽ a million tokens)")
        return
    if args.stamp:  # labels made before fingerprints: made on today's texts and questions
        n = 0
        for it in everything:
            lab = done["items"].get(key_of(it))
            if lab is not None and "text" not in lab:
                lab["text"] = fingerprint(it)
                n += 1
        save(done, None)
        print(f"{n} labels fingerprinted")
        return

    key = os.environ.get("POLZA_AI_API_KEY")
    if not key:
        sys.exit("POLZA_AI_API_KEY is not set")
    if args.all:
        current = {key_of(x) for x in everything}
        gone = [k for k in done["items"] if k.split(":", 1)[0] in kinds and k not in current]
        for k in gone:  # no longer in the game
            del done["items"][k]
        todo = [x for x in everything if done["items"].get(key_of(x), {}).get("text") != fingerprint(x)]
        print(f"{len(todo)} of {len(everything)} to ask" + (f", {len(gone)} gone" if gone else ""))
    else:
        if args.tree and not args.sample:  # nodes the regex is likely to misread
            words = ["stun threshold", "chill", "block", "critical", "rage", "charge", "minion", "totem", "curse",
                     "herald", "exposure", "daze", "infusion", "heavy stun", "wolf", "armour"]
            names = [n for n in (next((x["name"] for x in everything if w in " ".join(x["lines"]).lower()), None)
                                 for w in words) if n]
        else:
            names = args.sample or SAMPLE
        print("not in the game data:", ", ".join(n for n in names if n not in by_name) or "-")
        todo = [by_name[n] for n in dict.fromkeys(names) if n in by_name]
        done = {"items": {}}
    cost, model, n = 0.0, None, 0
    started = time.time()
    stop = None
    pool = ThreadPoolExecutor(WORKERS)
    try:
        for it, answer in pool.map(lambda x: (x, ask(x, key)), todo):
            n += 1
            model = answer.get("model", model)
            cost += float((answer.get("usage") or {}).get("cost_rub") or 0)
            lab = labels(answer) | {"text": fingerprint(it)}
            done["items"][key_of(it)] = lab
            if not args.all and it["kind"] in ("stat", "line"):
                top = max(lab["impact"].items(), key=lambda x: x[1])
                print(f"{it['name'][:70]}: {top[0]} {top[1]:.2f}  |  {' / '.join(it['lines'])[:90]}")
            elif not args.all and it["kind"] == "node":
                text = " ".join(it["lines"]).lower()
                rx = {k for k, pat in PACKAGE_MECHANICS if re.search(pat, text)}
                jev = {k for k, p in lab["has"].items() if p >= THRESHOLD}
                print(f"{it['name']}: {' / '.join(it['lines'])[:110]}")
                print(f"    Jev {sorted(jev)}  regex {sorted(rx)}" + ("" if jev == rx else "   <-- differ"))
            elif not args.all:
                diff = compare(it, lab)
                seen = "; ".join(f"{side[0]}:{k} {p:.2f}" for side in ("creates", "uses")
                                 for k, p in sorted(lab[side].items(), key=lambda x: -x[1]) if p >= 0.3)
                print(f"{it['name']}: Jev {seen or '-'}" + ("" if diff else "  = regex"))
                for d in diff:
                    print("   ", d)
            elif n % SAVE_EVERY == 0:
                print(f"{n}/{len(todo)}, {cost:.2f} ₽, {time.time() - started:.0f} s", flush=True)
                save(done, model)
            if args.budget is not None and cost >= args.budget:
                stop = f"the budget of {args.budget} ₽ is spent"
                break
    except Stop as err:
        stop = str(err)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        if args.all:
            save(done, model)
        elif done["items"]:
            SAMPLE_OUT.parent.mkdir(parents=True, exist_ok=True)
            SAMPLE_OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{n} requests, {cost:.2f} ₽, model {model}, {time.time() - started:.0f} s")
    if stop:
        print(f"stopped: {stop}; what is done is saved - run again to go on")


if __name__ == "__main__":
    main()
