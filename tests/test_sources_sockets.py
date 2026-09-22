"""Mod sources (essences, desecration) and socket plans on the user's Titan."""
from pathlib import Path

import pytest

from poe2lab.analysis.report import defence_weights
from poe2lab.analysis.sockets import plan_sockets
from poe2lab.analysis.sources import desecrated_sources, essence_sources
from poe2lab.analysis.threats import MapProfile, survivable_hits
from poe2lab.data.moddb import ModDB
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
    info = titan.socket_info("Weapon 1")
    base = titan.what_if(config=cfg)
    same = titan.what_if(config=cfg, replace_runes=("Weapon 1", info["runes"]))
    empty = titan.what_if(config=cfg, replace_runes=("Weapon 1", ["None"] * info["sockets"]))
    assert same["CombinedDPS"] == pytest.approx(base["CombinedDPS"])
    assert empty["CombinedDPS"] < base["CombinedDPS"]


def test_socket_plan_respects_corruption(titan):
    profile = MapProfile()
    plans = plan_sockets(titan, profile.config(), "balanced", defence_weights(survivable_hits(titan, profile)))
    boots = next(p for p in plans if p.slot == "Boots")
    allowed = {o["name"] for o in titan.socket_info("Boots")["options"] if o["corrupted"]}
    assert boots.best and all(o.name in allowed for o in boots.best)  # boots are corrupted
    assert any("Chaos Resistance" in " ".join(o.lines) for o in boots.best)
