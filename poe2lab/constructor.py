"""The build author's constructor: the character from PoB laid out the way the author explains it - who it is, its
skills with their gems, its gear slot by slot (the runes, soul cores and idols in its sockets), the passive tree's
keystones, notables and ascendancy, the jewels and what they do on the tree, the flasks and charms, the campaign's
reward choices. Nothing is calculated here (the program's advice is on a button); every element has an id the
author's notes are kept under (poe2lab.author), so a note stays on its element when the character is loaded again.

Element ids: "gem:<name>" (a gem, wherever it is socketed), "sk:<active names joined by +>" (a socket group),
"gear:<slot>" (an item slot, flasks and charms too), "node:<id>" (a passive), "jwl:<socket node id>" (a jewel),
"qst:<PoB variable>" (a reward choice), "sec:<section>" (a section's own notes). The build's Мин stage (the same build at
its start or on a budget) has its own gear and jewels: their ids end in "@min"; gems and passives share their notes."""
from .analysis import jewels as jewel_effects

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
