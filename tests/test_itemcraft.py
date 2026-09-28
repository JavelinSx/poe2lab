"""Gear made the way the game makes it: the base's mods by family and tier, the rarities' limits, the text PoB reads."""
import pytest

from poe2lab import itemcraft
from poe2lab.data.moddb import Mod


def mod(id_, type_, group, line, level, keys, set_="Item", affix=""):
    return Mod(id_, set_, type_, affix or id_, (line,), level, group, tuple(k for k, _ in keys), tuple(v for _, v in keys), (), ())


class DB:
    mods = [
        mod("Life1", "Prefix", "Life", "+(10-19) to maximum Life", 1, [("gloves", 1)], affix="Hale"),
        mod("Life7", "Prefix", "Life", "+(120-149) to maximum Life", 75, [("gloves", 1)]),
        mod("Armour1", "Prefix", "Armour", "(15-26)% increased Armour", 2, [("str_armour", 1), ("default", 0)]),
        mod("Mana1", "Prefix", "Mana", "+(10-19) to maximum Mana", 1, [("gloves", 1)]),
        mod("Fire1", "Suffix", "FireRes", "+(6-10)% to Fire Resistance", 1, [("gloves", 1)], affix="of the Whelpling"),
        mod("Cold1", "Suffix", "ColdRes", "+(6-10)% to Cold Resistance", 1, [("gloves", 1)]),
        mod("Wand1", "Suffix", "Spell", "(10-19)% increased Spell Damage", 1, [("wand", 1), ("default", 0)]),
        mod("Abyss", "Prefix", "AbyssLife", "+(20-30) to maximum Life", 1, [("gloves", 1)], set_="Desecrated"),
    ]


BASE = {"name": "Knightly Mitts", "tags": ["gloves", "str_armour", "armour", "default"], "implicit": "", "quality": 20}


def resolve(pairs):
    import re
    return [re.sub(r"\((\d+)-(\d+)\)", lambda m: str(round(int(m.group(1)) + r * (int(m.group(2)) - int(m.group(1))))), l)
            for l, r in pairs]


@pytest.fixture
def fams():
    return itemcraft.families(DB(), BASE["tags"], 70)


def test_the_base_s_families_with_tiers(fams):
    by = {f["group"]: f for f in fams}
    assert set(by) == {"Life", "Armour", "Mana", "FireRes", "ColdRes", "AbyssLife"}  # a wand's spell damage: no
    life = by["Life"]["tiers"]
    assert [(t["id"], t["tier"], t["open"]) for t in life] == [("Life7", 1, False), ("Life1", 2, True)]  # T1 needs ilvl 75


def test_a_rare_item_as_the_game_copies_it(fams):
    text = itemcraft.make(BASE, "rare", 70, [{"id": "Fire1", "roll": 1}, {"id": "Life1", "roll": 0}, {"id": "Abyss", "roll": 1}],
                          fams, 20, 0.5, resolve)
    assert text.split("\n") == ["Rarity: RARE", itemcraft.RARE_TITLE, "Knightly Mitts", "Item Level: 70", "Quality: 20",
                                "Implicits: 0", "+10 to maximum Life", "{desecrated}+30 to maximum Life",
                                "+10% to Fire Resistance"]
    magic = itemcraft.make(BASE, "magic", 70, [{"id": "Fire1"}, {"id": "Life1"}], fams, None, 0.5, resolve)
    assert magic.split("\n")[1] == "Hale Knightly Mitts of the Whelpling" and "Quality" not in magic


@pytest.mark.parametrize("rarity, picks, error", [
    ("rare", [{"id": "Life1"}, {"id": "Armour1"}, {"id": "Mana1"}, {"id": "Abyss"}], "префиксов не больше 3"),
    ("magic", [{"id": "Fire1"}, {"id": "Cold1"}], "суффиксов не больше 1"),
    ("rare", [{"id": "Life7"}], "уровня предмета"),
    ("rare", [{"id": "Wand1"}], "не выпадает"),
])
def test_what_the_game_would_not_make(fams, rarity, picks, error):
    with pytest.raises(itemcraft.CraftError, match=error):
        itemcraft.make(BASE, rarity, 70, picks, fams, None, 0.5, resolve)
