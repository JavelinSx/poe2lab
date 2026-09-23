"""A minion build: its damage is the army's, so every analysis ranks minion stats instead of seeing 0 DPS."""
from pathlib import Path

import pytest

from poe2lab.analysis.gradients import compute
from poe2lab.profile import open_build

LICH = Path(__file__).resolve().parent / "fixtures" / "lich-minions.txt"  # public build from pobb.in


@pytest.fixture(scope="module")
def lich():
    engine, _ = open_build(LICH)
    return engine


def test_damage_is_the_minion_army(lich):
    out = lich.what_if()
    assert out["DpsFromMinions"] == 1 and out["PlayerCombinedDPS"] == 0
    assert out["CombinedDPS"] == pytest.approx(out["Minion.CombinedDPS"] * out["MinionCount"])


def test_minion_stats_lead_the_ranking(lich):
    _, grads = compute(lich)
    best = {g.stat.key for g in sorted(grads, key=lambda g: -g.one["dps"])[:5]}
    assert best & {"minion_levels", "minion_speed", "minion_damage"}
