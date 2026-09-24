"""The game's own explanations of its terms - the popups it shows on hover (poe2lab.gamedata.KEYWORDS) - found in
the texts of skills, supports and unique items, so a mechanic is explained in the game's words, in the player's
language, instead of ours."""
import re

from . import gamedata, glossary

# Terms too common or not about mechanics: item classes, currencies, leagues and map content, basic stats. They
# stay in the glossary, but marking them in every line would bury the terms that explain something.
_STOP_NAMES = {
    "Axes", "Bows", "Foci", "Maces", "Wands", "Claws", "Daggers", "Flails", "Spears", "Staves", "Swords", "Quivers",
    "Shields", "Bucklers", "Sceptres", "Talismans", "Crossbows", "Quarterstaves", "Jewels", "Jewellery", "Charms",
    "Flasks", "Equipment", "Equipped", "Maximum", "Recently", "Quality", "Rarity", "Base Type", "Energy", "Power",
    "Limit", "Melee", "Attacks", "Spells", "Strength", "Dexterity", "Intelligence", "Attributes", "Minions", "Buffs",
    "Debuffs", "Pack", "Idol", "Jade", "Heat", "Allies", "Hit Damage", "Physical Damage", "Cold Damage",
    "Fire Damage", "Lightning Damage", "Chaos Damage", "Damage Types", "Elemental Damage Types", "Support Gems",
    "Meta Gems", "Evasion", "Armour", "Energy Shield", "Accuracy", "Resistances", "Spirit", "Reservation",
    "One-Handed", "Two-Handed", "Soul Core", "Augment", "Test", "Biome", "Oasis", "Wells", "Relics", "Tablets",
    "Breach", "Hideout", "Waystones", "Waypoints", "Difficulty", "Quest Item", "Account Bound", "Extra Content",
    "Bonus Reward", "Free Rerolls", "Room Upgrades", "Restricted Room", "Wandering Trader", "Corruption",
    "Item Armour", "Item Evasion", "Item Rarity", "Item Energy Shield", "Equippable Armours", "Martial Weapons",
    "Caster Weapons", "Mirrored Items", "Corrupted Items", "Sanctified Items", "Exceptional Item", "Unique Culture",
    "Small Passives", "Ascendancy Points", "Maximum Quality", "Maximum Item Level", "Stat Totals",
    "Adding to Stat Totals", "Crafted Modifiers", "Fractured Modifiers", "Desecrated Modifiers", "Bonded Modifiers",
    "Abyssal Modifiers", "Ancient Modifiers", "Orb of Alteration", "Artificer's Orb", "Default Attack",
    "Default Attack Damage", "Unarmed Damage", "Unarmed Attacks", "Dual Wielding", "Weapon Sets", "Expedition",
    "Attack", "Hit", "Hits", "Spell", "Skill", "Skills", "Damage", "Buff", "Debuff", "Life", "Mana", "Area",
}
_STOP_PATTERN = re.compile(r"Legacy of|Spirit Of The|Medallion|Rune$|Shrine|Strongbox|\bMap\b|Citadel|^Abyss|Monolith|"
                           r"Obelisk|Checkpoint|Essence|Delirium|Ritual|Temple|Precursor|Vaal Beacon|Invaded|City$|"
                           r"Landmark|Realmgate|DNT|Monster|Boss", re.I)
_LINK = re.compile(r"\[([^|\]]+)(?:\|([^\]]+))?\]")


def load(lang: str = "ru") -> dict[str, dict]:
    return gamedata.load_keywords(lang)


def plain(text: str) -> str:
    """"[Rage|свирепости]" -> "свирепости"."""
    return _LINK.sub(lambda m: m.group(2) or m.group(1), text or "")


def _vocabulary(keywords: dict) -> list[tuple[re.Pattern, str]]:
    """(pattern, id) for the terms worth marking, longest names first so "Heavy Stun" wins over "Stun"."""
    out = []
    for kid, k in keywords.items():
        name = k["name"]
        if kid.startswith("Monster") or name in _STOP_NAMES or _STOP_PATTERN.search(name):
            continue
        forms = {name, name[:-1]} if name.endswith("s") and len(name) > 5 else {name}
        alt = "|".join(re.escape(f) for f in sorted(forms, key=len, reverse=True))
        out.append((len(name), re.compile(rf"(?<![\w-])(?:{alt})(?![\w-])", re.I), kid))
    return [(p, kid) for _, p, kid in sorted(out, key=lambda x: -x[0])]


_cache: dict = {}


def find(texts, lang: str = "ru") -> list[str]:
    """Ids of the terms mentioned in the texts (English, as the game data and PoB write them), each once, in the
    order they appear; a longer term hides the shorter ones inside it."""
    keywords = load(lang)
    if not keywords:
        return []
    key = (lang, len(keywords))
    if key not in _cache:
        _cache.clear()
        _cache[key] = _vocabulary(keywords)
    text = " \n ".join(t for t in texts if t)
    taken, found = [], []
    for pattern, kid in _cache[key]:
        for m in pattern.finditer(text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append((m.start(), kid))
    seen, out = set(), []
    for _, kid in sorted(found):
        if kid not in seen:
            seen.add(kid)
            out.append(kid)
    return out


def entries(ids, lang: str = "ru") -> dict[str, dict]:
    """The terms by id, with the terms their texts link to, one level deep (the popup can open those too). Our own
    beginner's explanation (poe2lab.glossary) replaces the game's where we have one."""
    keywords = load(lang) | glossary.entries(lang)
    out = {}
    for kid in ids:
        k = keywords.get(kid)
        if not k:
            continue
        out[kid] = k
        for linked in _LINK.findall(k.get("textLocal") or k["text"]):
            if linked[0] in keywords and linked[0] not in out:
                out[linked[0]] = keywords[linked[0]]
    return out
