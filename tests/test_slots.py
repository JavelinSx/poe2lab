"""Mod database and per-slot plans on a public Titan (tests/fixtures/titan.txt)."""
from pathlib import Path

import pytest

from poe2lab.analysis.report import defence_weights
from poe2lab.analysis.slots import craft_path, plan_slot
from poe2lab.analysis.threats import MapProfile, survivable_hits
from poe2lab.data.moddb import ModDB, max_roll, pattern, ranges
from poe2lab.engine import PobEngine

TITAN = (Path(__file__).resolve().parent / "fixtures" / "titan.txt").read_text()


@pytest.fixture(scope="module")
def titan():
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(5)
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


def test_identify_boot_affixes(titan, db):
    item = _item(titan, "Boots")
    affixes, unknown = db.identify([x["line"] for x in item["explicit"]], item["tags"], item["itemLevel"])
    assert not unknown
    kinds = {a.rolled[0]: a.mod.type for a in affixes}
    assert kinds["25% increased Movement Speed"] == "Prefix"
    assert kinds["+43% to Cold Resistance"] == "Suffix"
    assert sum(k == "Prefix" for k in kinds.values()) == 3 and sum(k == "Suffix" for k in kinds.values()) >= 3


def test_slot_plan_flags_load_bearing_and_utility(titan, db, weights):
    cfg = MapProfile().config()
    boots = plan_slot(titan, db, cfg, _item(titan, "Boots"), "balanced", weights)
    ms = next(a for a in boots.affixes if "Movement Speed" in a.lines[0])
    assert ms.utility and not ms.replaceable
    cold = next(a for a in boots.affixes if "Cold Resistance" in a.lines[0])
    assert any("кап резиста" in h for h in cold.holds) and not cold.replaceable
    belt = plan_slot(titan, db, cfg, _item(titan, "Belt"), "balanced", weights)
    mana = next(a for a in belt.affixes if "maximum Mana" in a.lines[0])
    assert any("мана" in h for h in mana.holds) and not mana.replaceable
    helmet = plan_slot(titan, db, cfg, _item(titan, "Helmet"), "balanced", weights)
    regen = next(a for a in helmet.affixes if "Regeneration" in a.lines[0])
    assert 0 < regen.changes["recovery"] <= 100  # share of current recovery, not a blow-up vs. near zero


def test_craft_path_keeps_caps_and_restores_build(titan, db, weights):
    cfg = MapProfile().config()
    before = titan.what_if(config=cfg)
    details = titan.equipped_item_details()
    texts = {i["slot"]: titan.item_text(i["slot"]) for i in details}
    corrupted = {i["slot"] for i in details if i["corrupted"]}
    assert {"Body Armour", "Gloves"} <= corrupted
    path = craft_path(titan, db, cfg, "balanced", weights, steps=3)
    assert len(path) == 3
    assert not {s.slot for s in path} & corrupted  # corrupted items cannot be changed
    after = titan.what_if(config=cfg)
    assert after["CombinedDPS"] == pytest.approx(before["CombinedDPS"])
    assert {i["slot"]: titan.item_text(i["slot"]) for i in titan.equipped_item_details()} == texts
