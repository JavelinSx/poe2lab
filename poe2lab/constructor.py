"""The build author's constructor: the character from PoB laid out the way the author explains it - who it is, its
skills with their gems, its gear slot by slot (the runes, soul cores and idols in its sockets), the passive tree's
keystones, notables and ascendancy, the jewels and what they do on the tree, the flasks and charms, the campaign's
reward choices. Nothing is calculated here (the program's advice is on a button); every element has an id the
author's notes are kept under (poe2lab.author), so a note stays on its element when the character is loaded again.

Element ids: "gem:<name>" (a gem, wherever it is socketed), "sk:<active names joined by +>" (a socket group),
"gear:<slot>" (an item slot, flasks and charms too), "node:<id>" (a passive), "jwl:<socket node id>" (a jewel),
"qst:<PoB variable>" (a reward choice), "sec:<section>" (a section's own notes). The build's Мин stage (the same build at
its start or on a budget) has its own gear and jewels: their ids end in "@min"; gems and passives share their notes."""
import re

from .analysis import jewels as jewel_effects
from .analysis.threats import MAPS_LEVEL

SECTIONS = ("character", "skills", "gear", "tree", "jewels", "flasks", "quests", "leveling")
# the doll's order; anything else the build wears comes after
GEAR_ORDER = ("Weapon 1", "Weapon 2", "Weapon 1 Swap", "Weapon 2 Swap", "Helmet", "Body Armour", "Gloves", "Boots",
              "Amulet", "Ring 1", "Ring 2", "Belt")
FLASK_SLOTS = ("Flask", "Charm")


def group_id(actives: list[str]) -> str:
    """A socket group's id: its active skills (the same as the Skills tab's notes, "sk:Ice Strike")."""
    return "sk:" + "+".join(actives)


def _item(it: dict) -> dict:
    keep = ("name", "baseName", "rarity", "itemLevel", "quality", "corrupted", "implicit", "explicit", "runes", "enchant")
    return {k: it.get(k) for k in keep} | {"lines": [m["line"] for m in (it.get("implicit") or []) + (it.get("explicit") or [])]}


STAGES = ("max", "min")


def stage_suffix(stage: str) -> str:
    """What a stage's own elements' ids end in: the Макс (the build itself) none, the Мин "@min"."""
    return "" if stage == "max" else f"@{stage}"


def layout(engine, quest_rows: list[dict] | None = None, stage: str = "max") -> dict:
    """The character as PoB has it, by section, with the id of each element."""
    own = stage_suffix(stage)
    info = engine.info()
    groups = []
    for g in engine.skill_groups():
        actives = [a["name"] for a in g.get("actives") or []]
        groups.append({"id": group_id(actives), "index": g["index"], "enabled": g.get("enabled", True),
                       "main": g.get("main", False), "actives": actives,
                       "gems": [{"id": f"gem:{x['name']}", "name": x["name"], "support": x.get("support", False),
                                 "level": x.get("level"), "quality": x.get("quality"), "enabled": x.get("enabled", True)}
                                for x in g.get("gems") or []]})
    worn = engine.equipped_item_details()
    gear, flasks = [], []
    for it in sorted(worn, key=lambda x: (GEAR_ORDER.index(x["slot"]) if x["slot"] in GEAR_ORDER else 99, x["slot"])):
        row = {"id": f"gear:{it['slot']}{own}", "slot": it["slot"], "item": _item(it)}
        (flasks if it["slot"].startswith(FLASK_SLOTS) else gear).append(row)
    nodes = engine.allocated_nodes()
    tree = {"ascendancy": [n for n in nodes if n["ascendancy"] and n["type"] in ("Notable", "Keystone")],
            "keystones": [n for n in nodes if n["type"] == "Keystone" and not n["ascendancy"]],
            "notables": [n for n in nodes if n["type"] == "Notable" and not n["ascendancy"]],
            "small": sum(1 for n in nodes if n["type"] == "Normal" and not n["ascendancy"])}
    for part in ("ascendancy", "keystones", "notables"):
        tree[part] = [{"id": f"node:{n['id']}", "node": n["id"], "name": n["name"], "type": n["type"]} for n in tree[part]]
    effects = engine.jewel_effects()
    jewels = [{"id": f"jwl:{s['node']}{own}", "node": s["node"], "slot": s["slot"], "near": s["near"], "item": _item(s["item"]),
               "effect": jewel_effects.describe(s["item"], effects.get(s["node"]))}
              for s in engine.jewel_sockets() if s["item"]]
    quests = [{"id": f"qst:{q['var']}", "var": q["var"], "act": q["act"], "area": q["area"], "info": q["info"],
               "level": q.get("level"), "stat": q.get("stat"), "options": q.get("options") or [], "value": q.get("value")}
              for q in (quest_rows if quest_rows is not None else engine.quest_rewards())]
    return {"character": {"class": info["class"], "ascendancy": info["ascendancy"], "level": info["level"],
                          "mainSkill": engine.main_skill()},
            "skills": groups, "gear": gear, "flasks": flasks, "tree": tree, "jewels": jewels, "quests": quests,
            "sections": list(SECTIONS), "stage": stage}


# ---- the levelling the author writes: stage by stage, the links, the weapon, the passives ----
# Up to maps the gear is the usual (life and resistances); what makes the levelling easy is the skill links, the
# weapon they need and the passives. The author puts them in each stage; the program says at once what a stage's
# character can have (a gem's level, the passive points) and, on a button, works the stage out in PoB: a character
# of the stage's last level made from nothing with these links, this weapon and these passives.
RESIST = re.compile(r"\+(\d+)% to (Fire|Cold|Lightning|Chaos|all Elemental) Resistances?", re.I)
WEAPON_SLOT = "Weapon 1"


def _resists(lines) -> dict[str, int]:
    out = {}
    for line in lines:
        for m in RESIST.finditer(line):
            kinds = ("fire", "cold", "lightning") if m.group(2).lower() == "all elemental" else (m.group(2).lower(),)
            for k in kinds:
                out[k] = out.get(k, 0) + int(m.group(1))
    return out


def leveling_info(engine) -> dict:
    """What the levelling editor needs before anything is calculated: the stages (levels, the resistance penalty,
    the passive points by the stage's end, the resistances the campaign's fixed rewards give by then, the ones a
    choice can add), and from which character level each gem can be had."""
    from .analysis import leveling
    from .analysis.skills import available_level
    rows = engine.quest_rewards()
    stages = []
    for st in leveling.stages():
        top = st["to"] or MAPS_LEVEL
        fixed = _resists(r["stat"] for r in rows if not r.get("options") and r["level"] <= top)
        choice = _resists(o for r in rows if r.get("options") and r["level"] <= top for o in r["options"])
        stages.append(st | {"level": top, "points": top - 1, "questRes": fixed, "choiceRes": choice})
    gems = {}
    for g in engine.gem_catalog():
        lv = available_level(g)
        if lv is not None:
            gems[g["name"]] = lv
    return {"stages": stages, "gemLevels": gems}


def _token(tok: str) -> tuple[str, str]:
    kind, _, rest = tok.partition(":")
    return kind, rest


def check_stage(base, level: int, links: list[list[str]], weapon: list[str], tree: list[str]) -> dict:
    """A stage of the levelling worked out in PoB: a character of the build's ascendancy at `level` made from nothing,
    with the author's links (each gem at the highest level a character of that level can use), the weapon (a plain
    base, or a unique) with its runes, and the passives in the order given (each with the path to it). Its numbers
    against an enemy of that level, each link's damage (0: it does not work with this weapon), the passive points it
    took against the ones the level gives, the attributes the gems want and mana it cannot keep up."""
    from .analysis.threats import MapProfile
    from .engine import PobEngine, PobError
    from . import newbuild
    info = base.info()
    ids = {a["name"]: a["id"] for c in newbuild.classes(base) for a in c["ascendancies"]}
    asc = ids.get(info["ascendancy"]) or next((a["id"] for c in newbuild.classes(base) if c["name"] == info["class"]
                                               for a in c["ascendancies"]), None)
    e = PobEngine()
    e.load_xml(newbuild.empty_build(base, asc, level), "stage")
    known = {g["name"]: g["id"] for g in base.gem_catalog()}
    for g in base.skill_groups():
        for x in g["gems"]:
            known.setdefault(x["name"], x["id"])
    missing, groups = [], []
    for link in links:
        names = [_token(t)[1] for t in link if _token(t)[0] in ("gem", "support")]
        gem_ids = [known[n] for n in names if n in known]
        missing += [n for n in names if n not in known]
        if not gem_ids:
            continue
        lv = e.gem_level_at(gem_ids, level)
        group = 0
        for gid in gem_ids:
            group = e.set_gem(group, None, gid, level=lv.get(gid, 1))
        groups.append({"group": group, "gems": [{"name": n, "level": lv.get(known[n], 1)} for n in names if n in known]})
    weapon_note = None
    base_names = {b["name"]: b for b in base.item_bases()}
    uniques = {u["name"]: u for u in base.unique_catalog()}
    runes = [_token(t)[1] for t in weapon if _token(t)[0] == "rune"]
    item = next((t for t in weapon if _token(t)[0] in ("base", "unique")), None)
    if item:
        kind, name = _token(item)
        if kind == "unique" and name in uniques:
            text = uniques[name]["raw"]
            weapon_note = {"name": name, "level": uniques[name].get("level"), "unique": True}
        else:
            sockets = " ".join("S" for _ in runes) if runes else ""
            text = "Rarity: Normal\n" + name + (f"\nSockets: {sockets}" if sockets else "") + "".join(f"\nRune: {r}" for r in runes)
            weapon_note = {"name": name, "level": (base_names.get(name) or {}).get("level"), "unique": False}
        try:
            e.equip_item(WEAPON_SLOT, text)
        except PobError:
            weapon_note = (weapon_note or {}) | {"failed": True}
    unreachable = []
    for t in tree:
        kind, rest = _token(t)
        if kind != "passive":
            continue
        node_id = rest.split("|")[0]
        try:
            e.tree_add(int(node_id))
        except (PobError, ValueError):
            unreachable.append(rest.split("|", 1)[-1])
    cfg = MapProfile.for_level(level).config()
    rows = {r["group"]: r for r in e.skill_damage(cfg)}
    for g in groups:
        g["dps"] = round(rows.get(g["group"], {}).get("dps", 0))
    if groups:
        e.set_main_skill(groups[0]["group"], 1)
    out = e.what_if(config=cfg)
    attrs = [{"attr": a, "need": round(out.get("Req" + a, 0)), "have": round(out.get(a, 0))}
             for a in ("Str", "Dex", "Int") if out.get("Req" + a, 0) > out.get(a, 0)]
    cost, regen = out.get("ManaPerSecondCost", 0), out.get("ManaRegenRecovery", 0)
    return {"level": level, "links": groups, "missing": missing, "weapon": weapon_note,
            "points": {"used": e.tree_points(), "budget": level - 1}, "unreachable": unreachable,
            "life": round(out.get("Life", 0)), "es": round(out.get("EnergyShield", 0)), "ehp": round(out.get("TotalEHP", 0)),
            "mana": {"cost": round(cost, 1), "regen": round(regen, 1), "ok": cost <= regen or cost == 0},
            "attributes": attrs,
            "resists": {k: round(out.get(f"{k.capitalize()}Resist", 0)) for k in ("fire", "cold", "lightning", "chaos")}}
