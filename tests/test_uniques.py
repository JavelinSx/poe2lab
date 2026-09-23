"""Uniques of the whole game that go with the build's skills."""
from dataclasses import asdict
from pathlib import Path

import pytest

from poe2lab.analysis import skills as sk, uniques as un
from poe2lab.analysis.threats import MapProfile
from poe2lab.engine import PobEngine
from poe2lab.knowledge import collect

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_reasons_from_mechanics_skill_kinds_and_damage():
    traits = {"creates": {"rage": ["Ferocious Roar"]}, "uses": {"freeze": ["Glacial Cascade"]},
              "kinds": {"Warcry": ["Ferocious Roar"]}, "damage": {"cold"}, "terms": set()}
    amor = {"name": "Amor Mandragora", "lines": ["Gain 1 Druidic Prowess for every 20 total Rage spent"]}
    assert un.relate(amor, traits)[0] | {"skills": None} == {"kind": "uses", "mechanic": "rage", "skills": None,
                                                              "weight": 3}
    horn = {"name": "X", "lines": ["Warcries have 20% increased Cooldown Recovery Rate", "Adds 5 to 9 Cold Damage"]}
    kinds = [r["kind"] for r in un.relate(horn, traits)]
    assert kinds[:2] == ["skillKind", "damage"]
    assert un.relate({"name": "Y", "lines": ["+10 to Strength"]}, traits) == []


def test_off_hand_follows_the_weapon():
    two_hand = [{"slot": "Weapon 1", "type": "Staff", "tags": ["two_hand_weapon"]}]
    assert un.offhand_types(two_hand) == set()
    bow = [{"slot": "Weapon 1", "type": "Bow", "tags": ["two_hand_weapon"]}]
    assert un.offhand_types(bow) == {"Quiver"}
    sword = [{"slot": "Weapon 1", "type": "One Hand Mace", "tags": ["one_hand_weapon"]}]
    assert un.offhand_types(sword) == {"Shield", "Focus"}


@pytest.fixture(scope="module")
def titan():
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text())
    e.set_main_skill(5)
    return e


def test_suggestions_for_a_build(titan):
    cfg = MapProfile().config()
    m = collect(titan)
    view = sk.build_view(titan, cfg, titan.mechanics_raw(), m.uniques, [asdict(g) for g in m.gaps if g.source == "item"])
    base = titan.what_if(config=cfg)["CombinedDPS"]
    r = un.suggest(titan, cfg, view)
    names = [s["name"] for s in r["suggestions"]]
    assert r["suggestions"] and "Amor Mandragora" not in names  # worn uniques are left out
    assert all(s["type"] not in ("Shield", "Focus", "Quiver") for s in r["suggestions"])  # two-handed talismans
    rage = [s for s in r["suggestions"] if any(x.get("mechanic") == "rage" for x in s["reasons"])]
    assert rage  # the build builds and spends Rage: uniques about Rage are found
    low = un.suggest(titan, cfg, view, max_level=20)
    assert all(s["level"] <= 20 for s in low["suggestions"])
    assert titan.what_if(config=cfg)["CombinedDPS"] == base
