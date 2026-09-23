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
Everything else is left to the player's filter below the block."""
import ctypes
import re
from dataclasses import dataclass, field
from pathlib import Path

from .analysis.slots import AFFIX_LIMIT, SKIP_TYPES, plan_slot
from .data.moddb import ModDB

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
}


def _block(comment: str, conditions: list[str], style: str) -> str:
    return "\n".join([f"Show # poe2lab: {comment}", *("\t" + c for c in conditions), *("\t" + s for s in STYLES[style])])


def render(rules: list[SlotRule], build: str) -> str:
    """The filter block: most specific first (a filter stops at the first matching block)."""
    blocks = [BEGIN, f"# Билд: {build}. Собрано poe2lab: вещи под этот билд поверх твоего фильтра.", ""]
    for kind, need, style in (("голда", 3, "gold"), ("хорошая вещь", 2, "good")):
        for r in rules:
            if not r.item_class or len(r.affixes) < need:
                continue
            blocks.append(_block(f"{r.slot} — {kind} для билда ({need}+ нужных аффикса)", [
                "Identified True", "Rarity Magic Rare" if need <= 2 else "Rarity Rare", f'Class == "{r.item_class}"',
                *r.defence, f"HasExplicitMod >={need} {_quote(r.affixes)}"], style))
            blocks.append("")
    # levelling: one set per item class and defence type (both rings share one), any base of it
    groups = {}
    for r in rules:
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
    bases = {}
    for r in rules:
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
