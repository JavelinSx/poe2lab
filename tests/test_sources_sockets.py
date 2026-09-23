"""Mod sources (essences, desecration) and socket plans on a public Titan (tests/fixtures/titan.txt)."""
from pathlib import Path

import pytest

from poe2lab.analysis.report import defence_weights
from poe2lab.analysis.sockets import plan_sockets
from poe2lab.analysis.sources import desecrated_sources, essence_sources
from poe2lab.analysis.threats import MapProfile, survivable_hits
from poe2lab.data.moddb import ModDB
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


def test_essences_and_desecration_as_sources(titan, db):
    essences = titan.export_essences()
    chaos = next(m for m in db.mods if m.id == "ChaosResist6")
    names = [name for name, _ in essence_sources(db, essences, chaos, "Helmet")]
    assert "Essence of Ruin" in names
    assert not essence_sources(db, essences, chaos, "Talisman")
    mom = next(m for m in db.mods if m.set == "Item" and "taken from Mana before Life" in m.lines[0])
    assert desecrated_sources(db, mom)


def test_rune_replacement_round_trips(titan):
    cfg = MapProfile().config()
    slot = "Weapon 1 Swap"  # the talisman Furious Slam hits with: two Greater Iron Runes
    info = titan.socket_info(slot)
    base = titan.what_if(config=cfg)
    same = titan.what_if(config=cfg, replace_runes=(slot, info["runes"]))
    empty = titan.what_if(config=cfg, replace_runes=(slot, ["None"] * info["sockets"]))
    assert same["CombinedDPS"] == pytest.approx(base["CombinedDPS"])
    assert empty["CombinedDPS"] < base["CombinedDPS"]


def test_socket_plan_skips_corrupted_and_druid_only_runes(titan):
    profile = MapProfile()
    plans = plan_sockets(titan, profile.config(), "balanced", defence_weights(survivable_hits(titan, profile)))
    corrupted = {i["slot"] for i in titan.equipped_item_details() if i["corrupted"]}
    assert {p.slot for p in plans} == {"Helmet", "Boots"}  # socketed and not corrupted (Body Armour, Gloves are)
    assert not corrupted & {p.slot for p in plans}
    assert all(not o.name.startswith("Legacy of") for p in plans for o in p.best)  # Titan is not a Druid
