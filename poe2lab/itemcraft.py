"""Gear made the way the game makes it, to try on in a slot and see what it does for the build.

The base must be one the slot takes (PoB's own rule). The rarity sets how many mods it has: magic takes one prefix
and one suffix at most, rare three and three. The mods are the ones that base rolls at the item level: PoB's gear
affixes whose spawn weight on the base's tags is above zero, desecrated ones included.

Each mod belongs to a family (its mod group), and no two mods of one family go on one item. Each family has tiers:
T1 is the best that rolls on the base, and a tier above the item level does not roll. Each mod is rolled where the
player puts it between its range's ends. Quality works as on any other item (poe2lab.quality).

The text this makes is the game's own copy format, so PoB reads it like an item copied from the game."""

from .data.moddb import ModDB

LIMITS = {"normal": (0, 0), "magic": (1, 1), "rare": (3, 3)}  # rarity -> (prefixes, suffixes)
DEFAULT_ITEM_LEVEL = 82
# the item levels an end-game item is made at, lowest and highest: from 65 (the end game's first maps); every best
# tier (T1) rolls from 82, on jewellery too (PoB's data: a ring's best life, resistances and attributes want 81-82)
ITEM_LEVELS = (65, 82)
ENDGAME_BASE = 65  # an armour's or weapon's base from this level (the expert tier) - or its type's best
ALL_BASES = ("Ring", "Amulet", "Belt", "Quiver", "Jewel", "Flask", "Charm")  # none above 64: each for its implicit
RARE_TITLE = "Crafted Item"
SETS = ("Item", "Desecrated")


class CraftError(ValueError):
    """An item the game would not make; the message is the player's (Russian)."""


def families(db: ModDB, base_tags, item_level: int) -> list[dict]:
    """The mod families the base rolls: each with its tiers, best (T1) first, and whether the item level lets it roll."""
    tags = set(base_tags)
    found: dict[tuple, list] = {}
    for m in db.mods:
        if m.set in SETS and m.weight_for(tags) > 0:
            found.setdefault((m.set, m.group, m.patterns), []).append(m)
    out = []
    for (set_, group, _), mods in found.items():
        mods.sort(key=lambda m: -m.level)
        out.append({"set": set_, "type": mods[0].type, "group": group,
                    "tiers": [{"id": m.id, "tier": i + 1, "level": m.level, "affix": m.affix, "lines": list(m.lines),
                               "open": m.level <= item_level} for i, m in enumerate(mods)]})
    out.sort(key=lambda f: (f["type"], f["set"] != "Item", f["tiers"][-1]["lines"]))
    return out


def endgame_bases(bases: list[dict]) -> list[dict]:
    """The bases an end-game item is made on. For armour and weapons: the expert tier (a base from level 65) or the
    best level of its type (sceptres stop at 65), since a lower base of the same defence or weapon only has less of
    it; the few low bases of no defence type are for uniques (they stay in the uniques' list). Jewellery and quivers:
    every base - none goes above level 64, and each has its own implicit."""
    top: dict[str, int] = {}
    for b in bases:
        top[b["type"]] = max(top.get(b["type"], 0), b["level"])
    return [b for b in bases if b["type"] in ALL_BASES or b["level"] >= min(ENDGAME_BASE, top[b["type"]])]


def _roll(value) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.5


def make(base: dict, rarity: str, item_level: int, picks: list[dict], fams: list[dict], quality: int | None,
         implicit_roll: float, resolve) -> str:
    """The item's text: `base` as PobEngine.export_item_data lists bases, picks [{"id": a tier's id, "roll"}] from
    `fams` (families(...) of the base), quality None when the base takes none; resolve(pairs of (line, roll)) ->
    lines with the numbers (PobEngine.resolve_ranges). Raises CraftError on what the game would not make."""
    if rarity not in LIMITS:
        raise CraftError(f"неизвестная редкость {rarity!r}")
    if not 1 <= item_level <= 100:
        raise CraftError("уровень предмета — от 1 до 100")
    tiers = {t["id"]: (f, t) for f in fams for t in f["tiers"]}
    chosen = []
    for p in picks:
        if p.get("id") not in tiers:
            raise CraftError(f"на {base['name']} такой мод не выпадает: {p.get('id')}")
        f, t = tiers[p["id"]]
        if not t["open"]:
            raise CraftError(f"тир {t['tier']} этого мода выпадает с {t['level']} уровня предмета, а у этого — {item_level}")
        chosen.append((f, t, _roll(p.get("roll", 0.5))))
    for side, cap, word in zip(("Prefix", "Suffix"), LIMITS[rarity], ("префикс", "суффикс")):
        n = sum(1 for f, _, _ in chosen if f["type"] == side)
        if n > cap:
            kind = {"magic": "магического", "rare": "редкого", "normal": "обычного"}[rarity]
            raise CraftError(f"у {kind} предмета {word}ов не больше {cap}, выбрано {n}")
    groups = [f["group"] for f, _, _ in chosen]
    if len(set(groups)) != len(groups):
        raise CraftError("два мода одного семейства на одном предмете не бывают")
    chosen.sort(key=lambda c: c[0]["type"] != "Prefix")
    implicit = [l for l in (base.get("implicit") or "").split("\n") if l.strip()]
    pairs = [(l, _roll(implicit_roll)) for l in implicit] + [(l, r) for _, t, r in chosen for l in t["lines"]]
    lines = resolve(pairs) if pairs else []
    flags = ["{desecrated}" if f["set"] == "Desecrated" else "" for f, t, _ in chosen for _ in t["lines"]]
    if rarity == "magic":
        prefix = next((t["affix"] for f, t, _ in chosen if f["type"] == "Prefix"), "")
        suffix = next((t["affix"] for f, t, _ in chosen if f["type"] == "Suffix"), "")
        head = [" ".join(x for x in (prefix, base["name"], suffix) if x)]
    elif rarity == "rare":
        head = [RARE_TITLE, base["name"]]
    else:
        head = [base["name"]]
    text = [f"Rarity: {rarity.upper()}", *head, f"Item Level: {item_level}"]
    if quality is not None:
        text.append(f"Quality: {int(quality)}")
    text.append(f"Implicits: {len(implicit)}")
    text += lines[:len(implicit)]
    text += [f + l for f, l in zip(flags, lines[len(implicit):])]
    return "\n".join(text)
