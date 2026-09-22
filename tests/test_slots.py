"""Mod database and per-slot plans on the user's Titan."""
from pathlib import Path

import pytest

from poe2lab.analysis.report import defence_weights
from poe2lab.analysis.slots import craft_path, plan_slot
from poe2lab.analysis.threats import MapProfile, survivable_hits
from poe2lab.data.moddb import ModDB, max_roll, pattern, ranges
from poe2lab.engine import PobEngine

TITAN = (Path(__file__).resolve().parents[1] / "builds" / "titan.txt").read_text()


@pytest.fixture(scope="module")
def titan():
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(4)
    return e


@pytest.fixture(scope="module")
def db(titan):
    return ModDB.from_engine(titan)


@pytest.fixture(scope="module")
def weights(titan):
    return defence_weights(survivable_hits(titan, MapProfile()))


def _item(engine, slot):
    return next(i for i in engine.equipped_item_details() if i["slot"] == slot)


def test_line_helpers():
    assert pattern("+(24-27)% to Chaos Resistance") == pattern("+44% to Chaos Resistance") == "#% to Chaos Resistance"
    assert ranges("Adds (23-35) to (39-59) Physical Damage") == [(23, 35), (39, 59)]
    assert max_roll("Adds (23-35) to (39-59) Physical Damage") == "Adds 35 to 59 Physical Damage"


def test_rollable_respects_base_tags_and_item_level(db):
    helmet = {"helmet", "str_armour", "armour", "default"}
    talisman = {"talisman", "weapon", "twohand", "two_hand_weapon", "default"}
    chaos = lambda tags, ilvl: [m for m in db.rollable(tags, ilvl) if m.id.removeprefix("ChaosResist").isdigit()]
    assert chaos(helmet, 82) and not chaos(talisman, 82)
    assert max(m.level for m in chaos(helmet, 70)) <= 70


def test_identify_weapon_affixes(titan, db):
    item = _item(titan, "Weapon 1")
    affixes, unknown = db.identify([x["line"] for x in item["explicit"]], item["tags"], item["itemLevel"])
    assert not unknown
    kinds = {a.rolled[0]: a.mod.type for a in affixes}
    assert kinds["+4 to Level of all Melee Skills"] == "Suffix"
    assert kinds["Adds 26 to 42 Physical Damage"] == "Prefix"
    assert sum(k == "Prefix" for k in kinds.values()) == 3 and sum(k == "Suffix" for k in kinds.values()) == 3


def test_slot_plan_flags_load_bearing_and_utility(titan, db, weights):
    cfg = MapProfile().config()
    amulet = plan_slot(titan, db, cfg, _item(titan, "Amulet"), "balanced", weights)
    spirit = next(a for a in amulet.affixes if "Spirit" in a.lines[0])
    assert "spirit на резервы" in spirit.holds and not spirit.replaceable
    boots = plan_slot(titan, db, cfg, _item(titan, "Boots"), "balanced", weights)
    ms = next(a for a in boots.affixes if "Movement Speed" in a.lines[0])
    assert ms.utility and not ms.replaceable
    ring = plan_slot(titan, db, cfg, _item(titan, "Ring 1"), "balanced", weights)
    leech = next(a for a in ring.affixes if "Leech" in a.lines[0])
    assert 50 < leech.changes["recovery"] <= 100  # share of current recovery, not a blow-up vs. near zero


def test_craft_path_keeps_caps_and_restores_build(titan, db, weights):
    cfg = MapProfile().config()
    before = titan.what_if(config=cfg)
    texts = {i["slot"]: titan.item_text(i["slot"]) for i in titan.equipped_item_details()}
    path = craft_path(titan, db, cfg, "balanced", weights, steps=3)
    assert len(path) == 3
    assert all(s.slot not in ("Weapon 1", "Helmet", "Boots", "Body Armour", "Ring 2") for s in path)  # corrupted
    after = titan.what_if(config=cfg)
    assert after["CombinedDPS"] == pytest.approx(before["CombinedDPS"])
    assert {i["slot"]: titan.item_text(i["slot"]) for i in titan.equipped_item_details()} == texts
