"""How the build works, explained from PoB's own modifiers - the answers a player asks a friend who knows the game:
how the crit chance gets that high, why the mana runs out and what fixes it, what the meta gems do for the build.

- Crit: base (the weapon's for an attack, the gem's for a spell) plus flat additions, times the sum of "increased"
  (grouped: the small passives of one name together, notables, the ascendancy, jewels, items, gems), times each
  "more"; the conditions it stands on (an enemy blinded) and the crit and damage without each.
- Mana: spent per second against regenerated and leeched (and leech's own cap); leech by the damage types it takes
  from against what the skill's hit is made of (physical leech on a cold skill takes from almost nothing); the
  supports that fix the balance, priced in damage.
- Meta gems: what fills each one's Energy and how much per event, its modifiers, how often it goes off against a
  boss and a pack (poe2lab.analysis.triggers), what it triggers and what that gives the main skill, the Spirit it
  holds."""
import re

from .leveling import CHAIN_CONFIG
from .skills import UNCUT_SUPPORT_AREA, mechanics_of
from .triggers import trigger_view

DAMAGE_TYPES = ("Physical", "Fire", "Cold", "Lightning", "Chaos")
LEECH_STATS = [f"{t}DamageManaLeech" for t in DAMAGE_TYPES] + ["ElementalDamageManaLeech", "DamageManaLeech"]
LEECH_FLAGS = ("ManaLeechBasedOnElementalDamage", "ManaLeechBasedOnChaosDamage")
MANA_TOP = 3
_LIFE_COST = re.compile(r"into a life cost|life instead of mana", re.I)
# a support that saves mana by making the skill rare (a long cooldown) fixes nothing
_COOLDOWN = re.compile(r"gain a long cooldown", re.I)
MANA_DPS_FLOOR = -30.0  # a fix costing more of the skill's damage than this is no fix
TOP_ROWS = 12


def main_group(engine, groups: list[dict], rows: list[dict]) -> dict | None:
    """The skill the explanations are about: the build's main one when PoB gives it damage; else the one the player
    uses with the most (a main skill triggered by something else is not what the player presses)."""
    main = next((g for g in groups if g["main"]), None)
    by = {g["index"]: g for g in groups}
    if main and any(r["group"] == main["index"] and r["dps"] >= 1 for r in rows):
        return main
    for r in rows:
        g = by.get(r["group"])
        types = set(g["actives"][0]["types"]) if g and g["actives"] else set()
        if g and g["enabled"] and r["dps"] >= 1 and not types & {"Triggered", "Meta", "InbuiltTrigger"}:
            return g
    return main


def _grouped(rows: list[dict]) -> list[dict]:
    """Modifiers by where they come from: small passives of one name summed (their count kept), the rest one by one."""
    by = {}
    for r in rows:
        s = r["source"]
        conds = sorted({c.get("label") or c["var"] for c in r["conds"] if not c["neg"]})
        kind = ("asc" if s.get("asc") else "jewel" if s.get("jewel") else "tree" if s["kind"] == "Tree"
                else "item" if s["kind"] == "Item" else "gem" if s["kind"] == "Skill" else "other")
        key = (kind, s["name"], tuple(conds))
        e = by.setdefault(key, {"kind": kind, "name": s["name"], "small": s.get("nodeType") == "Normal",
                                "count": 0, "value": 0.0, "conds": conds})
        e["count"] += 1
        e["value"] += r["value"]
    return sorted(by.values(), key=lambda e: -abs(e["value"]))


def crit(engine, config: dict, group: dict) -> dict:
    """The main skill's crit chance, made of its base, flat additions, "increased" and "more"; and without each
    condition it stands on."""
    attack = "Attack" in (group["actives"][0]["types"] if group["actives"] else [])
    with engine.main_skill_of(group["index"]):
        src = engine.stat_sources(["CritChance"])
        out = engine.what_if(config=config)
        rows = src["stats"].get("CritChance", {"BASE": [], "INC": [], "MORE": []})
        boxes = {c["box"]: c.get("label") or c["var"] for t in ("INC", "MORE") for r in rows[t] for c in r["conds"] if c.get("box") and not c["neg"]}
        without = []
        for box, label in boxes.items():
            o = engine.what_if(config=config | {box: False})
            dps = (o["CombinedDPS"] / out["CombinedDPS"] - 1) * 100 if out.get("CombinedDPS") else 0.0
            without.append({"box": box, "label": label, "crit": o.get("CritChance", 0.0), "dps": dps})
    more = 1.0
    for r in rows["MORE"]:
        more *= 1 + r["value"] / 100
    return {"skill": src.get("skill") or group["actives"][0]["name"], "value": out.get("CritChance", 0.0),
            "base": (src.get("weaponCrit") if attack else src.get("skillCrit")) or 0.0, "weapon": src.get("weapon") if attack else None,
            "adds": _grouped(rows["BASE"]), "inc": _grouped(rows["INC"])[:TOP_ROWS], "incTotal": sum(r["value"] for r in rows["INC"]),
            "incRest": max(0, len(_grouped(rows["INC"])) - TOP_ROWS), "more": _grouped(rows["MORE"]), "moreTotal": more,
            "without": sorted(without, key=lambda w: w["dps"])}


def mana(engine, config: dict, group: dict, level: int | None = None) -> dict:
    """How the main skill's mana comes and goes, why leech takes little, and the supports that fix the balance."""
    with engine.main_skill_of(group["index"]):
        o = engine.what_if(config=config)
        src = engine.stat_sources(LEECH_STATS, flags=LEECH_FLAGS)
    hand = "MainHand." if any(k.startswith("MainHand.") and k.endswith("HitAverage") for k in o) else ""
    hits = {t: o.get(f"{hand}{t}HitAverage", 0.0) for t in DAMAGE_TYPES}
    total = sum(hits.values())
    shares = {t: v / total * 100 for t, v in hits.items() if total and v > 0}
    leech = [{"type": name.removesuffix("DamageManaLeech") or "All", "value": r["value"], "from": r["source"]["name"]}
             for name, per in src["stats"].items() for r in per.get("BASE", [])]
    spent, regen = o.get("ManaPerSecondCost", 0.0), o.get("ManaRegenRecovery", 0.0)
    leeched = o.get("ManaLeechRate", 0.0)
    net = regen + leeched - spent
    out = {"skill": src.get("skill") or group["actives"][0]["name"], "cost": o.get("ManaCost", 0.0), "spent": spent,
           "regen": regen, "leech": leeched, "leechMax": o.get("MaxManaLeechRate", 0.0), "net": net,
           "pool": o.get("ManaUnreserved", 0.0), "lasts": o.get("ManaUnreserved", 0.0) / -net if net < 0 else None,
           "shares": shares, "leechFrom": leech, "flags": [f for f, on in src["flags"].items() if on], "fixes": []}
    # PoB counts a skill whose cooldown the build bypasses as used without a break (Flicker Strike): in the game it
    # goes in bursts, the balance between them
    name = out["skill"].replace(" ", "")
    out["bursts"] = bool(engine.config().get(f"{name}BypassCD"))
    if net >= 0 or spent <= 0:
        return out
    # the supports that fix it, each tried in the skill's group (a socket it takes): the cuttable ones the character
    # can have by its level and the lineage ones (rare drops: marked); the build's own and their families left out;
    # one turning the cost into life not for a build with no life to pay it with (Chaos Inoculation)
    used = {x["name"] for g in engine.skill_groups() if g["enabled"] for x in g["gems"] if x["support"] and x["enabled"]}
    families = {x.get("family") or x["name"] for x in group["gems"]}
    catalog = {c["name"]: c for c in engine.gem_catalog() if c["support"]}
    cands = [c for c in engine.support_candidates(group["index"])
             if level is None or UNCUT_SUPPORT_AREA.get(c["tier"], 999) <= level]
    cands += [c for c in catalog.values() if c.get("lineage")]
    no_life = o.get("Life", 0) <= 1
    picked = {}
    for c in cands:
        info = catalog.get(c["name"], c)
        if c["name"] in used or (c.get("family") or c["name"]) in families or c["name"] in picked:
            continue
        if (no_life and _LIFE_COST.search(info.get("description", ""))) or _COOLDOWN.search(info.get("description", "")):
            continue
        picked[c["name"]] = c | {"lineage": bool(info.get("lineage")), "life": bool(_LIFE_COST.search(info.get("description", "")))}
    if not picked:
        return out
    gains = engine.support_gains(group["index"], [c["id"] for c in picked.values()], config, measure_group=group["index"])
    base = gains["base"]
    fixes = []
    for c in picked.values():
        g = gains.get(c["id"])
        dps = (g["dps"] / base["dps"] - 1) * 100 if g and base["dps"] else 0.0
        if g and g["mana"] - base["mana"] >= max(5.0, -net * 0.2) and dps > MANA_DPS_FLOOR:
            fixes.append({"name": c["name"], "mana": g["mana"] - base["mana"], "net": g["mana"], "tier": c.get("tier"),
                          "lineage": c["lineage"], "life": c["life"], "dps": dps})
    # the ones that close the gap first - costing the least damage, not paying with life, bringing most - then the
    # others by how much they bring
    out["fixes"] = sorted(fixes, key=lambda f: (f["net"] < 0, -round(f["dps"]) if f["net"] >= 0 else 0,
                                                f["life"], -f["mana"]))[:MANA_TOP]
    return out


def metas(engine, config: dict, groups: list[dict], main: dict | None, rows: list[dict]) -> list[dict]:
    """Each meta gem (and each skill an ascendancy or item triggers on crit): how often it goes off and from what,
    its Energy and what raises it, what it triggers and what that gives the main skill, the Spirit it holds."""
    view = trigger_view(engine, config, rows)
    base = engine.what_if(config=config)
    uses = set()
    main_skill = next((x for x in main["gems"] if not x["support"]), None) if main else None
    if main_skill:
        uses = set(mechanics_of(main_skill)["uses"])
    by = {g["index"]: g for g in groups}
    out = []
    for t in view:
        g = by.get(t["group"])
        gives = []
        for s in t["skills"]:
            gem = next((x for x in (g["gems"] if g else []) if x["name"] == s["name"]), None)
            if not gem:
                continue
            for key in sorted(set(mechanics_of(gem)["creates"]) & uses):
                give = {"skill": s["name"], "mechanic": key, "dps": None}
                if key in CHAIN_CONFIG:
                    var, off = CHAIN_CONFIG[key]
                    o = engine.what_if(config=config | {var: off})
                    give["dps"] = (o["CombinedDPS"] / base["CombinedDPS"] - 1) * 100 if base.get("CombinedDPS") else None
                gives.append(give)
        spirit = 0
        if g and t["kind"] == "energy":
            o = engine.what_if(config=config, disable_gems=[(g["index"], x["index"]) for x in g["gems"]])
            spirit = max(0, round(o.get("SpiritUnreserved", 0) - base.get("SpiritUnreserved", 0)))
        out.append(t | {"gives": gives, "spirit": spirit})
    return out


def explain(engine, config: dict, rows: list[dict], level: int | None = None) -> dict:
    """The explanations for the build's main skill (see the module's note)."""
    groups = engine.skill_groups()
    g = main_group(engine, groups, rows)
    if g is None:
        return {"skill": None, "crit": None, "mana": None, "metas": []}
    return {"skill": g["actives"][0]["name"] if g["actives"] else None, "group": g["index"],
            "crit": crit(engine, config, g), "mana": mana(engine, config, g, level),
            "metas": metas(engine, config, groups, g, rows)}
