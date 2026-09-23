"""The game's term popups: found in skill and item texts, linked to each other, and uniques in the skill links."""
import pytest

from poe2lab import gamedata, keywords as kw
from poe2lab.analysis import skills as sk

TERMS = {
    "Rage": {"name": "Rage", "text": "Rage grants 1% more [Attack|Attack] damage per 1 Rage.",
             "nameLocal": "Свирепость", "textLocal": "Свирепость дарует на 1% больше урона от [Attack|атак]."},
    "Attack": {"name": "Attack", "text": "An attack.", "nameLocal": "Атака", "textLocal": "Атака."},
    "DruidicProwess": {"name": "Druidic Prowess", "text": "A stacking [Buff] granting [Rage].",
                       "nameLocal": "Друидизм", "textLocal": "Суммирующийся эффект, дающий [Rage|свирепость]."},
    "Stun": {"name": "Stun", "text": "Stun.", "nameLocal": "Оглушение", "textLocal": "Оглушение."},
    "HeavyStun": {"name": "Heavy Stun", "text": "Heavy.", "nameLocal": "Сильное оглушение", "textLocal": "Сильное."},
    "IceCrystals": {"name": "Ice Crystals", "text": "Solid ice.", "nameLocal": "Ледяные кристаллы", "textLocal": "Лёд."},
    "Maces": {"name": "Maces", "text": "A weapon class.", "nameLocal": "Булавы", "textLocal": "Класс оружия."},
}


@pytest.fixture(autouse=True)
def terms(monkeypatch):
    monkeypatch.setattr(gamedata, "load_keywords", lambda lang: TERMS)
    kw._cache.clear()


def test_terms_found_in_text():
    text = "Gain 1 Druidic Prowess for every 20 total Rage spent. Heavy Stun enemies. Call forth an Ice Crystal. Maces."
    assert kw.find([text]) == ["DruidicProwess", "Rage", "HeavyStun", "IceCrystals"]  # singular form found too
    assert kw.find(["an Attack that Stuns"]) == []  # generic words stay out; "Stuns" is not "Stun"


def test_entries_bring_the_terms_they_link_to():
    got = kw.entries(["DruidicProwess"])
    assert set(got) == {"DruidicProwess", "Rage"}  # [Buff] is not a known term: left out
    assert kw.plain(TERMS["Rage"]["textLocal"]) == "Свирепость дарует на 1% больше урона от атак."


def test_a_unique_joins_the_links_between_skills():
    slam = {"name": "Furious Slam", "description": "Consumes 10 Rage if possible", "stats": [], "tags": ["attack"],
            "support": False}
    roar = {"name": "Ferocious Roar", "description": "immediately gaining Rage", "stats": [], "tags": [],
            "support": False}
    group = lambda i, g: {"index": i, "enabled": True, "actives": [{"name": g["name"]}],
                          "gems": [g | {"enabled": True, "mechanics": sk.mechanics_of(g)}]}
    amor = {"name": "Amor Mandragora, Changeling Talisman", "slot": "Weapon 1", "support": True,
            "description": "Gain 1 Druidic Prowess for every 20 total Rage spent"}
    amor["mechanics"] = sk.mechanics_of(amor)
    rage = next(l for l in sk.links([group(1, slam), group(2, roar)], [amor]) if l["key"] == "rage")
    users = {r["gem"]: r for r in rage["uses"]}
    assert users["Amor Mandragora, Changeling Talisman"]["item"] and "Furious Slam" in users
    assert rage["terms"] == ["Rage"]
