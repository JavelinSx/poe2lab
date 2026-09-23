"""My build against a reference one (a guide someone else made, usually with gear already in it).

Two questions: how far are my characteristics from the reference, and what each of its items would do in my
build - slot by slot and all of them at once. The reference is measured with its own profile; items are tried in
my build with mine, so "their item" means the item alone, not their tree."""
from dataclasses import asdict

from .items import compare
from .threats import DAMAGE_TYPES, MapProfile, survivable_hits

GEAR_SLOTS = ["Weapon 1", "Weapon 2", "Weapon 1 Swap", "Weapon 2 Swap", "Helmet", "Body Armour", "Gloves", "Boots",
              "Amulet", "Ring 1", "Ring 2", "Belt"]  # swap slots too: a main skill may hit with the second weapon set
# (group, key in PoB output, name key for the UI, higher is better)
STATS = [
    ("offence", "CombinedDPS", "dps", True),
    ("offence", "HitChance", "hitChance", True),
    ("offence", "CritChance", "critChance", True),
    ("offence", "Speed", "speed", True),
    ("defence", "Life", "life", True),
    ("defence", "EnergyShield", "es", True),
    ("defence", "Mana", "mana", True),
    ("defence", "TotalEHP", "ehp", True),
    ("defence", "Armour", "armour", True),
    ("defence", "Evasion", "evasion", True),
    ("resist", "FireResist", "res_Fire", True),
    ("resist", "ColdResist", "res_Cold", True),
    ("resist", "LightningResist", "res_Lightning", True),
    ("resist", "ChaosResist", "res_Chaos", True),
    ("attributes", "Str", "Str", True),
    ("attributes", "Dex", "Dex", True),
    ("attributes", "Int", "Int", True),
    ("other", "SpiritUnreserved", "spiritFree", True),
    ("other", "EffectiveMovementSpeedMod", "moveSpeed", True),
]


def snapshot(engine, profile: MapProfile) -> dict:
    out = engine.what_if(config=profile.config())
    stats = {key: out.get(pob, 0.0) for _, pob, key, _ in STATS}
    for h in survivable_hits(engine, profile):
        stats[f"hit_{h.damage_type}"] = h.normal
    return stats


def _items(engine) -> dict[str, dict]:
    return {i["slot"]: i for i in engine.equipped_items() if i["slot"] in GEAR_SLOTS}


def versus(mine, mine_profile: MapProfile, ref, ref_profile: MapProfile) -> dict:
    a, b = snapshot(mine, mine_profile), snapshot(ref, ref_profile)
    rows = [{"group": g, "key": key, "mine": a[key], "ref": b[key], "higherBetter": hb} for g, _, key, hb in STATS]
    rows += [{"group": "hits", "key": f"hit_{t}", "mine": a[f"hit_{t}"], "ref": b[f"hit_{t}"], "higherBetter": True}
             for t in DAMAGE_TYPES]

    cfg = mine_profile.config()
    my_items, ref_items = _items(mine), _items(ref)
    slots, theirs = [], {}
    for slot in GEAR_SLOTS:
        m, r = my_items.get(slot), ref_items.get(slot)
        if not m and not r:
            continue
        row = {"slot": slot, "mine": m and {"name": m["name"], "rarity": m["rarity"]},
               "ref": r and {"name": r["name"], "rarity": r["rarity"]}, "swap": None, "error": None}
        if r:
            text = ref.item_text(slot)
            theirs[slot] = text
            try:
                row["swap"] = asdict(compare(mine, cfg, slot, text))
            except Exception as err:  # an item PoB cannot equip here (e.g. a weapon type the build cannot use)
                row["error"] = str(err)
        slots.append(row)

    all_gear = None
    if theirs:
        # their full gear at once: slots they leave empty are emptied too
        swap = {s: theirs.get(s) for s in set(theirs) | set(my_items)}
        with mine.swapped_items(swap):
            worn = snapshot(mine, mine_profile)
        all_gear = {k: worn[k] for k in worn}
    return {"mineSkill": mine.main_skill(), "refSkill": ref.main_skill(), "rows": rows, "slots": slots,
            "allGear": all_gear}
