"""An item's maximum quality by its mods, and a catalyst's raise moved from one kind of mod to another."""
import pytest

from poe2lab import quality
from poe2lab.data.moddb import Affix, Mod


def test_maximum_quality_by_the_item_s_mods():
    assert quality.max_quality([]) == quality.DEFAULT_MAX
    assert quality.max_quality(["Maximum Quality is 40%"]) == 40  # Breach rings, some uniques
    assert quality.max_quality(["Maximum Quality is 200%", "+20% to Maximum Quality"]) == 200  # it sets, not adds
    assert quality.max_quality(["+20% to Maximum Quality"]) == 40  # on top of the usual 20%
    assert quality.max_quality(["+25% to Maximum Quality"]) == 45


def test_which_items_take_a_catalyst():
    assert quality.takes_catalyst("Ring", []) and quality.takes_catalyst("Amulet", [])
    assert not quality.takes_catalyst("Belt", [])
    assert quality.takes_catalyst("Belt", ["Catalysts can be applied to this item"])
    assert quality.catalyst_index("") == 0 and quality.catalyst_index("Flesh") == 1
    with pytest.raises(ValueError):
        quality.catalyst_index("Gold")


def mod(line, tags):
    return Mod(line, "Item", "Prefix", "", (line,), 1, line, (), (), tags, ())


class DB:
    """ModDB.identify, for these lines: each its own mod with these tags."""
    def __init__(self, tagged):
        self.tagged = tagged

    def identify(self, lines, base_tags, item_level):
        return [Affix(mod(l, self.tagged[l]), [l], 1, 1) for l in lines if l in self.tagged], []


LIFE, FIRE, LEECH = "+50 to maximum Life", "25% increased Fire Damage", "Leech 7.21% of Physical Attack Damage as Life"
TEXT = "\n".join(["Rarity: RARE", "Ring", "Ruby Ring", LIFE, "{fractured}" + FIRE, LEECH, "{tags:life}+10 to maximum Life"])
DATA = DB({LIFE: ("life",), FIRE: ("elemental", "fire", "damage"), LEECH: ("life", "physical", "attack")})


def lines(text):
    return text.split("\n")[3:]


def test_a_catalyst_raises_its_kind_of_mods():
    flesh = quality.recatalyse(TEXT, [LIFE, FIRE, LEECH], DATA, [], 82, (0, 0), (1, 20))
    # life mods x1.2 (decimals kept), the fire one as it is, a line PoB scales itself ({tags:}) left to PoB
    assert lines(flesh) == ["+60 to maximum Life", "{fractured}" + FIRE, "Leech 8.65% of Physical Attack Damage as Life",
                            "{tags:life}+10 to maximum Life"]


def test_a_new_catalyst_takes_the_old_one_s_raise_out():
    shown = [l.replace("{fractured}", "") for l in lines(quality.recatalyse(TEXT, [LIFE, FIRE, LEECH], DATA, [], 82, (0, 0), (1, 20)))]
    now = "\n".join(TEXT.split("\n")[:3] + [shown[0], "{fractured}" + shown[1], shown[2], shown[3]])
    data = DB({shown[0]: ("life",), FIRE: ("fire",), shown[2]: ("life", "physical", "attack")})
    xoph = quality.recatalyse(now, shown[:3], data, [], 82, (1, 20), (5, 20))
    assert lines(xoph)[:3] == [LIFE, "{fractured}30% increased Fire Damage", LEECH]
    assert quality.recatalyse(TEXT, [LIFE], DATA, [], 82, (1, 20), (1, 20)) == TEXT  # nothing moves
