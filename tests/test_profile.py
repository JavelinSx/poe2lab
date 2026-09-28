"""Build profiles: confirmed facts and corrections for mechanics PoB misses."""
import json
from pathlib import Path

import pytest

from poe2lab.analysis.report import gates
from poe2lab.analysis.threats import MapProfile, recovery, survivable_hits
from poe2lab.profile import CORRECTION_BLOCK, BuildProfile, Correction, open_build

BUILDS = Path(__file__).resolve().parent / "fixtures"


def test_correction_scales_by_uptime():
    c = Correction("Gain 30% of Damage as Extra Fire Damage", "test", uptime=0.5)
    assert c.line == "Gain 15% of Damage as Extra Fire Damage"
    assert Correction("Gain 30% of Damage as Extra Fire Damage", "test").line.startswith("Gain 30%")


def test_missing_profile_is_empty(tmp_path):
    build = tmp_path / "x.txt"
    build.write_text("")
    p = BuildProfile.for_build(build)
    assert p.path is None and p.group is None and not p.corrections


def test_titan_profile_applies_skill_and_correction():
    engine, bp = open_build(BUILDS / "titan.txt")
    assert engine.main_skill() == "Furious Slam" and bp.mana_sustained and bp.rage is None
    cfg = MapProfile().config()
    with_fix = engine.what_if(config=cfg)["CombinedDPS"]
    engine.set_custom_mods(CORRECTION_BLOCK, [])
    without = engine.what_if(config=cfg)["CombinedDPS"]
    assert with_fix / without - 1 == pytest.approx(bp.correction_dps_pct / 100, abs=1e-6)
    assert bp.correction_dps_pct > 15


def test_arguments_override_profile_skill():
    engine, _ = open_build(BUILDS / "titan.txt", group=3, corrections=False)
    assert engine.main_skill() == "Lunar Assault"


def test_mana_gate_respects_confirmation():
    engine, _ = open_build(BUILDS / "titan.txt", corrections=False)
    profile = MapProfile()
    stats = engine.what_if(config=profile.config())
    hits, rec = survivable_hits(engine, profile), recovery(engine, profile)
    title = "Основной скилл тратит больше маны, чем восстанавливается"
    assert title in {g.title for g in gates(stats, hits, rec)}
    assert title not in {g.title for g in gates(stats, hits, rec, mana_sustained=True)}


def test_build_by_name_and_from_pob_xml(tmp_path, monkeypatch):
    from poe2lab import pobfiles
    from poe2lab.engine import decode_pob_code
    assert pobfiles.resolve_build("titan") == (BUILDS / "titan.txt").resolve()
    saved = tmp_path / "Builds"
    saved.mkdir()
    (saved / "My Titan.xml").write_text(decode_pob_code((BUILDS / "titan.txt").read_text()), encoding="utf-8")
    monkeypatch.setattr(pobfiles, "pob_build_dirs", lambda: [saved])
    path = pobfiles.resolve_build("my titan")
    assert path.name == "My Titan.xml"
    engine, bp = open_build(path, group=5)
    assert engine.main_skill() == "Furious Slam" and bp.path is None
    with pytest.raises(FileNotFoundError):
        pobfiles.resolve_build("no such build")


def test_profile_file_is_valid_json():
    raw = json.loads((BUILDS / "titan.profile.json").read_text(encoding="utf-8"))
    assert raw["main_skill"]["group"] == 5


def test_uptime_scales_a_whole_range():
    assert Correction("Adds 26 to 42 Physical Damage", "test", uptime=0.5).line == "Adds 13 to 21 Physical Damage"
    assert Correction("Adds 3 to 5.5 Fire Damage to Attacks", "test", uptime=0.5).line == "Adds 1.5 to 2.75 Fire Damage to Attacks"


def test_chaos_inoculation_has_no_chaos_resistance_to_cap():
    from poe2lab.analysis.threats import IMMUNE_HIT, HitRow, Recovery
    rec = Recovery(life=1, leech=0, regen=0, recoup=0, leech_capped_per_hit=False, energy_shield=6000,
                   es_recharge=800, es_recharge_delay=4)
    stats = {"FireResist": 75, "ColdResist": 75, "LightningResist": 75, "FireResistOverCap": 20, "ColdResistOverCap": 20,
             "LightningResistOverCap": 20, "ChaosResist": 0}
    rows = [HitRow(t, 6000, 5000, 4000) for t in ("Physical", "Fire", "Cold", "Lightning")]
    immune = rows + [HitRow("Chaos", IMMUNE_HIT, IMMUNE_HIT, IMMUNE_HIT)]
    mortal = rows + [HitRow("Chaos", 3000, 2500, 2000)]
    title = "Хаос-резист ниже капа"
    assert title not in {g.title for g in gates(stats, immune, rec)}
    assert title in {g.title for g in gates(stats, mortal, rec)}


def test_russian_node_counts():
    from poe2lab.analysis.report import _nodes_word
    assert [_nodes_word(n) for n in (1, 2, 5, 11, 12, 21, 22, 25)] == [
        "ноду", "ноды", "нод", "нод", "нод", "ноду", "ноды", "нод"]
