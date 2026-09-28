"""An item's quality as the game sets it: how high it goes, and a catalyst's quality on jewellery.

Weapons and armour take quality from currency. Their maximum comes from the item's own mods:
"Maximum Quality is N%" sets it (Breach rings, some uniques), "+N% to Maximum Quality" adds to the usual 20%
(Breach rings, the Breachlord's prefix). Items without such mods allow up to DEFAULT_MAX: the most PoB takes.

Rings and amulets take a catalyst's quality instead, and so does an item that says "Catalysts can be applied to this
item". A catalyst raises the values of one kind of mod by its quality in %: the kind is the catalyst's tags, listed
the way PoB's Item.lua lists them. The text of an item copied from the game already shows its current catalyst's
raise. So a new catalyst is applied to the values with the old one's raise taken out. That covers the lines PoB does
not scale itself: the ones with no {tags:}, which are the lines of items that came from the game."""
import re

from .data.moddb import ModDB

BASE_MAX = 20
DEFAULT_MAX = 30
# name (the game's "<name> Catalyst"; PoB's Catalyst: spec), the kind of mod, its tags - PoB's order (Item.lua)
CATALYSTS = [
    ("Flesh", "Life", ("life",)), ("Neural", "Mana", ("mana",)),
    ("Carapace", "Defence", ("defences", "armour", "evasion", "energyshield")),
    ("Uul-Netol's", "Physical", ("physical",)), ("Xoph's", "Fire", ("fire",)), ("Tul's", "Cold", ("cold",)),
    ("Esh's", "Lightning", ("lightning",)), ("Chayula's", "Chaos", ("chaos",)), ("Reaver", "Attack", ("attack",)),
    ("Sibilant", "Caster", ("caster",)), ("Skittering", "Speed", ("speed",)), ("Adaptive", "Attribute", ("attribute",)),
    ("Necrotic", "Minion", ("minion",)),
]
CATALYST_TYPES = ("Ring", "Amulet")
_OVERRIDE = re.compile(r"^Maximum Quality is (\d+)%", re.I)
_ADDED = re.compile(r"^\+(\d+)% to Maximum Quality", re.I)
_TAKES = "Catalysts can be applied to this item"
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_TOKENS = re.compile(r"^((?:\{[^}]*\})*)(.*)$")


def max_quality(lines: list[str], default: int = DEFAULT_MAX) -> int:
    """The item's maximum quality by its mods (lines: every mod line of the item)."""
    for line in lines:
        if m := _OVERRIDE.match(line):
            return int(m.group(1))
    added = sum(int(m.group(1)) for line in lines if (m := _ADDED.match(line)))
    return max(default, BASE_MAX + added) if added else default


def takes_catalyst(item_type: str, lines: list[str]) -> bool:
    return item_type in CATALYST_TYPES or any(line.startswith(_TAKES) for line in lines)


def catalyst_index(name: str) -> int:
    """PoB's number of a catalyst (1..13), 0 for none; ValueError for a name that is none of them."""
    if not name:
        return 0
    for i, (n, _, _) in enumerate(CATALYSTS, 1):
        if n == name:
            return i
    raise ValueError(name)


def _scaled(line: str, factor: float) -> str:
    def one(m):
        x = float(m.group(0)) * factor
        decimals = len(m.group(0).split(".")[1]) if "." in m.group(0) else 0
        return f"{x:.{decimals}f}" if decimals else str(round(x))
    return _NUMBER.sub(one, line)


def recatalyse(text: str, explicit: list[str], db: ModDB, base_tags, item_level: int,
               old: tuple[int, int], new: tuple[int, int]) -> str:
    """The item's text with a catalyst's raise moved: `old` and `new` are (catalyst number, quality). An explicit line
    of a mod the old catalyst raised loses its raise, one the new catalyst raises gets it. Lines PoB scales itself
    (with {tags:}) and lines with ranges are left to PoB."""
    def scale(tags, catalyst):
        index, quality = catalyst
        return 1 + quality / 100 if index and any(t in tags for t in CATALYSTS[index - 1][2]) else 1.0
    affixes, _ = db.identify(explicit, base_tags, item_level)
    factors = {}
    for a in affixes:
        f = scale(a.mod.tags, new) / scale(a.mod.tags, old)
        if abs(f - 1) > 1e-9:
            for line in a.rolled:
                factors[line] = f
    if not factors:
        return text
    out = []
    for raw in text.split("\n"):
        tokens, body = _TOKENS.match(raw).groups()
        if body in factors and "tags:" not in tokens and "(" not in body:
            raw = tokens + _scaled(body, factors[body])
        out.append(raw)
    return "\n".join(out)
