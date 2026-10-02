"""What matters in a gear slot for this build - the answer to "which stats on my staff (gloves, boots...) are
best, and is the unique a must?", worked out by PoB on the build itself.

- Every mod the slot's base rolls, priced alone: its best tier the item level allows, at the middle of its range,
  on an otherwise empty rare of an end-game base of the same kind as the worn item - what that mod gives the build
  in damage and effective life (a mod of no worth to this build shows as such: accuracy it has enough of).
- The best item made of them: three prefixes and three suffixes picked one by one (each pick counted with the ones
  before - a capped resistance stops paying), for damage and balanced (damage plus effective life); against the
  worn item. The worn item a unique: whether a rare beats it, and by how much.

- Each mod in context: what it is worth inside that good item, not on an empty one.
- Why, from the build itself: what the main skill's hit is made of, the links PoB counts between stats (damage
  gained as another type, evasion granting deflection) with where each comes from, the character's defences; and
  the kinds of mod the slot pays for most - "the hit is 77% cold and its cold comes from the staff's physical: the
  staff's physical damage first".

Middle rolls of the top tiers: a good item that can drop, not a perfect one; the mods of a family (one per item) and
the sides (three each) as the game allows (poe2lab.itemcraft)."""
import re
from contextlib import nullcontext

from .. import itemcraft
from .explain import DEFENCE_MIN, _grouped, hit_shares
from .gradients import metric_changes

ITEM_LEVEL = 82
ROLL = 0.5
POOL = 14  # the mods worth most alone, the best item is picked from
MODES = {"damage": lambda d, e: d, "balanced": lambda d, e: d + e}
# what the game makes much of that PoB does not count in damage or effective life
PLAY = re.compile(r"movement speed", re.I)
# PoB's links between stats: damage gained as or converted to another type, evasion or armour granting deflection,
# life as energy shield
LINKS = ("GainAs", "ConvertTo")
_LINK = re.compile(r"^(?:Skill)?(?P<src>[A-Za-z]*?)(?:Damage)?(?:Skill)?(?P<how>GainAs|ConvertTo)(?P<dst>[A-Za-z]+)$")
DEFENCES = ("Life", "EnergyShield", "Evasion", "Armour")
# the kinds of mod, the first that matches a mod's lines (PoB's English wording)
KINDS = [("gems", r"to Level of all"), ("crit", r"Critical"), ("speed", r"Attack Speed|Cast Speed"),
         ("resist", r"Resistance"), ("deflect", r"Deflect"), ("evasion", r"Evasion"), ("armour", r"Armour"),
         ("es", r"Energy Shield"), ("life", r"maximum Life"), ("mana", r"Mana"), ("phys", r"Physical Damage"),
         ("elemental", r"(Fire|Cold|Lightning|Elemental) Damage"), ("chaos", r"Chaos Damage"),
         ("accuracy", r"Accuracy"), ("attributes", r"Strength|Dexterity|Intelligence|all Attributes")]
KINDS = [(k, re.compile(rx)) for k, rx in KINDS]
WHY_TOP = 3  # kinds of mod the slot's why names


def mod_lines(text: str) -> list[str]:
    """The mod lines of an item text made by itemcraft.make: after its "Implicits: N" line and the N implicits."""
    lines = [l for l in text.splitlines() if l.strip()]
    i = next((k for k, l in enumerate(lines) if l.startswith("Implicits:")), None)
    if i is None:
        return []
    return lines[i + 1 + int(lines[i].split(":")[1]):]


def pick_base(bases: list[dict], worn: dict | None) -> dict | None:
    """The base the advice is made on: the highest end-game base of the worn item's kind (its type and defence
    type), else of the worn base itself, else the highest the slot takes. Rune-forged bases are left out (they
    exist to take more runes, not as a plain base)."""
    plain = [b for b in bases if not b["name"].startswith(("Rune", "Runeforged", "Runemastered"))] or bases
    if worn:
        same = [b for b in plain if b["type"] == worn.get("type") and b["subType"] == worn.get("subType")]
        if same:
            return max(same, key=lambda b: b["level"])
        own = next((b for b in bases if b["name"] == worn.get("base")), None)
        if own:
            return own
    return max(plain, key=lambda b: b["level"], default=None)


def kind_of(lines) -> str:
    text = " / ".join(lines)
    return next((k for k, rx in KINDS if rx.search(text)), "other")


def facts(engine, config: dict, main_socket_group: int | None = None) -> dict:
    """What the build is made of, for the why of a slot: the main skill and what its hit is made of (% by damage
    type), its crit chance, the links PoB counts between stats (each with its total and where it comes from) and the
    character's defences."""
    with engine.main_skill_of(main_socket_group) if main_socket_group is not None else nullcontext():
        o = engine.what_if(config=config)
        names = engine.stat_names(LINKS)
        src = engine.stat_sources(names) if names else {"stats": {}}
    links = []
    for name, per in src["stats"].items():
        m = _LINK.match(name)
        rows = [r for r in per.get("BASE", []) if r["value"]]
        if not m or not rows:
            continue
        links.append({"stat": name, "from": m["src"] or "All", "how": "gain" if m["how"] == "GainAs" else "convert",
                      "to": m["dst"], "value": sum(r["value"] for r in rows),
                      "sources": [{k: g[k] for k in ("kind", "name", "small", "value", "count")} for g in _grouped(rows)]})
    return {"skill": src.get("skill"), "hit": hit_shares(o), "crit": o.get("CritChance", 0.0),
            "links": sorted(links, key=lambda l: -l["value"]),
            "defences": {d: o.get(d, 0.0) for d in DEFENCES if o.get(d, 0.0) >= DEFENCE_MIN},
            "deflection": o.get("DeflectChance", 0.0)}


def why_of(mods: list[dict]) -> list[dict]:
    """The kinds of mod the slot pays for most (each by its best mod in the good item), best first."""
    best = {}
    for m in mods:
        k = kind_of(m["lines"])
        if k != "other" and m["dps"] + m["ehp"] >= 1 and (k not in best or m["dps"] + m["ehp"] > best[k]["value"]):
            best[k] = {"kind": k, "value": m["dps"] + m["ehp"], "dps": m["dps"], "ehp": m["ehp"], "lines": m["lines"]}
    return sorted(best.values(), key=lambda b: -b["value"])[:WHY_TOP]


def advise(engine, db, config: dict, slot: str, bases: list[dict], worn: dict | None,
           main_socket_group: int | None = None, level: int | None = None) -> dict:
    """The slot's mods priced for this build and the best items made of them (see the module's note).
    `worn`: the equipped item's base, type, subType and rarity (PobEngine.equipped_bases), None for an empty slot;
    `main_socket_group`: the skill whose damage counts (the build's main one by default); `level`: a character's
    level - the bases it can wear and the tiers an item found at its level rolls (the end game without it)."""
    item_level = min(ITEM_LEVEL, level) if level else ITEM_LEVEL
    if level:
        bases = [b for b in bases if b["level"] <= level]
    base = pick_base(bases, worn)
    if base is None:
        return {"slot": slot, "base": None, "mods": [], "best": {}, "why": [], "facts": None}
    fams = [f for f in itemcraft.families(db, base["tags"], item_level) if f["set"] == "Item"]
    now = engine.what_if(config=config, main_socket_group=main_socket_group)
    quality = 20 if base.get("quality") else None

    def text_of(picks: list[str]) -> str:
        return itemcraft.make(base, "rare", item_level, [{"id": i, "roll": ROLL} for i in picks], fams, quality, ROLL,
                              engine.resolve_ranges)

    def measure(picks: list[str]) -> dict:
        return metric_changes(engine.what_if(config=config, replace_item=(slot, text_of(picks)),
                                             main_socket_group=main_socket_group), now)

    empty = measure([])
    mods = []
    for f in fams:
        top = next((t for t in f["tiers"] if t["open"]), None)
        if top is None:
            continue
        try:
            c = measure([top["id"]])
        except itemcraft.CraftError:
            continue
        mods.append({"id": top["id"], "type": f["type"], "group": f["group"], "tier": top["tier"],
                     "lines": top["lines"], "dps": c["dps"] - empty["dps"], "ehp": c["ehp"] - empty["ehp"]})
    group_of = {m["id"]: m["group"] for m in mods}
    best = {}
    for mode, score in MODES.items():
        pool = sorted(mods, key=lambda m: -score(m["dps"], m["ehp"]))[:POOL]
        picks, sides = [], {"Prefix": 0, "Suffix": 0}
        for _ in range(6):
            found = None
            for m in pool:
                if (m["id"] in picks or sides[m["type"]] >= 3
                        or any(group_of[p] == m["group"] for p in picks)):
                    continue
                c = measure(picks + [m["id"]])
                if found is None or score(c["dps"], c["ehp"]) > score(found[1]["dps"], found[1]["ehp"]):
                    found = (m, c)
            if found is None or (picks and score(found[1]["dps"], found[1]["ehp"]) <= score(best_c["dps"], best_c["ehp"])):
                break
            picks.append(found[0]["id"])
            sides[found[0]["type"]] += 1
            best_c = found[1]
        if picks and not any(sorted(b["picks"]) == sorted(picks) for b in best.values()):
            text = text_of(picks)
            best[mode] = {"text": text, "lines": mod_lines(text), "picks": picks, "dps": best_c["dps"], "ehp": best_c["ehp"]}
    if "damage" in best and "balanced" in best and best["damage"]["dps"] < 0.5:
        del best["damage"]  # the slot gives this build no damage: the balanced item says it all
    # each mod in context: what it is worth inside the good item, not on an empty one (where a weapon's damage is
    # its own physical only, and a local "% increased Physical Damage" looks bigger than it is in a real item) -
    # a mod of the item by what the item loses without it, another by what it gives in place of the item's weakest
    # mod of its side
    ref = next(iter(best.values()), None)
    if ref:
        ref_c = measure(ref["picks"])
        alone = {m["id"]: m["dps"] + m["ehp"] for m in mods}
        for m in mods:
            m["aloneDps"], m["aloneEhp"] = m["dps"], m["ehp"]
            if m["id"] in ref["picks"]:
                c = measure([p for p in ref["picks"] if p != m["id"]])
                m["dps"], m["ehp"] = ref_c["dps"] - c["dps"], ref_c["ehp"] - c["ehp"]
                continue
            side = [p for p in ref["picks"] if next(x for x in mods if x["id"] == p)["type"] == m["type"]]
            rest_ = [p for p in ref["picks"] if group_of[p] != m["group"]]
            if len(side) >= 3:
                weakest = min(side, key=lambda p: alone[p])
                rest_ = [p for p in rest_ if p != weakest]
            try:
                c = measure(rest_ + [m["id"]])
            except itemcraft.CraftError:
                continue
            m["dps"], m["ehp"] = c["dps"] - ref_c["dps"], c["ehp"] - ref_c["ehp"]
    mods.sort(key=lambda m: -(m["dps"] + m["ehp"]))
    counted = [m for m in mods if abs(m["dps"]) >= 0.1 or abs(m["ehp"]) >= 0.1]
    rest = [" / ".join(m["lines"]) for m in mods if m not in counted]
    return {"slot": slot, "base": base["name"], "itemLevel": item_level, "forLevel": level, "worn": worn,
            "uniqueWorn": bool(worn and worn.get("rarity") == "UNIQUE"), "empty": empty, "mods": counted,
            "inItem": ref is not None,
            # nothing to this build's damage or effective life by PoB; movement speed and the like are the game's
            "play": sorted({l for l in rest if PLAY.search(l)}), "useless": sorted({l for l in rest if not PLAY.search(l)}),
            "best": best, "why": why_of(counted), "facts": facts(engine, config, main_socket_group)}
