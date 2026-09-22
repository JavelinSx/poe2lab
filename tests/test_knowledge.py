"""Mechanics PoB ignores are found from game data alone - the Titan's key ones without asking the player."""
import pytest

from poe2lab.knowledge import collect
from poe2lab.profile import open_build


@pytest.fixture(scope="module")
def mechanics():
    engine, _ = open_build("titan", corrections=False)
    return collect(engine)


def _gap(m, stat_or_line):
    return next(g for g in m.gaps if g.what == stat_or_line)


def test_walking_calamity_buff_is_found_with_real_values(mechanics):
    fire = _gap(mechanics, "walking_calamity_non_skill_base_all_damage_%_to_gain_as_fire")
    rage = _gap(mechanics, "walking_calamity_base_rage_regeneration_per_minute")
    assert fire.likely_impact and "Gained as Fire" in fire.text
    assert "Rage regenerated per second" in rage.text


def test_druidic_prowess_line_is_found(mechanics):
    g = _gap(mechanics, "Gain 1 Druidic Prowess for every 20 total Rage spent")
    assert g.source == "item" and "Amor Mandragora" in g.where and g.likely_impact


def test_cosmetic_stats_are_filtered(mechanics):
    assert not any("head_movement" in g.what or "display" in g.what for g in mechanics.gaps)


def test_skill_descriptions_and_uniques_are_collected(mechanics):
    wc = next(s for s in mechanics.skills if s["name"] == "Walking Calamity")
    assert "Glory" in wc["description"]
    assert any(u["name"].startswith("Amor Mandragora") for u in mechanics.uniques)
