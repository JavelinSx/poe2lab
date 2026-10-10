"""The build's conditions in one place: everything that holds "while / if / against / for each" - one answer each, the
same for every line that waits for it.

Three tiers of the same thing (docs: the constructor's plan, point 3):
  A. a condition PoB knows and asks about (its Configuration box: "Have you Killed Recently?", "Is the enemy Frozen?");
  B. a line PoB does not read, which poe2lab rewrites so it does (poe2lab.analysis.unmodeled) - its condition is the
     correction's uptime;
  C. a condition inside a line PoB does not read ("...if you've Killed Recently, 30% more Damage"): the phrase maps to
     the box of tier A (condition_of), so the line takes that box's answer.

For each condition the program says what share of the fight it holds where it can work it out - an ailment on the
enemy from its chance, the hits per second and its duration (poe2lab.analysis.combat), "recently" (the last 4 seconds)
from how often the build hits or crits, killing on maps - and the player's answer, when there is one, takes its place.
The damage and defences are then counted with each condition at its share: never + share x (always - never), the
conditions independent of each other (their gains multiply)."""
import math
import re

from .combat import ailment_uptimes

RECENTLY = 4.0  # "recently" in the game: the past 4 seconds
# a line's condition, by its words -> PoB's Configuration box (the same answer as the box's)
PHRASES = [
    (r"\bif you(?:'ve| have) Killed Recently\b|\bif you've killed an enemy recently\b", "conditionKilledRecently"),
    (r"\bif you(?:'ve| have) (?:dealt a )?Critical(?:ly)? (?:Hit|Struck)(?: an enemy)? Recently\b|\bif you(?:'ve| have) Crit Recently\b",
     "conditionCritRecently"),
    (r"\bif you(?:'ve| have) been Hit Recently\b", "conditionBeenHitRecently"),
    (r"\bif you(?:'ve| have) Hit(?: an enemy)? Recently\b", "conditionHitRecently"),
    (r"\bif you(?:'ve| have) Blocked Recently\b", "conditionBlockedRecently"),
    (r"\bif you(?:'ve| have) Attacked Recently\b", "conditionAttackedRecently"),
    (r"\bif you(?:'ve| have) cast a Spell Recently\b", "conditionCastSpellRecently"),
    (r"\bwhile (?:you are )?on Low Life\b", "conditionLowLife"),
    (r"\bwhile (?:you are )?on Full Life\b", "conditionFullLife"),
    (r"\bwhile (?:you are )?Moving\b", "conditionMoving"),
    (r"\bwhile (?:you are )?Leeching\b", "conditionLeeching"),
    (r"\b(?:against|to|from) Frozen (?:enemies|targets)\b|\bFrozen enemies\b", "conditionEnemyFrozen"),
    (r"\b(?:against|to|from) Shocked (?:enemies|targets)\b|\bShocked enemies\b", "conditionEnemyShocked"),
    (r"\b(?:against|to|from) Ignited (?:enemies|targets)\b|\bIgnited enemies\b", "conditionEnemyIgnited"),
    (r"\b(?:against|to|from) Chilled (?:enemies|targets)\b|\bChilled enemies\b", "conditionEnemyChilled"),
    (r"\b(?:against|to|from) Poisoned (?:enemies|targets)\b|\bPoisoned enemies\b", "conditionEnemyPoisoned"),
    (r"\b(?:against|to|from) Bleeding (?:enemies|targets)\b|\bBleeding enemies\b", "conditionEnemyBleeding"),
    (r"\b(?:against|to|from) Stunned (?:enemies|targets)\b|\bStunned enemies\b", "conditionEnemyStunned"),
    (r"\b(?:against|to|from) enemies on Low Life\b", "conditionEnemyLowLife"),
]
PHRASES = [(re.compile(rx, re.I), var) for rx, var in PHRASES]
# an event with an effect for a while after it: "When you Freeze a target ..., ... for 15 seconds"
EVENT = re.compile(r"\b(?:when|after) you (Freeze|Shock|Ignite|Kill|Crit|Critically Hit|Block|Hit)\b", re.I)
FOR_SECONDS = re.compile(r"\bfor (\d+(?:\.\d+)?) seconds?\b", re.I)
PER = re.compile(r"\b(?:per|for each) (\d+ )?(\w+(?: \w+)?)\b", re.I)


def condition_of(text: str) -> dict | None:
    """The condition inside a game line, when its words name one: {"var": PoB's box, "phrase": the words} or for an
    event, {"event": what happens, "seconds": how long the effect lasts}; None when the line holds no condition."""
    line = " ".join(text.split())
    for rx, var in PHRASES:
        m = rx.search(line)
        if m:
            return {"var": var, "phrase": m.group(0)}
    m = EVENT.search(line)
    if m:
        sec = FOR_SECONDS.search(line)
        return {"event": m.group(1).lower(), "phrase": m.group(0), "seconds": float(sec.group(1)) if sec else None}
    return None


def _recent(rate: float) -> float:
    """The share of the fight something that happens `rate` times a second has happened in the last 4 seconds."""
    return 1 - math.exp(-rate * RECENTLY) if rate > 0 else 0.0


def suggest(var: str, out: dict, boss: bool = False) -> dict | None:
    """What share of the fight a condition holds, as the program can tell from PoB's output for the main skill:
    {"uptime": 0..1, "how": a key for the page's words, "values": the numbers it took}; None when it cannot tell
    (the player's answer only)."""
    hits = (out.get("Speed") or 0) * (out.get("HitChance") or 0) / 100
    ups = ailment_uptimes(out)
    if var in ups:
        u = ups[var]
        return {"uptime": u["uptime"], "how": "ailment", "values": {"chance": u["chance"], "duration": u["duration"], "hits": hits}}
    crit = min(1.0, (out.get("CritChance") or 0) / 100)
    if var in ("conditionHitRecently", "conditionAttackedRecently", "conditionHitMeleeRecently", "conditionHitRecentlyWithWeapon"):
        return {"uptime": _recent(hits), "how": "recentHits", "values": {"hits": hits}}
    if var == "conditionCritRecently":
        return {"uptime": _recent(hits * crit), "how": "recentCrits", "values": {"hits": hits, "crit": crit}}
    if var == "conditionKilledRecently":
        # on maps the packs die all the time; on a boss nothing dies
        return {"uptime": 0.0 if boss else 0.9, "how": "boss" if boss else "maps", "values": {}}
    if var in ("conditionLowLife", "conditionFullLife"):
        life, reserved = out.get("Life") or 0, out.get("LifeReserved") or 0
        low = life > 0 and reserved / life >= 0.65  # a build that reserves its life lives on low life
        if var == "conditionLowLife":
            return {"uptime": 1.0 if low else 0.0, "how": "reserved" if low else "notLow", "values": {}}
        return {"uptime": 0.0 if low else 0.3, "how": "fullLife", "values": {}}
    return None


def event_uptime(event: str, seconds: float | None, out: dict) -> dict | None:
    """The share of the fight an effect "for N seconds when you <event>" holds, from how often the event happens."""
    if not seconds:
        return None
    hits = (out.get("Speed") or 0) * (out.get("HitChance") or 0) / 100
    crit = min(1.0, (out.get("CritChance") or 0) / 100)
    ups = ailment_uptimes(out)
    rate = {"hit": hits, "crit": hits * crit, "critically hit": hits * crit}.get(event)
    if rate is None and event in ("freeze", "shock", "ignite"):
        key = {"freeze": "conditionEnemyChilled", "shock": "conditionEnemyShocked", "ignite": "conditionEnemyIgnited"}[event]
        rate = hits * ups[key]["chance"] if key in ups else 0.0
    if rate is None:
        return None
    return {"uptime": 1 - math.exp(-rate * seconds) if rate > 0 else 0.0, "how": "event",
            "values": {"rate": rate, "seconds": seconds}}


def combine(base: float, gains: list[tuple[float, float, bool]]) -> float:
    """PoB's number with each condition at its share of the fight instead of all or nothing: `gains` of (the change
    in % when PoB's answer is flipped, the share 0..1, whether PoB counts it as on). One PoB counts as off adds its
    gain for its share; one it counts as on loses its gain for the rest. The conditions multiply (independent)."""
    out = base
    for pct, share, on in gains:
        share = max(0.0, min(1.0, share))
        out *= 1 + ((1 - share) if on else share) * pct / 100
    return out


# where a condition comes from, for the page: items, passives, gems (PoB's own mechanics - "Base", "Many Sources" - not)
SOURCE_KINDS = ("Item", "Tree", "Skill")


def view(impacts: list[dict], sources: list[dict], out: dict, answers: dict, gaps: list, boss: bool = False) -> dict:
    """Every condition that moves the build's numbers, with what it moves, where it comes from, what share of the
    fight it holds (the player's answer, else the program's estimate, else PoB's yes/no) and the damage counted with
    every condition at its share. `impacts`: poe2lab.analysis.conditions.audit as dicts; `sources`:
    PobEngine.condition_sources; `out`: PoB's output for the main skill; `answers`: the player's shares by box;
    `gaps`: the lines PoB does not read (poe2lab.knowledge), those with a condition joined to it (tier C)."""
    by = {}
    for r in sources:
        if r["source"]["kind"] in SOURCE_KINDS:
            by.setdefault(r["var"], [])
            names = {(x["kind"], x["name"]) for x in by[r["var"]]}
            if (r["source"]["kind"], r["source"]["name"]) not in names:
                by[r["var"]].append(r["source"])
    lines = {}
    for g in gaps:
        c = condition_of(g.text)
        if c and c.get("var"):
            lines.setdefault(c["var"], []).append({"where": g.where, "text": g.text, "text_local": g.text_local})
    rows = []
    for imp in impacts:
        var = imp["var"]
        sugg = suggest(var, out, boss)
        ans = answers.get(var)
        share = ans if ans is not None else sugg["uptime"] if sugg else (1.0 if imp["checked"] else 0.0)
        rows.append({"var": var, "label": imp["label"], "on": imp["checked"], "dps": round(imp["dps_pct"], 1),
                     "phys": round(imp["phys_hit_pct"], 1), "ele": round(imp["ele_hit_pct"], 1),
                     "chaos": round(imp["chaos_hit_pct"], 1), "recovery": round(imp["recovery_pct"], 1),
                     "sources": by.get(var, []), "lines": lines.get(var, []), "suggested": sugg, "answer": ans,
                     "share": share})
    base = out.get("CombinedDPS", 0)
    expected = combine(base, [(r["dps"], r["share"], r["on"]) for r in rows])
    return {"conditions": rows, "dps": {"pob": base, "expected": expected}}
