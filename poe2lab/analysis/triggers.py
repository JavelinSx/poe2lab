"""How often the build's triggered skills go off, which PoB-PoE2 does not count: it has no Energy, so a spell in a
meta gem is priced as if cast by hand and a skill triggered on crit is given no damage per second.

A meta gem gains Energy on an event and triggers its spells when it has the Energy one trigger costs:
    triggers per second = Energy per second / Energy per trigger
- Energy per event: the gem's base (its stat "gain X centienergy per monster power on <event>", 100 = 1 Energy)
  times the power of the monster it happened to (a boss 20, a normal monster 1), times the Energy modifiers: the
  gem's and its supports' "increased Energy" and the passives' and items' (which PoB does not read, Invoker's "Meta
  Skills gain 35% more Energy").
- A critical hit gives Energy by the share of the enemy's Ailment Threshold it deals. Whether more than all of
  it counts is not known: the low end takes up to 100%, the high end all of it (one trigger per crit at most).
- Events per second come from the skill that makes them, as PoB computes it: its hits per second (times the crit
  chance, the ignite or shock chance, the freeze buildup).
- Energy per trigger: for a gem whose maximum is the total of its socketed spells, 1 per 10 ms of their base cast
  time (Cast on Critical with Profane Ritual: 100); otherwise the gem's maximum.
A skill an ascendancy or item triggers on crit ("Trigger Elemental Expression on Melee Critical Hit") goes off on
every such crit, but not more often than its cooldown allows.

Two fights: a boss (power 20, one target) and a pack of normal monsters (power 1, PACK_TARGETS of them under one
area hit). Events this cannot count - kills, stuns, blocks, dodge rolls, minion deaths - are listed, not guessed."""
import re

from .skills import trigger_hit

POWER = {"boss": 20, "pack": 1}
PACK_TARGETS = 3  # normal monsters one area hit catches in a pack
AREA_TYPES = {"Area", "Projectile", "Chains"}
# a meta gem's Energy stats: "<gem>_gain_X_centienergy_per_monster_power_on_<event>"
_GAIN = re.compile(r"gain_X_centienergy_per_monster_power_on_(\w+)$")
_CAST_TIME_GAIN = re.compile(r"gain_X_centienergy_per_10ms_base_cast_time$")
_MORE_ENERGY = re.compile(r"meta skills gain (\d+)% more energy", re.I)
_INC_ENERGY = re.compile(r"(\d+)% increased energy(?! shield)", re.I)
_DOUBLE_ENERGY = re.compile(r"energy generation is doubled", re.I)
_REFUND = "trigger_skills_refund_half_energy_spent_chance_%"
# "Trigger Elemental Expression on Melee Critical Hit", "Trigger Elemental Storm on Critical Hit with Spells"
_ON_CRIT = re.compile(r"^Trigger (.+?) on (Melee )?Critical Hits?(?: with (Spells|Attacks))?", re.I)
NEEDS = {"Spells": "Spell", "Attacks": "Attack"}
COUNTED = {"crit", "hit", "melee_hit", "ignite", "shock", "freeze"}


def _per_second(row: dict) -> float:
    """Hits per second of a skill as PoB computes it (a skill with several hits per use: its hit rate)."""
    return (row.get("hitSpeed") or row.get("speed") or 0.0) * (row.get("hitChance") or 0.0) / 100


def _events(row: dict, event: str) -> float:
    """How many times per second the skill makes the event happen to one enemy."""
    hits = _per_second(row)
    if event == "crit":
        return hits * (row.get("crit") or 0.0) / 100
    if event in ("hit", "melee_hit"):
        return hits
    if event == "ignite":
        return hits * min(1.0, (row.get("igniteOnHit") or 0.0) / 100)
    if event == "shock":
        return hits * min(1.0, (row.get("shockOnHit") or 0.0) / 100)
    if event == "freeze":
        return hits * min(1.0, (row.get("freezeBuildup") or 0.0) / 100)
    return 0.0


def _energy_modifiers(lines: list[str]) -> tuple[float, float]:
    """(increased %, more multiplier) for meta skills' Energy from passive and item lines PoB does not read."""
    inc, more = 0.0, 1.0
    for line in lines:
        if "meta" not in line.lower() and "energy generation" not in line.lower():
            continue
        if m := _MORE_ENERGY.search(line):
            more *= 1 + int(m.group(1)) / 100
        elif m := _INC_ENERGY.search(line):
            inc += int(m.group(1))
        if _DOUBLE_ENERGY.search(line):
            more *= 2
    return inc, more


def _feeder(rows: list[dict], types: dict, event: str, excluded: set, need: str | None = None) -> dict | None:
    """The skill the player uses that makes the event most often: the one with the most damage among those
    that can (a triggered skill and a spell socketed in a meta gem are not used by the player). `need`: a skill
    type it must have ("Melee", "Spell")."""
    if event in ("hit", "melee_hit"):  # the gems that gain Energy on hits gain it on melee ones
        need = "Melee"
    best = None
    for r in rows:
        t = types.get((r["group"], r["name"]), set())
        if (r["group"], r["name"]) in excluded or "Triggered" in t or r["dps"] <= 0 or (need and need not in t):
            continue
        if _events(r, event) > 0 and (best is None or r["dps"] > best["dps"]):
            best = r
    return best


def _targets(row: dict, types: dict, fight: str) -> int:
    t = types.get((row["group"], row["name"]), set())
    return PACK_TARGETS if fight == "pack" and t & AREA_TYPES else 1


def _rate(gains: dict, feeders: dict, types: dict, multiplier: float, cost: float, capped: bool, fight: str) -> float:
    """Triggers per second in a fight."""
    energy, events = 0.0, 0.0
    for event, base in gains.items():
        row = feeders.get(event)
        if not row:
            continue
        n = _events(row, event) * _targets(row, types, fight)
        share = 1.0
        if event == "crit" and row.get("threshold") and row.get("hit"):
            share = row["hit"] / row["threshold"]
            share = min(1.0, share) if capped else share
        energy += n * base / 100 * POWER[fight] * share * multiplier
        events += n
    if cost <= 0:
        return 0.0
    # a gem that triggers on reaching its maximum goes off once per event at most
    return min(energy / cost, events)


def _per_trigger(row: dict, hit: float) -> float:
    """The damage one trigger deals: a skill that keeps hitting for a duration (a storm) hits that many times."""
    hits = (row.get("hitSpeed") or 0) * (row.get("duration") or 0)
    return hit * max(1.0, hits)


def _skill(name: str, row: dict, hit: float, rate: dict) -> dict:
    """A triggered skill: how often it goes off (its cooldown caps it) and its damage per second from that."""
    cd = row.get("cooldown") or 0
    r = {f: [min(x, 1 / cd) if cd else x for x in v] for f, v in rate.items()}
    per = _per_trigger(row, hit) if hit else 0.0
    return {"name": name, "hit": hit, "perTrigger": per, "rate": r, "cooldown": cd, "pobDps": row.get("dps") or 0.0,
            "dps": {f: [x * per for x in v] for f, v in r.items()} if per else None}


def trigger_view(engine, config: dict, rows: list[dict] | None = None) -> list[dict]:
    """For each meta gem that triggers with Energy and each skill triggered on crit by a passive or an item: how
    often it goes off against a boss and a pack ([low, high] each: see the module's note), what feeds it, and the
    damage per second of the skills it triggers (one trigger's hit times the rate)."""
    rows = rows if rows is not None else engine.skill_damage(config)
    groups = {g["index"]: g for g in engine.skill_groups()}
    types = {(g["index"], x["name"]): set(x.get("types", [])) for g in groups.values() for x in g["gems"] if not x["support"]}
    by_skill = {(r["group"], r["name"]): r for r in rows}
    lines = [line for n in engine.tree_graph()["nodes"] if n["alloc"] for line in n["stats"]]
    lines += [l["line"] for it in engine.equipped_item_details() for k in ("implicit", "explicit", "runes", "enchant")
              for l in it.get(k, [])]
    inc_lines, more_lines = _energy_modifiers(lines)
    inputs = {g["group"]: g for g in engine.trigger_inputs()}
    metas, excluded = [], set()
    for gi, inp in inputs.items():
        meta = next((a for a in inp["actives"] if any("ongoing_trigger" in k for k in a["stats"])), None)
        if meta:
            socketed = [a for a in inp["actives"] if a is not meta]
            excluded |= {(gi, a["name"]) for a in inp["actives"]}
            metas.append((gi, meta, socketed, inp["supportEnergy"]))
    out = []
    for gi, meta, socketed, support in metas:
        st = meta["stats"]
        gains = {m.group(1): v for k, v in st.items() if (m := _GAIN.search(k)) and v}
        unknown = sorted(e for e in gains if e not in COUNTED)
        gains = {e: v for e, v in gains.items() if e in COUNTED}
        if any(_CAST_TIME_GAIN.search(k) for k in st):
            unknown.append("cast_time")
        if not gains:
            if unknown or any("gain" in k for k in st):
                out.append({"group": gi, "kind": "energy", "gem": meta["name"], "unknown": unknown or ["other"],
                            "skills": [{"name": a["name"]} for a in socketed]})
            continue
        if st.get("generic_ongoing_trigger_maximum_energy_is_total_of_socketed_skills") or not st.get("generic_ongoing_trigger_maximum_energy"):
            cost = sum(a["castTime"] for a in socketed) * 1000 / 10
        else:
            cost = sum(a["castTime"] for a in socketed) * 1000 / 10 or st["generic_ongoing_trigger_maximum_energy"]
        cost *= 1 + st.get("skill_maximum_energy_+%", 0) / 100
        cost *= 1 - st.get(_REFUND, 0) / 100 * 0.5
        multiplier = (1 + (st.get("energy_generated_+%", 0) + support + inc_lines) / 100) * more_lines
        multiplier *= 1 + st.get("active_skill_energy_generated_+%_final", 0) / 100
        feeders = {e: _feeder(rows, types, e, excluded) for e in gains}
        rate = {fight: [_rate(gains, feeders, types, multiplier, cost, capped, fight) for capped in (True, False)]
                for fight in POWER}
        fed = [{"event": e, "skill": r["name"], "perSecond": _events(r, e)} for e, r in feeders.items() if r]
        skills = [_skill(a["name"], by_skill.get((gi, a["name"])) or {}, (by_skill.get((gi, a["name"])) or {}).get("hit") or 0.0, rate)
                  for a in socketed]
        # what the Energy is made of: per event, and the modifiers - the gem's, its supports', the passives' and items'
        energy = {"gains": {e: v / 100 for e, v in gains.items()}, "gem": st.get("energy_generated_+%", 0),
                  "supports": support, "passives": inc_lines, "more": more_lines}
        out.append({"group": gi, "kind": "energy", "gem": meta["name"], "cost": cost, "multiplier": multiplier,
                    "rate": rate, "fed": fed, "unknown": unknown, "skills": skills, "energy": energy})
    # a skill a passive or an item triggers on crit
    seen = set()
    for line in lines:
        m = _ON_CRIT.search(line)
        if not m or m.group(1) in seen:
            continue
        name = m.group(1)
        seen.add(name)
        gi = next((i for i, g in groups.items() if g["enabled"] and any(a["name"] == name for a in g["actives"])), None)
        if gi is None:
            continue
        own = {(gi, a["name"]) for a in groups[gi]["actives"]}
        feeder = _feeder(rows, types, "crit", excluded | own, "Melee" if m.group(2) else NEEDS.get(m.group(3) or ""))
        if not feeder:
            continue
        rate = {}
        for fight in POWER:
            n = _events(feeder, "crit") * _targets(feeder, types, fight)
            rate[fight] = [n, n]
        row = by_skill.get((gi, name)) or {}
        skill = _skill(name, row, trigger_hit(engine, config, groups[gi]), rate)
        out.append({"group": gi, "kind": "crit", "gem": name, "line": line, "rate": skill["rate"],
                    "fed": [{"event": "crit", "skill": feeder["name"], "perSecond": _events(feeder, "crit")}],
                    "unknown": [], "skills": [skill]})
    return out
