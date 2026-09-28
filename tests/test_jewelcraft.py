"""Jewels made the way the game makes them: which bases, which mods, the rarities' limits, the text PoB reads."""
import pytest

from poe2lab import jewelcraft


def mod(id_, type_, group, lines, keys, set_="Jewel", affix=""):
    return {"id": id_, "set": set_, "type": type_, "affix": affix or id_, "lines": lines, "level": 1, "group": group,
            "weightKey": [k for k, _ in keys], "weightVal": [v for _, v in keys], "tags": [], "tradeHashes": []}


DATA = {
    "bases": [
        {"name": "Ruby", "type": "Jewel", "subType": "", "tags": ["default", "strjewel", "jewel"]},
        {"name": "Sapphire", "type": "Jewel", "subType": "", "tags": ["default", "intjewel", "jewel"]},
        {"name": "Diamond", "type": "Jewel", "subType": "", "tags": ["default", "strjewel", "dexjewel", "intjewel", "jewel"]},
        {"name": "Time-Lost Ruby", "type": "Jewel", "subType": "Radius",
         "tags": ["default", "radius_jewel", "str_radius_jewel", "jewel"]},
        {"name": "Iron Ring", "type": "Ring", "subType": "", "tags": ["ring", "default"]},
    ],
    "mods": [
        mod("Armour", "Prefix", "Armour", ["(10-20)% increased Armour"], [("strjewel", 1), ("jewel", 0)], affix="Plated"),
        mod("Armour2", "Prefix", "Armour", ["(21-30)% increased Armour"], [("strjewel", 1), ("jewel", 0)]),
        mod("Area", "Prefix", "Area", ["(4-6)% increased Area of Effect"], [("strjewel", 1), ("intjewel", 1), ("jewel", 0)]),
        mod("Life", "Prefix", "Life", ["(2-4)% increased maximum Life"], [("strjewel", 1), ("jewel", 0)]),
        mod("Stun", "Suffix", "Stun", ["(5-10)% increased Stun Buildup"], [("strjewel", 1), ("jewel", 0)], affix="of Stunning"),
        mod("Cast", "Suffix", "Cast", ["(2-4)% increased Cast Speed"], [("intjewel", 1), ("jewel", 0)]),
        mod("Wide", "Prefix", "Radius", ["Upgrades Radius to Large"], [("str_radius_jewel", 1), ("jewel", 0)]),
        mod("Abyss", "Prefix", "AbyssHybrid", ["(4-8)% increased Chaos Damage", "(3-6)% increased Withered Magnitude"],
            [("strjewel", 1), ("intjewel", 1)], set_="Desecrated"),
        mod("Str", "Corrupted", "Str", ["+(4-6) to Strength"], [("jewel", 1)], set_="Corruption"),
    ],
}
UNIQUES = [
    {"name": "The Adorned", "base": "Diamond", "type": "Jewel", "level": 0, "raw": "The Adorned\nDiamond\nLimited to: 1\n"
     "(50-150)% increased Effect of Jewel Socket Passive Skills", "lines": ["(50-150)% increased Effect of Jewel Socket Passive Skills"]},
    {"name": "Ventor's Gamble", "base": "Gold Ring", "type": "Ring", "level": 0, "raw": "", "lines": []},
]


def resolve(pairs):
    """PobEngine.resolve_ranges, simplified: each range at its roll, rounded."""
    out = []
    for line, r in pairs:
        out.append(jewelcraft.RANGE.sub(lambda m: str(round(float(m.group(0)[1:-1].split("-")[0]) + r * (
            float(m.group(0)[1:-1].split("-")[1]) - float(m.group(0)[1:-1].split("-")[0])))), line))
    return out


@pytest.fixture(scope="module")
def cat():
    return jewelcraft.catalog(DATA, UNIQUES)


def base(cat, name):
    return next(b for b in cat["bases"] if b["name"] == name)


def test_one_colour_bases_only_the_rest_are_uniques(cat):
    assert [b["name"] for b in cat["bases"]] == ["Ruby", "Sapphire", "Time-Lost Ruby"]
    assert base(cat, "Time-Lost Ruby")["radius"] and base(cat, "Ruby")["colour"] == "str"
    assert [u["name"] for u in cat["uniques"]] == ["The Adorned"] and cat["uniques"][0]["ranged"]


def test_each_base_rolls_its_own_mods(cat):
    ruby = {m["id"] for m in base(cat, "Ruby")["mods"]}
    assert ruby == {"Armour", "Armour2", "Area", "Life", "Stun", "Abyss"}  # a radius mod, a Sapphire's cast speed: no
    assert {m["id"] for m in base(cat, "Sapphire")["mods"]} == {"Area", "Cast", "Abyss"}
    assert {m["id"] for m in base(cat, "Time-Lost Ruby")["mods"]} == {"Wide"}
    assert [m["id"] for m in base(cat, "Ruby")["corruption"]] == ["Str"]


def test_a_rare_jewel_as_the_game_copies_it(cat):
    text = jewelcraft.make(base(cat, "Ruby"), "rare",
                           [{"id": "Stun", "roll": 1}, {"id": "Armour", "roll": 0}, {"id": "Abyss", "roll": 0.5}],
                           {"id": "Str", "roll": 1}, resolve)
    assert text.split("\n") == [
        "Rarity: RARE", jewelcraft.RARE_TITLE, "Ruby", "Implicits: 1", "{enchant}+6 to Strength",
        "10% increased Armour", "{desecrated}6% increased Chaos Damage", "{desecrated}4% increased Withered Magnitude",
        "10% increased Stun Buildup", "Corrupted"]


def test_a_magic_jewel_is_named_by_its_affixes(cat):
    text = jewelcraft.make(base(cat, "Ruby"), "magic", [{"id": "Stun"}, {"id": "Armour"}], None, resolve)
    assert text.split("\n")[:3] == ["Rarity: MAGIC", "Plated Ruby of Stunning", "Implicits: 0"]


def test_a_time_lost_jewel_has_its_radius(cat):
    text = jewelcraft.make(base(cat, "Time-Lost Ruby"), "rare", [{"id": "Wide"}], None, resolve)
    assert "Radius: Small" in text and "Upgrades Radius to Large" in text


@pytest.mark.parametrize("rarity, picks, error", [
    ("magic", [{"id": "Armour"}, {"id": "Life"}], "префиксов не больше 1"),
    ("rare", [{"id": "Armour"}, {"id": "Life"}, {"id": "Area"}], "префиксов не больше 2"),
    ("rare", [{"id": "Armour"}, {"id": "Armour2"}], "одного семейства"),
    ("rare", [{"id": "Cast"}], "не выпадает"),  # a Sapphire's mod on a Ruby
    ("normal", [{"id": "Stun"}], "суффиксов не больше 0"),
    ("unique", [], "неизвестная редкость"),
])
def test_what_the_game_would_not_make(cat, rarity, picks, error):
    with pytest.raises(jewelcraft.CraftError, match=error):
        jewelcraft.make(base(cat, "Ruby"), rarity, picks, None, resolve)


def test_a_corruption_the_base_cannot_get(cat):
    with pytest.raises(jewelcraft.CraftError, match="порча"):
        jewelcraft.make(base(cat, "Ruby"), "rare", [], {"id": "Armour"}, resolve)


def test_a_unique_rolled_and_its_limit(cat):
    text = jewelcraft.rolled_unique(cat["uniques"][0], 1, resolve)
    assert text.startswith("Rarity: UNIQUE\nThe Adorned\nDiamond")
    assert "150% increased Effect of Jewel Socket Passive Skills" in text
    assert jewelcraft.limited_to(text) == 1 and jewelcraft.limited_to("Rarity: RARE\nRuby") is None
