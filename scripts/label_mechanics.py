"""Label which game mechanics each gem and unique creates or uses, with Jev (TypeSafe's "System One" model, typed
yes/no answers with probabilities) - run by the developer after a game patch; players never need a key.

The regex dictionary in poe2lab/analysis/skills.py (MECHANICS) reads the same texts and misfires ("shockwave" as
Shock, "culling a Shocked enemy" as creating Shock). Jev answers each question about a text on its own: for every
gem and unique, whether it creates / uses each mechanic. The result is data/mechanics_labels.json.

The key comes from the POLZA_AI_API_KEY environment variable (polza.ai/jev) and is never printed.

  python scripts/label_mechanics.py --dry-run                 # what would be sent, no request
  python scripts/label_mechanics.py --sample                  # ~30 tricky items, compared with the regex
  python scripts/label_mechanics.py --sample "Glacial Cascade" "Tempest Bell"
  python scripts/label_mechanics.py --all                     # everything, into data/mechanics_labels.json
"""
import argparse
import json
import os
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
from poe2lab.engine import PobEngine  # noqa: E402
from poe2lab.engine.luahost import POB_COMMIT  # noqa: E402

URL = "https://polza.ai/api/v1/systemone"
MODEL = "jev-latest"
OUT = ROOT / "data" / "mechanics_labels.json"
SAMPLE_OUT = ROOT / "data" / "cache" / "mechanics_sample.json"
THRESHOLD = 0.5
WORKERS = 3
PER_MINUTE = 90

# each mechanic as the game means it, for the questions (English: the texts are English)
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

# where the regex is known to go wrong, and the build skills the links are about
SAMPLE = ["Glacial Cascade", "Tempest Bell", "Frozen Locus", "Ice Strike", "Freezing Mark", "Frost Bomb",
          "Herald of Ice", "Shockwave Totem", "Tempest Flurry", "Falling Thunder", "Killing Palm", "Whirling Assault",
          "Furious Slam", "Boneshatter", "Armour Breaker", "Fangs of Frost", "Lunar Assault", "Earthquake",
          "Infernal Cry", "Elemental Expression", "Close Combat II", "Fist of War II", "Crystalline Shards",
          "Cold Attunement", "Embitter", "Impale", "Culling Strike", "Amor Mandragora", "Constricting Command",
          "Polcirkeln"]


def items(engine) -> list[dict]:
    """Every gem and unique with the text Jev reads and the fields the regex reads."""
    out = []
    for g in engine.gem_texts():
        kind = "support gem (its effects apply to the skills it supports)" if g["support"] else "active skill gem"
        out.append(g | {"kind": "gem", "label": kind})
    for u in engine.unique_catalog():
        out.append({"kind": "unique", "label": "unique item", "name": u["name"], "support": True,
                    "description": "", "lines": u["lines"], "stats": [], "types": [], "tags": []})
    return out


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
    """Two questions per mechanic about what the text says; a mechanic the text does not name is a no (without
    that Jev lent resources like Combo or Glory to skills that never mention them)."""
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


_pace = threading.Lock()
_next = [0.0]


def _wait_turn():
    """At most PER_MINUTE requests a minute (polza.ai limits requests per minute)."""
    with _pace:
        now = time.monotonic()
        start = max(now, _next[0])
        _next[0] = start + 60 / PER_MINUTE
    time.sleep(max(0.0, start - now))


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
            detail = err.read().decode("utf-8", "replace")[:300]
            raise SystemExit(f"{item['name']}: HTTP {err.code} {detail}") from None
        except urllib.error.URLError as err:
            if attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise SystemExit(f"{item['name']}: {err.reason}") from None


KEEP = 0.1  # below this a probability is a plain no: not kept, so the data file stays small


def labels(answer: dict) -> dict:
    """{"creates": {key: p}, "uses": {key: p}} from Jev's answers."""
    out = {"creates": {}, "uses": {}}
    for q, a in answer["answers"].items():
        side, key = q.split("_", 1)
        out[side][key] = float(a["noul"])
    return compact(out)


def compact(lab: dict) -> dict:
    return {side: {k: round(p, 2) for k, p in probs.items() if p >= KEEP} for side, probs in lab.items()}


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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--sample", nargs="*")
    mode.add_argument("--all", action="store_true")
    args = ap.parse_args()

    engine = PobEngine()
    everything = items(engine)
    by_name = {}
    for it in everything:
        by_name.setdefault(it["name"], it)
    if args.dry_run:
        it = by_name["Glacial Cascade"]
        total = sum(len(state(x)) + sum(len(q["instructions"]) for q in questions(x).values()) for x in everything)
        print(state(it), "\n", json.dumps(questions(it)["uses_freeze"], ensure_ascii=False), sep="")
        print(f"\n{len(everything)} items, ~{total // 4:,} input tokens in all (4 chars a token), "
              f"{len(questions(it))} questions each")
        return

    key = os.environ.get("POLZA_AI_API_KEY")
    if not key:
        sys.exit("POLZA_AI_API_KEY is not set")
    chosen = everything if args.all else [by_name[n] for n in (args.sample or SAMPLE) if n in by_name]
    missing = [n for n in (args.sample or SAMPLE) if n not in by_name] if not args.all else []
    if missing:
        print("not in the game data:", ", ".join(missing))
    done = json.loads(OUT.read_text(encoding="utf-8")) if args.all and OUT.exists() else {"items": {}}
    todo = [it for it in chosen if f"{it['kind']}:{it['name']}" not in done["items"]]
    cost, model = 0.0, None
    started = time.time()

    def run(it):
        return it, ask(it, key)

    with ThreadPoolExecutor(WORKERS) as pool:
        for n, (it, answer) in enumerate(pool.map(run, todo), 1):
            model = answer.get("model", model)
            cost += float((answer.get("usage") or {}).get("cost_rub") or 0)
            lab = labels(answer)
            done["items"][f"{it['kind']}:{it['name']}"] = lab
            if not args.all:
                diff = compare(it, lab)
                seen = "; ".join(f"{side[0]}:{k} {p:.2f}" for side in ("creates", "uses")
                                 for k, p in sorted(lab[side].items(), key=lambda x: -x[1]) if p >= 0.3)
                print(f"{it['name']}: Jev {seen or '-'}" + ("" if diff else "  = regex"))
                for d in diff:
                    print("   ", d)
            elif n % 50 == 0:
                print(f"{n}/{len(todo)}, {cost:.2f} ₽, {time.time() - started:.0f} s")
                OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(todo)} requests, {cost:.2f} ₽, model {model}, {time.time() - started:.0f} s")
    if not args.all:  # kept for a look without asking again
        SAMPLE_OUT.parent.mkdir(parents=True, exist_ok=True)
        SAMPLE_OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.all:
        done["items"] = {k: compact(v) for k, v in sorted(done["items"].items())}
        done["meta"] = {"model": model or done.get("meta", {}).get("model"), "date": date.today().isoformat(),
                        "pob": POB_COMMIT, "threshold": THRESHOLD, "kept": KEEP}
        OUT.write_text(json.dumps({"meta": done["meta"], "items": done["items"]}, ensure_ascii=False,
                                  separators=(",", ":")), encoding="utf-8")
        print(f"written {OUT}")


if __name__ == "__main__":
    main()
