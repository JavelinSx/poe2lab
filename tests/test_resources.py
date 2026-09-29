"""Rage and charges as a fight plays them out: what the build's lines and gems make, the level they keep, and a
tree priced at the level a node brings."""
from pathlib import Path

import pytest

from poe2lab.analysis import resources
from poe2lab.analysis.resources import ResourceModel, Sources, fight, read_gems, read_lines
from poe2lab.analysis.threats import MapProfile
from poe2lab.profile import open_build

BUILDS = Path(__file__).resolve().parent / "fixtures"
CTX = {"melee": True, "axe": False, "shapeshift": False}


def test_the_lines_that_make_and_keep_rage_and_charges():
    got = read_lines(["Gain 3 Rage when Hit by an Enemy", "Gain 1 Rage on Melee Hit", "+4 to Maximum Rage",
                      "Inherent loss of Rage is 25% slower", "Gain 2 Rage on Melee Axe Hit",
                      "20% increased Endurance, Frenzy and Power Charge Duration",
                      "10% chance when you gain a Frenzy Charge to gain an additional Frenzy Charge",
                      "+1 to Maximum Endurance Charges", "30% increased Armour"], CTX)
    rage = got["rage"]
    assert rage.gains == [("hit_taken", 3.0, 1.0), ("melee_hit", 1.0, 1.0)]  # the axe line: no axe
    assert rage.max_add == 4 and rage.loss_slower == 25
    assert got["frenzy"].duration_inc == 20 and got["frenzy"].extra == pytest.approx(0.1)
    assert got["endurance"].max_add == 1 and not got["endurance"].any  # a bigger pool, nothing that fills it
    gems = read_gems([{"name": "Rage III", "main": False, "stats": {"gain_x_rage_on_melee_hit": 5}},
                      {"name": "Empty", "main": True, "stats": []}])
    assert gems["rage"].gains == [("melee_hit", 5.0, 1.0)]


def test_a_fight_played_out():
    rates = {"melee_hit": 2.0, "hit_taken": 1.0}
    slow = fight(Sources(gains=[("melee_hit", 1.0, 1.0)]), rates, 30, 10, 2, 0, "map")
    fast = fight(Sources(gains=[("melee_hit", 5.0, 1.0)]), rates, 30, 10, 2, 0, "map")
    assert 0 < slow["level"] < fast["level"] <= 30 and fast["fullAfter"] < 6
    # losing it slower between packs keeps more; a boss fight is one long fight
    kept = fight(Sources(gains=[("melee_hit", 1.0, 1.0)]), rates, 30, 2, 2, 0, "map")
    assert kept["level"] > slow["level"]
    assert fight(Sources(gains=[("melee_hit", 1.0, 1.0)]), rates, 30, 10, 2, 0, "boss")["level"] > slow["level"]
    # charges: gone when none came for their duration
    rare = fight(Sources(gains=[("kill", 1.0, 0.05)]), {"kill": 1.0}, 3, 0, 0, 4, "map")
    lasting = fight(Sources(gains=[("kill", 1.0, 0.05)]), {"kill": 1.0}, 3, 0, 0, 30, "map")
    assert rare["level"] < lasting["level"] <= 3


def test_the_titan_s_rage_and_a_node_priced_at_the_rage_it_brings():
    from poe2lab.analysis.tree import Pricing
    engine, bp = open_build(BUILDS / "titan.txt")
    profile = MapProfile(rage=bp.rage, mana_sustained=bp.mana_sustained)
    pricing = Pricing(engine, profile)
    rage = pricing.now["rage"]
    assert 0 < rage["level"] <= rage["max"] and rage["fullAfter"]
    assert pricing.cfg["multiplierRage"] == round(rage["level"])
    # a node that only makes Rage faster moves it - and is priced at the Rage it brings
    when_hit = next(i for i, lines in engine.node_lines(
        [n["id"] for n in engine.tree_graph()["nodes"] if not n["alloc"]]).items()
        if any("Rage when Hit by an Enemy" in line for line in lines))
    cfg, moved = pricing.of(add=[when_hit])
    assert moved["rage"][1] > moved["rage"][0] and cfg["multiplierRage"] >= pricing.cfg["multiplierRage"]
    armour = next(n["id"] for n in engine.tree_graph()["nodes"] if not n["alloc"] and n["stats"] == ["15% increased Armour"])
    assert pricing.of(add=[armour]) == (pricing.cfg, None)  # nothing to do with Rage: the build's own level
    # a Rage the player set stands
    set_by_player = Pricing(engine, MapProfile(rage=20))
    assert "rage" not in set_by_player.now and set_by_player.cfg["multiplierRage"] == 20


def test_a_package_on_a_full_tree_takes_the_weakest_branches_place():
    from poe2lab.analysis.tree import mechanic_packages, take_package
    engine, bp = open_build(BUILDS / "titan.txt")
    profile = MapProfile(rage=bp.rage, mana_sustained=bp.mana_sustained)
    budget = engine.points_budget()
    assert budget["used"] == budget["total"]  # the fixture's tree is full
    pk = mechanic_packages(engine, profile)["packages"][0]
    ids = [n["id"] for n in sorted(pk["notables"], key=lambda n: n["points"])]
    r = take_package(engine, profile, "balanced", ids, budget["total"])
    after = engine.points_budget()
    assert r["fits"] and r["removed"] and after["used"] <= budget["total"]
    if r["kept"]:
        assert r["value"] > 0 and all(n["alloc"] for n in engine.tree_graph()["nodes"] if n["id"] in ids)
    else:
        assert after == budget  # put back as it was
