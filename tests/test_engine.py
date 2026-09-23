"""Calibration tests. Expected values were checked against the PoB-PoE2 GUI of the pinned
submodule commit (ce566ea). If PoB is updated and these fail, re-check in the GUI before changing them."""
from pathlib import Path

import pytest

from poe2lab.engine import EnginePool, PobEngine, PobError

BUILD = (Path(__file__).resolve().parent / "fixtures" / "monk.txt").read_text()


@pytest.fixture(scope="module")
def engine():
    e = PobEngine()
    e.load_code(BUILD)
    return e


def test_build_identity(engine):
    info = engine.info()
    assert (info["class"], info["ascendancy"], info["level"]) == ("Monk", "Martial Artist", 95)
    assert engine.main_skill() == "Whirling Assault"


def test_defences_match_gui(engine):
    s = engine.stats()
    assert s["Life"] == 1772
    assert s["EnergyShield"] == 4156
    assert s["Evasion"] == 21218
    assert (s["FireResist"], s["ColdResist"], s["LightningResist"], s["ChaosResist"]) == (75, 75, 75, 69)


def test_damage_matches_gui(engine):
    assert engine.stats()["CombinedDPS"] == pytest.approx(205470, rel=0.005)


def test_what_if_without_changes_equals_full_calc(engine):
    full, misc = engine.stats(), engine.what_if()
    for key in ("CombinedDPS", "TotalEHP", "EnergyShield", "Life"):
        assert misc[key] == pytest.approx(full[key], rel=1e-6)


def test_what_if_does_not_modify_build(engine):
    before = engine.stats()
    node = next(n["id"] for n in engine.allocated_nodes() if n["name"] == "Heavy Frost")
    changed = engine.what_if(remove_nodes=[node])
    assert changed["CombinedDPS"] < before["CombinedDPS"] * 0.6
    engine.recalc()
    assert engine.stats()["CombinedDPS"] == pytest.approx(before["CombinedDPS"])


def test_main_skill_switch(engine):
    try:
        engine.set_main_skill(2, 1)
        assert engine.main_skill() == "Hollow Form"
        assert engine.stats()["CombinedDPS"] < 10000
    finally:
        engine.set_main_skill(2, 2)
    assert engine.main_skill() == "Whirling Assault"


def test_invalid_input_raises(engine):
    with pytest.raises(PobError):
        engine.set_main_skill(99)
    with pytest.raises(PobError):
        engine.what_if(remove_nodes=[999999999])


def test_injected_mods_apply_without_modifying_build(engine):
    base = engine.stats()
    boosted = engine.what_if(mods=["+100 to maximum Life", "10% increased Attack Speed"])
    assert boosted["Life"] > base["Life"]
    assert boosted["Speed"] > base["Speed"]
    after = engine.what_if()
    assert after["Life"] == base["Life"] and after["Speed"] == pytest.approx(base["Speed"])


def test_unparseable_mod_raises(engine):
    with pytest.raises(PobError, match="cannot parse"):
        engine.what_if(mods=["totally not a mod"])


def test_config_override_applies_and_restores(engine):
    base = engine.what_if()
    mob = engine.what_if(config={"enemyLevel": 79, "enemyIsBoss": "None", "enemyCritChance": 100})
    assert mob["PhysicalEnemyDamage"] < base["PhysicalEnemyDamage"]
    assert mob["EnemyCritEffect"] > base["EnemyCritEffect"]
    again = engine.what_if()
    for key in ("PhysicalEnemyDamage", "EnemyCritEffect", "TotalEHP", "CombinedDPS"):
        assert again[key] == pytest.approx(base[key])
    assert engine.config().get("enemyLevel") is None


def test_enemy_damage_mods_lower_survivable_hit(engine):
    base = engine.what_if()
    juiced = engine.what_if(enemy_mods=["50% increased Damage"])
    assert juiced["PhysicalMaximumHitTaken"] < base["PhysicalMaximumHitTaken"]
    assert engine.what_if()["PhysicalMaximumHitTaken"] == base["PhysicalMaximumHitTaken"]


def test_survivable_hits_order(engine):
    from poe2lab.analysis.threats import MapProfile, survivable_hits
    for row in survivable_hits(engine, MapProfile()):
        assert 0 < row.juiced < row.crit < row.normal


def test_all_probe_stats_parse(engine):
    from poe2lab.analysis.stats import STATS, mod_line
    bad = [mod_line(s, m) for s in STATS for m in (1, 2) if not engine.can_parse_mod(mod_line(s, m))]
    assert bad == []


def test_pool_matches_single_engine(engine):
    nodes = [n["id"] for n in engine.allocated_nodes()][:6]
    expected = [engine.what_if(remove_nodes=[n])["CombinedDPS"] for n in nodes]
    with EnginePool(BUILD, workers=2) as pool:
        got = [r["CombinedDPS"] for r in pool.map("what_if", [{"remove_nodes": [n]} for n in nodes])]
    assert got == pytest.approx(expected)
