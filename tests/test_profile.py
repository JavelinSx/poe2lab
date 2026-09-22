"""Build profiles: confirmed facts and corrections for mechanics PoB misses."""
import json
from pathlib import Path

import pytest

from poe2lab.analysis.report import gates
from poe2lab.analysis.threats import MapProfile, recovery, survivable_hits
from poe2lab.profile import CORRECTION_BLOCK, BuildProfile, Correction, open_build

BUILDS = Path(__file__).resolve().parents[1] / "builds"


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
    assert engine.main_skill() == "Rampage"


def test_mana_gate_respects_confirmation():
    engine, _ = open_build(BUILDS / "titan.txt", corrections=False)
    profile = MapProfile()
    stats = engine.what_if(config=profile.config())
    hits, rec = survivable_hits(engine, profile), recovery(engine, profile)
    title = "Основной скилл тратит больше маны, чем восстанавливается"
    assert title in {g.title for g in gates(stats, hits, rec)}
    assert title not in {g.title for g in gates(stats, hits, rec, mana_sustained=True)}


def test_profile_file_is_valid_json():
    raw = json.loads((BUILDS / "titan.profile.json").read_text(encoding="utf-8"))
    assert raw["main_skill"]["group"] == 4
