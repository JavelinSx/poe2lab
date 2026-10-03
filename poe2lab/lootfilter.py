"""A loot filter block for the open build, put on top of the player's own filter.

PoE2 filters see an unidentified rare's base, class and item level, and an identified item's affix *names*
("of the Gorilla" is the fifth Strength tier), not its values. So the block marks, per gear slot of the build:
- identified items of the slot's class with several affixes that matter to this build, at their best tiers -
  "gold" (players identify promising bases in the inventory and drop them again: the filter re-checks them);
- unidentified rares of the build's own bases at an item level where those tiers roll - "identify";
- normal/magic items of those bases at that item level - "craft base";
- the build's unique items (by base: filters cannot match unique names);
- while levelling (areas below the maps' level): any item of the slot's class and defence type with the same
  mod families at the tiers that drop there, and unidentified rares of that class - uniques' slots included,
  since the unique is not there yet.
Which affixes matter comes from the slot plans (PoB what-ifs for the chosen goal); affix names from PoB's mod data.
Everything else is left to the player's filter below the block.

Two filters, one for each part of the game (the player switches at maps):
- levelling, the campaign below area level 65: the levelling rules above, the build's uniques, the weapon of the way
  the player levels with, the bases and uniques the build's author put into the levelling plan;
- maps, from 65: the build's items at their best tiers, its craft bases and uniques, what is worth a lot by
  poe.ninja (the market block), and the bases in demand - the kinds of gear most players wear rare (poe.ninja's
  ladder: rare boots on 90% of characters, a rare sceptre on a fifth), the best base of each defence kind (every
  jewellery base), white, at an item level every tier rolls at."""
import ctypes
import re
from dataclasses import dataclass, field
from pathlib import Path

from .analysis.slots import AFFIX_LIMIT, SKIP_TYPES, plan_slot
from .data.moddb import ModDB
from .itemcraft import ALL_BASES

TYPE_CLASS = {
    "Helmet": "Helmets", "Body Armour": "Body Armours", "Gloves": "Gloves", "Boots": "Boots", "Amulet": "Amulets",
    "Ring": "Rings", "Belt": "Belts", "Talisman": "Talismans", "Quiver": "Quivers", "Shield": "Shields",
    "Buckler": "Bucklers", "Focus": "Foci", "Bow": "Bows", "Crossbow": "Crossbows", "Spear": "Spears",
    "Sceptre": "Sceptres", "Wand": "Wands", "One Handed Mace": "One Hand Maces", "Two Handed Mace": "Two Hand Maces",
}
ARMOUR_TYPES = {"Helmet", "Body Armour", "Gloves", "Boots", "Shield"}
DEFENCE_CONDITIONS = {"str": "BaseArmour > 0", "dex": "BaseEvasion > 0", "int": "BaseEnergyShield > 0"}
MAX_ILVL = 82  # every tier rolls from here
TOP_TIERS = 3  # affix names counted per mod group: the best tiers the base can roll
GROUPS_PER_SLOT = 8  # mod groups that matter most for a slot
LEVELING_AREA = 65  # the campaign's areas are below this level, maps start at it
STAGES = ("all", "leveling", "maps")  # one filter for both, the campaign's, the maps'
# what poe.ninja's ladder calls a kind of gear ("Rare Boots") -> PoB's base type (a quarterstaff is a "Staff" too)
LADDER_KINDS = {"Ring": "Ring", "Amulet": "Amulet", "Belt": "Belt", "Boots": "Boots", "Gloves": "Gloves",
                "Helmet": "Helmet", "Body Armour": "Body Armour", "Shield": "Shield", "Focus": "Focus", "Quiver": "Quiver",
                "Sceptre": "Sceptre", "Wand": "Wand", "Staff": "Staff", "Quarterstaff": "Staff", "Bow": "Bow",
                "Crossbow": "Crossbow", "Spear": "Spear", "Talisman": "Talisman", "One Handed Mace": "One Hand Mace",
                "Two Handed Mace": "Two Hand Mace"}
DEMAND_SHARE = 5.0  # % of the ladder's characters wearing a rare of a kind: its end-game bases are sought after
DEMAND_ILVL = 82  # a white base from this item level rolls every tier
SPECIAL_TAGS = {"runeforged", "not_for_sale", "demigods"}  # bases that do not drop as plain white items
# the item classes of a way of levelling (poe2lab.analysis.leveling's weapons)
WAY_CLASSES = {"quarterstaff": ["Quarterstaves"], "mace": ["One Hand Maces", "Two Hand Maces"], "bow": ["Bows"],
               "crossbow": ["Crossbows"], "spear": ["Spears"], "talisman": ["Talismans"], "spell": ["Wands", "Staves"],
               "minion": ["Sceptres", "Wands"]}
BEGIN, END = "# ===== poe2lab: begin =====", "# ===== poe2lab: end ====="


@dataclass
class SlotRule:
    slot: str
    item_class: str | None
    base: str
    item_level: int  # craft/identify from this item level: the best wanted tiers roll there
    defence: list[str] = field(default_factory=list)  # filter conditions keeping the base's defence type
    affixes: list[str] = field(default_factory=list)  # affix names worth having on this slot
    mods: list[str] = field(default_factory=list)  # the matching mod lines (for the interface)
    unique: bool = False
    leveling: list[str] = field(default_factory=list)  # affix names of the same families that drop in the campaign


def item_class(item: dict) -> str | None:
    if item["type"] == "Staff":
        return "Quarterstaves" if "warstaff" in item["tags"] else "Staves"
    return TYPE_CLASS.get(item["type"])


def _defence(item: dict) -> list[str]:
    if item["type"] not in ARMOUR_TYPES:
        return []
    tag = next((t for t in item["tags"] if t.endswith("_armour") and t != "armour"), "")
    return [DEFENCE_CONDITIONS[k] for k in ("str", "dex", "int") if k in tag.removesuffix("_armour").split("_")]


def slot_rules(engine, db: ModDB, config: dict, mode: str, weights: dict) -> list[SlotRule]:
    """One rule per gear slot of the build, weapon sets included (a main skill may use the second set)."""
    by_lines = {}
    for m in db.mods:
        by_lines.setdefault(tuple(m.lines), m)
    by_id = {m.id: m for m in db.mods}
    rules = []
    for item in engine.equipped_item_details():
        if item["type"] in SKIP_TYPES:
            continue
        rule = SlotRule(item["slot"], item_class(item), item["baseName"], MAX_ILVL, _defence(item),
                        unique=item["rarity"] in ("UNIQUE", "RELIC"))
        rules.append(rule)
        if item["rarity"] not in AFFIX_LIMIT and not rule.unique:
            continue
        plan = plan_slot(engine, db, config, item, mode, weights, top=GROUPS_PER_SLOT)
        # the mod families that matter: affixes the item has that carry value, then the best it could roll.
        # A unique is matched by its base at maps; its slot still gets families for the rare worn while levelling.
        wanted = [] if rule.unique else [(by_lines.get(tuple(a.template)), a.score) for a in plan.affixes
                                         if a.score > 0.5]
        wanted += [(by_id.get(c.mod_id), c.score) for c in plan.candidates if c.score > 0.5]
        families, levels = [], []
        for mod, _ in sorted((w for w in wanted if w[0]), key=lambda w: -w[1]):
            key = (mod.group, mod.patterns)
            if key in families:
                continue
            families.append(key)
            every = db.tiers_of(mod, item["tags"])
            for m in every:
                if m.level < LEVELING_AREA and m.affix and m.affix not in rule.leveling:
                    rule.leveling.append(m.affix)
            if rule.unique:
                if len(families) >= GROUPS_PER_SLOT:
                    break
                continue
            tiers = [m for m in every if m.level <= MAX_ILVL][:TOP_TIERS]
            for m in tiers:
                if m.affix and m.affix not in rule.affixes:
                    rule.affixes.append(m.affix)
            if tiers:
                rule.mods.append(tiers[0].lines[0])
                levels.append(tiers[-1].level)  # the lowest kept tier: from this item level they can roll
            if len(families) >= GROUPS_PER_SLOT:
                break
        if levels:
            top = sorted(levels, reverse=True)[:3]  # the three most valuable families decide the item level
            rule.item_level = min(MAX_ILVL, max(top))
    return rules


def _quote(names) -> str:
    return " ".join('"' + n.replace('"', "") + '"' for n in names)


STYLES = {
    "gold": ["SetFontSize 45", "SetTextColor 255 255 255 255", "SetBorderColor 255 170 0 255",
             "SetBackgroundColor 120 50 0 255", "PlayAlertSound 1 300", "PlayEffect Orange", "MinimapIcon 0 Orange Star"],
    "good": ["SetFontSize 40", "SetTextColor 255 220 150 255", "SetBorderColor 255 170 0 255",
             "SetBackgroundColor 60 30 0 230", "PlayAlertSound 2 200", "MinimapIcon 1 Orange Diamond"],
    "identify": ["SetFontSize 38", "SetBorderColor 255 170 0 255", "MinimapIcon 2 Orange Circle"],
    "craft": ["SetFontSize 36", "SetBorderColor 150 200 255 255", "MinimapIcon 2 Blue Circle"],
    "unique": ["SetFontSize 42", "SetBorderColor 255 120 0 255", "PlayAlertSound 3 300", "MinimapIcon 1 Brown Star"],
    # the market block: priced by poe.ninja
    "market_top": ["SetFontSize 45", "SetTextColor 255 0 0 255", "SetBorderColor 255 0 0 255",
                   "SetBackgroundColor 255 255 255 255", "PlayAlertSound 6 300", "PlayEffect Red", "MinimapIcon 0 Red Star"],
    "market": ["SetFontSize 42", "SetTextColor 0 0 0 255", "SetBorderColor 0 0 0 255", "SetBackgroundColor 235 190 60 240",
               "PlayAlertSound 2 250", "PlayEffect Yellow", "MinimapIcon 1 Yellow Circle"],
    "market_maybe": ["SetFontSize 38", "SetBorderColor 235 190 60 255", "MinimapIcon 2 Yellow Diamond"],
    # a base many players craft on
    "demand": ["SetFontSize 38", "SetTextColor 200 255 245 255", "SetBorderColor 80 220 200 255", "MinimapIcon 2 Cyan Square"],
    # an unidentified rare on a base the top characters wear
    "top_rare": ["SetFontSize 38", "SetBorderColor 80 220 200 255", "MinimapIcon 2 Cyan Circle"],
    # levelling: a weapon to compare
    "weapon": ["SetFontSize 38", "SetBorderColor 220 220 220 255", "MinimapIcon 2 White Triangle"],
}


def _block(comment: str, conditions: list[str], style: str) -> str:
    return "\n".join([f"Show # poe2lab: {comment}", *("\t" + c for c in conditions), *("\t" + s for s in STYLES[style])])


_LEVELLED = re.compile(r"^(.+) \(Level (\d+)\)$")


def market_blocks(market: dict, top: float, low: float, valid: set | None = None) -> tuple[list[str], dict]:
    """Blocks for what is worth `top` and `low` divines or more by poe.ninja, and what went into them. Stackable items
    by name; "Uncut Skill Gem (Level 19)" by its base from the lowest level where it and every level above are worth
    it; uniques by base: a base whose every unique is worth it, and (softer) a base where one is worth `top`.
    `valid`: the game's base names - a name the game does not know would make it refuse the whole filter."""
    def tier(v):
        return "top" if v >= top else "low" if v >= low else None

    def known(name):
        return valid is None or name in valid

    names = {"top": [], "low": []}
    levelled = {}
    for name, x in market["items"].items():
        m = _LEVELLED.match(name)
        if m:
            if known(m.group(1)):
                levelled.setdefault(m.group(1), []).append((int(m.group(2)), x["div"]))
        elif tier(x["div"]) and known(name):
            names[tier(x["div"])].append((name, x["div"]))
    from_level = {"top": [], "low": []}
    for base, levels in levelled.items():
        levels.sort()
        for key, bar in (("top", top), ("low", low)):
            start = next((lvl for i, (lvl, _) in enumerate(levels) if all(v >= bar for _, v in levels[i:])), None)
            if start is not None and not (key == "low" and any(b == base for b, _, _ in from_level["top"])
                                          and start >= next(l for b, l, _ in from_level["top"] if b == base)):
                from_level[key].append((base, start, min(v for lvl, v in levels if lvl >= start)))
    by_base = {}
    for u in market["uniques"]:
        if known(u["base"]):
            by_base.setdefault(u["base"], []).append(u)
    unique_sure = {"top": [], "low": []}
    unique_maybe = []
    for base, us in by_base.items():
        cheapest, dearest = min(u["div"] for u in us), max(u["div"] for u in us)
        if tier(cheapest):
            unique_sure[tier(cheapest)].append((base, cheapest, [u["name"] for u in us]))
        elif dearest >= top:
            unique_maybe.append((base, dearest, [u["name"] for u in us if u["div"] >= top]))

    blocks = []
    for key, style, words in (("top", "market_top", "очень ценное"), ("low", "market", "ценное")):
        if names[key]:
            blocks.append(_block(f"рынок — {words}", [f"BaseType == {_quote(sorted(n for n, _ in names[key]))}"], style))
            blocks.append("")
        for base, level, _ in sorted(from_level[key]):
            blocks.append(_block(f"рынок — {words}: {base} от уровня {level}",
                                 [f'BaseType == "{base}"', f"ItemLevel >= {level}"], style))
            blocks.append("")
        if unique_sure[key]:
            blocks.append(_block(f"рынок — {words}: уники, у которых любой вариант на базе столько стоит",
                                 ["Rarity Unique", f"BaseType == {_quote(sorted(b for b, _, _ in unique_sure[key]))}"], style))
            blocks.append("")
    if unique_maybe:
        blocks.append(_block("рынок — уник на этой базе бывает очень ценным, проверь какой",
                             ["Rarity Unique", f"BaseType == {_quote(sorted(b for b, _, _ in unique_maybe))}"], "market_maybe"))
        blocks.append("")
    summary = {
        "top": sorted(names["top"], key=lambda x: -x[1]), "low": sorted(names["low"], key=lambda x: -x[1]),
        "levelled": {k: [{"base": b, "level": l, "div": v} for b, l, v in from_level[k]] for k in from_level},
        "uniques": {k: [{"base": b, "div": v, "names": n} for b, v, n in sorted(unique_sure[k], key=lambda x: -x[1])]
                    for k in unique_sure},
        "maybe": [{"base": b, "div": v, "names": n} for b, v, n in sorted(unique_maybe, key=lambda x: -x[1])],
    }
    return blocks, summary


def demand_bases(worn: dict[str, int], total: int, bases: list[dict], share: float = DEMAND_SHARE) -> list[dict]:
    """The kinds of gear many players wear rare (poe.ninja's ladder: {"Rare Boots": characters}) and the bases of each
    end-game items are made on: [{"kind", "share" (% of characters), "bases": [names]}], the most worn first."""
    out = []
    for kind, base_type in LADDER_KINDS.items():
        pct = worn.get(f"Rare {kind}", 0) / total * 100 if total else 0.0
        if pct < share:
            continue
        of = [b for b in bases if b["type"] == base_type and not b.get("hidden")]
        if base_type == "Staff":  # a quarterstaff and a caster's staff are both PoB's "Staff"
            of = [b for b in of if ("warstaff" in b.get("tags", [])) == (kind == "Quarterstaff")]
        names = _craft_bases(of)
        if names:
            out.append({"kind": kind, "share": round(pct, 1), "bases": names})
    return sorted(out, key=lambda d: -d["share"])


def kind_of_base(base: dict) -> str:
    """The ladder's name of a base's kind of gear ("Quarterstaff", "Body Armour"), PoB's type otherwise."""
    if base["type"] == "Staff":
        return "Quarterstaff" if "warstaff" in base.get("tags", []) else "Staff"
    return next((k for k, t in LADDER_KINDS.items() if t == base["type"]), base["type"])


def _craft_bases(bases: list[dict]) -> list[str]:
    """The bases of one kind of gear people craft on: of armour and weapons the best of each defence or sub-kind
    (its highest level - a lower one only has less of it), of jewellery every base (each has its own implicit);
    without the special ones that do not drop white."""
    bases = [b for b in bases if not SPECIAL_TAGS & set(b.get("tags", [])) and b["name"] != b["type"]]
    if bases and bases[0]["type"] in ALL_BASES:
        return sorted({b["name"] for b in bases})
    top: dict[str, int] = {}
    for b in bases:
        top[b.get("subType", "")] = max(top.get(b.get("subType", ""), 0), b["level"])
    return sorted({b["name"] for b in bases if b["level"] == top[b.get("subType", "")]})


def demand_blocks(demand: list[dict], valid: set | None = None, item_level: int = DEMAND_ILVL) -> list[str]:
    """A block per kind of gear in demand: its end-game bases, white, at an item level every tier rolls at."""
    blocks = []
    for d in demand:
        names = [n for n in d["bases"] if valid is None or n in valid]
        if names:
            blocks.append(_block(f"востребованная база: {d['kind']} (редкую носят {d['share']}% игроков) — белая, "
                                 f"уровень предмета {item_level}+", ["Rarity Normal", f"BaseType == {_quote(names)}",
                                                                      f"ItemLevel >= {item_level}"], "demand"))
            blocks.append("")
    return blocks


TOP_MIN = 2  # a base worn rare by at least this many of the ladder's top characters goes into the filter


def top_base_blocks(top: list[dict], valid: set | None = None, item_level: int = DEMAND_ILVL,
                    least: int = TOP_MIN) -> tuple[list[str], list[dict]]:
    """Blocks for the bases the ladder's top characters wear rare (ladder.top_bases): white and magic ones to craft
    on, unidentified rares to identify - from an item level every tier rolls at; and the bases that went in."""
    bases = [b for b in top if b["n"] >= least and (valid is None or b["base"] in valid)]
    names = [b["base"] for b in bases]
    if not names:
        return [], []
    blocks = [
        _block(f"база топ-игроков — белая или синяя под крафт, уровень предмета {item_level}+",
               ["Rarity Normal Magic", f"BaseType == {_quote(names)}", f"ItemLevel >= {item_level}"], "demand"), "",
        _block(f"база топ-игроков — редкая неопознанная, опознай", [
            "Identified False", "Rarity Rare", f"BaseType == {_quote(names)}", f"ItemLevel >= {item_level}"], "top_rare"), ""]
    return blocks, bases


def leveling_blocks(way_weapon: str | None, own_classes: set, plan_bases: list[str], plan_unique_bases: list[str],
                    valid: set | None = None) -> tuple[list[str], dict]:
    """The campaign's extra blocks: the weapon of the way the player levels with (when the build's own slots do not
    cover its class), the bases and the uniques' bases the build's author put into the levelling plan."""
    area = f"AreaLevel < {LEVELING_AREA}"
    known = lambda names: sorted({n for n in names if valid is None or n in valid})  # noqa: E731
    classes = [c for c in WAY_CLASSES.get(way_weapon or "", []) if c not in own_classes]
    bases, uniques = known(plan_bases), known(plan_unique_bases)
    blocks = []
    if classes:
        blocks += [_block("прокачка — оружие для способа прокачки: сравни урон", [
            area, "Rarity Magic Rare", f"Class == {_quote(classes)}"], "weapon"), ""]
    if bases:
        blocks += [_block("прокачка — базы из плана автора билда", [area, f"BaseType == {_quote(bases)}"], "craft"), ""]
    if uniques:
        blocks += [_block("прокачка — уники из плана автора билда (по базе)", [
            area, "Rarity Unique", f"BaseType == {_quote(uniques)}"], "unique"), ""]
    return blocks, {"weapons": classes, "bases": bases, "uniques": uniques}


def render(rules: list[SlotRule], build: str, market: list[str] | None = None, stage: str = "all",
           extra: list[str] | None = None) -> str:
    """The filter block: most specific first (a filter stops at the first matching block). `stage`: "leveling" -
    the campaign's rules and `extra` (leveling_blocks); "maps" - the build's items at their tiers, its uniques, the
    market and `extra` (demand_blocks) after it; "all" - both parts in one filter."""
    title = {"leveling": " — прокачка до 65", "maps": " — карты 65+", "all": ""}[stage]
    blocks = [BEGIN, f"# Билд: {build}{title}. Собрано poe2lab: вещи под этот билд поверх твоего фильтра.", ""]
    for kind, need, style in (("голда", 3, "gold"), ("хорошая вещь", 2, "good")) if stage != "leveling" else ():
        for r in rules:
            if not r.item_class or len(r.affixes) < need:
                continue
            blocks.append(_block(f"{r.slot} — {kind} для билда ({need}+ нужных аффикса)", [
                "Identified True", "Rarity Magic Rare" if need <= 2 else "Rarity Rare", f'Class == "{r.item_class}"',
                *r.defence, f"HasExplicitMod >={need} {_quote(r.affixes)}"], style))
            blocks.append("")
    # levelling: one set per item class and defence type (both rings share one), any base of it
    groups = {}
    for r in (rules if stage != "maps" else []):
        if r.item_class and r.leveling:
            g = groups.setdefault((r.item_class, tuple(r.defence)), {"slots": [], "affixes": []})
            g["slots"].append(r.slot)
            g["affixes"] += [a for a in r.leveling if a not in g["affixes"]]
    area = f"AreaLevel < {LEVELING_AREA}"
    for (cls, defence), g in groups.items():
        slots = ", ".join(g["slots"])
        for kind, need, rarity, style in (("голда", 3, "Rare", "gold"), ("хорошая вещь", 2, "Magic Rare", "good")):
            if len(g["affixes"]) >= need:
                blocks.append(_block(f"прокачка, {slots} — {kind} ({need}+ нужных аффикса)", [
                    area, "Identified True", f"Rarity {rarity}", f'Class == "{cls}"', *defence,
                    f"HasExplicitMod >={need} {_quote(g['affixes'])}"], style))
                blocks.append("")
        blocks.append(_block(f"прокачка, {slots} — редкая вещь класса билда, опознай", [
            area, "Identified False", "Rarity Rare", f'Class == "{cls}"', *defence], "identify"))
        blocks.append("")
    if stage == "leveling":
        blocks += extra or []
    bases = {}
    for r in (rules if stage != "leveling" else []):
        if not r.unique:
            bases.setdefault((r.base, r.item_level), []).append(r.slot)
    for (base, ilvl), slots in bases.items():
        blocks.append(_block(f"{', '.join(slots)} — база билда, опознай", [
            "Identified False", "Rarity Rare", f'BaseType == "{base}"', f"ItemLevel >= {ilvl}"], "identify"))
        blocks.append("")
        blocks.append(_block(f"{', '.join(slots)} — база под крафт", [
            "Rarity Normal Magic", f'BaseType == "{base}"', f"ItemLevel >= {ilvl}"], "craft"))
        blocks.append("")
    uniques = sorted({r.base for r in rules if r.unique})
    if uniques:
        blocks.append(_block("уникальные предметы билда (по базе)", ["Rarity Unique", f"BaseType == {_quote(uniques)}"],
                             "unique"))
        blocks.append("")
    if stage != "leveling":
        blocks += market or []
    if stage == "maps":
        blocks += extra or []
    blocks.append(END)
    return "\n".join(blocks) + "\n"


def merge(block: str, player_filter: str) -> str:
    """The block on top of the player's filter; an older poe2lab block in it is replaced, not stacked."""
    player_filter = re.sub(rf"{re.escape(BEGIN)}.*?{re.escape(END)}\n?", "", player_filter, flags=re.S)
    return block + "\n" + player_filter.lstrip("﻿")


def filters_dir() -> Path:
    """Where PoE2 reads local filters: Documents\\My Games\\Path of Exile 2 (Documents may be moved by OneDrive)."""
    docs = Path.home() / "Documents"
    try:
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:  # CSIDL_PERSONAL
            docs = Path(buf.value)
    except (AttributeError, OSError):
        pass
    return docs / "My Games" / "Path of Exile 2"


# a native "open file" dialog in the game's filter folder; run in its own process, since Tk wants the main thread
_PICK = r"""
import sys, tkinter
from tkinter import filedialog
root = tkinter.Tk()
root.withdraw()
root.attributes("-topmost", True)
path = filedialog.askopenfilename(parent=root, initialdir=sys.argv[1], title=sys.argv[2],
                                  filetypes=[(sys.argv[3], "*.filter"), (sys.argv[4], "*")])
sys.stdout.write(path or "")
"""


def pick_filter(title: str = "Фильтр, поверх которого добавить правила билда") -> Path | None:
    """Let the player choose a filter file in a Windows dialog opened in the game's filter folder."""
    import subprocess
    import sys
    folder = filters_dir()
    res = subprocess.run([sys.executable, "-c", _PICK, str(folder if folder.is_dir() else Path.home()), title,
                          "Лут-фильтр PoE2", "Все файлы (онлайн-фильтры — в OnlineFilters, без расширения)"],
                         capture_output=True, text=True, encoding="utf-8")
    path = res.stdout.strip()
    return Path(path) if path else None


def looks_like_filter(path: Path) -> bool:
    """A loot filter by its content: the game's copies of online filters have no extension."""
    try:
        with path.open(encoding="utf-8-sig", errors="replace") as f:
            head = f.read(200_000)
    except OSError:
        return False
    return bool(re.search(r"^\s*(Show|Hide|Minimal)\b", head, re.M))


def online_filters() -> list[dict]:
    """Online filters the player subscribes to (NeverSink, FilterBlade): the game keeps a copy of each in
    OnlineFilters, named by an id, with the filter's name in its header."""
    folder = filters_dir() / "OnlineFilters"
    out = []
    for path in sorted(folder.glob("*")) if folder.is_dir() else []:
        if not path.is_file():
            continue
        try:
            with path.open(encoding="utf-8-sig", errors="replace") as f:
                head = f.read(4000)
        except OSError:
            continue
        name = re.search(r"^#name:(.+)$", head, re.M)
        updated = re.search(r"^#lastUpdate:(\S+)", head, re.M)
        if name:
            out.append({"path": str(path), "name": name.group(1).strip(),
                        "updated": updated.group(1)[:10] if updated else None})
    return out


def is_online_copy(path: Path) -> bool:
    try:
        path.resolve().relative_to((filters_dir() / "OnlineFilters").resolve())
        return True
    except ValueError:
        return False


def local_filters() -> list[str]:
    d = filters_dir()
    return sorted(p.name for p in d.glob("*.filter")) if d.is_dir() else []


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', " ", name).strip() or "poe2lab"
