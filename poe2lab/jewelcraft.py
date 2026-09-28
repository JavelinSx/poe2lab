"""Jewels made the way the game makes them, for the tree's jewel sockets.

A base of one colour: Ruby (strength), Emerald (dexterity) or Sapphire (intelligence), or their Time-Lost kin with a
radius. Diamond, Time-Lost Diamond and Timeless jewels carry all three colours and come only as uniques.

A rarity. Magic has one prefix and one suffix at most, rare two and two: PoB's affix limit for jewels
(ItemClass:ParseRaw).

The mods its base can roll. These are PoB's jewel mods whose spawn weight on the base's tags is above zero.
Desecrated ones are included and take a prefix or suffix place like any other. No two come from one family (a mod
group). Each is rolled where the player puts it between its range's ends.

Optionally, the enchantment a corruption leaves: the corrupted "implicit" PoB keeps as an enchantment line.

Uniques come from PoB's list and are rolled the same way. The text this makes is the game's own copy format, so PoB
reads it like an item copied from the game."""

import re

MOD_SETS = ("Jewel", "Desecrated", "Corruption")
LIMITS = {"normal": (0, 0), "magic": (1, 1), "rare": (2, 2)}  # rarity -> (prefixes, suffixes)
COLOURS = ("str", "dex", "int")
RANGE = re.compile(r"\(-?[\d.]+--?[\d.]+\)")
RARE_TITLE = "Crafted Jewel"


class CraftError(ValueError):
    """A jewel the game would not make; the message is the player's (Russian)."""


def spawn_weight(mod: dict, tags: set[str]) -> int:
    """PoB's ItemClass:GetModSpawnWeight: the first of the mod's weight keys the base has decides."""
    for key, value in zip(mod["weightKey"], mod["weightVal"]):
        if key in tags:
            return value
    return 0


def _colours(tags: set[str]) -> list[str]:
    return [c for c in COLOURS if f"{c}jewel" in tags or f"{c}_radius_jewel" in tags]


def catalog(item_data: dict, uniques: list[dict]) -> dict:
    """The bases a jewel can be made on, each with the mods it rolls (and a corruption's enchantments), and the
    unique jewels: item_data is PobEngine.export_item_data(MOD_SETS), uniques PobEngine.unique_catalog()."""
    bases = []
    for b in item_data["bases"]:
        tags = set(b["tags"])
        colours = _colours(tags)
        if b["type"] != "Jewel" or len(colours) != 1:
            continue
        mods, corruption = [], []
        for m in item_data["mods"]:
            if spawn_weight(m, tags) > 0:
                entry = {k: m[k] for k in ("id", "set", "type", "affix", "lines", "level", "group")}
                (corruption if m["set"] == "Corruption" else mods).append(entry)
        mods.sort(key=lambda m: (m["type"], m["set"] != "Jewel", m["group"], m["level"]))
        corruption.sort(key=lambda m: m["lines"])
        bases.append({"name": b["name"], "colour": colours[0], "radius": b["subType"] == "Radius",
                      "mods": mods, "corruption": corruption})
    bases.sort(key=lambda b: (b["radius"], COLOURS.index(b["colour"])))
    jewels = sorted(({"name": u["name"], "base": u["base"], "lines": u["lines"], "level": u["level"], "raw": u["raw"],
                      "ranged": any(RANGE.search(line) for line in u["lines"])}
                     for u in uniques if u["type"] == "Jewel"), key=lambda u: (u["name"], u["base"]))
    return {"bases": bases, "uniques": jewels, "limits": LIMITS}


def _roll(value) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.5


def make(base: dict, rarity: str, picks: list[dict], corruption: dict | None, resolve) -> str:
    """The jewel's text: `base` one of catalog()["bases"], picks [{"id", "roll"}] (roll 0 is the low end of each
    range, 1 the high end), corruption {"id", "roll"} or None; resolve(pairs of (line, roll)) -> lines with the
    numbers (PobEngine.resolve_ranges). Raises CraftError on what the game would not allow."""
    if rarity not in LIMITS:
        raise CraftError(f"неизвестная редкость {rarity!r}")
    by_id = {m["id"]: m for m in base["mods"]}
    chosen = []
    for p in picks:
        m = by_id.get(p.get("id"))
        if m is None:
            raise CraftError(f"на {base['name']} такой мод не выпадает: {p.get('id')}")
        chosen.append((m, _roll(p.get("roll", 0.5))))
    for side, cap, word in zip(("Prefix", "Suffix"), LIMITS[rarity], ("префикс", "суффикс")):
        n = sum(1 for m, _ in chosen if m["type"] == side)
        if n > cap:
            raise CraftError(f"у {'магического' if rarity == 'magic' else 'редкого' if rarity == 'rare' else 'обычного'}"
                             f" самоцвета {word}ов не больше {cap}, выбрано {n}")
    groups = [m["group"] for m, _ in chosen]
    if len(set(groups)) != len(groups):
        raise CraftError("два мода одного семейства на одном предмете не бывают")
    chosen.sort(key=lambda c: c[0]["type"] != "Prefix")
    pairs = [(line, r) for m, r in chosen for line in m["lines"]]
    flags = ["{desecrated}" if m["set"] == "Desecrated" else "" for m, _ in chosen for _ in m["lines"]]
    enchant = None
    if corruption:
        c = next((m for m in base["corruption"] if m["id"] == corruption.get("id")), None)
        if c is None:
            raise CraftError(f"порча не даёт {base['name']} такого свойства: {corruption.get('id')}")
        enchant = [(line, _roll(corruption.get("roll", 0.5))) for line in c["lines"]]
    lines = resolve(pairs + (enchant or []))
    explicit = [f + line for f, line in zip(flags, lines[:len(pairs)])]
    if rarity == "magic":
        prefix = next((m["affix"] for m, _ in chosen if m["type"] == "Prefix"), "")
        suffix = next((m["affix"] for m, _ in chosen if m["type"] == "Suffix"), "")
        head = [" ".join(x for x in (prefix, base["name"], suffix) if x)]
    elif rarity == "rare":
        head = [RARE_TITLE, base["name"]]
    else:
        head = [base["name"]]
    text = [f"Rarity: {rarity.upper()}", *head]
    if base["radius"]:
        text.append("Radius: Small")  # PoB's crafted Time-Lost jewel; "Upgrades Radius to ..." mods widen it
    if enchant:
        text += [f"Implicits: {len(enchant)}", *("{enchant}" + line for line in lines[len(pairs):])]
    else:
        text.append("Implicits: 0")
    text += explicit
    if enchant:
        text.append("Corrupted")
    return "\n".join(text)


def rolled_unique(unique: dict, roll, resolve) -> str:
    """A unique jewel's text with each of its ranges where `roll` puts them (0: the low end, 1: the high end)."""
    r = _roll(roll)
    raw = unique["raw"].strip()
    if not raw.startswith("Rarity:"):  # PoB's unique data leaves the rarity to its reader
        raw = "Rarity: UNIQUE\n" + raw
    return "\n".join(resolve([(line, r) for line in raw.split("\n")]))


def limited_to(text: str) -> int | None:
    """A unique's "Limited to: N": no more than N of it socketed at once."""
    m = re.search(r"^Limited to: (\d+)", text, re.M)
    return int(m.group(1)) if m else None
