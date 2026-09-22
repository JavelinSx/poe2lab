"""Passive tree: growth options priced by their whole path, respec candidates, and what PoB cannot see."""
from pathlib import Path

import pytest

from poe2lab.analysis.threats import MapProfile
from poe2lab.analysis.tree import analyse
from poe2lab.profile import open_build

BUILDS = Path(__file__).resolve().parents[1] / "builds"


@pytest.fixture(scope="module")
def titan_tree():
    engine, bp = open_build(BUILDS / "titan.txt")
    return analyse(engine, MapProfile(rage=bp.rage, mana_sustained=bp.mana_sustained), max_points=5)


def test_growth_is_priced_per_point_including_travel(titan_tree):
    growth = titan_tree["growth"]
    assert growth and all(1 <= g["points"] <= 5 for g in growth)
    assert [g["perPoint"] for g in growth] == sorted((g["perPoint"] for g in growth), reverse=True)
    assert all(g["name"] not in g["via"] for g in growth)  # the target is not its own travel node
    assert growth[0]["changes"]["dps"] > 0


def test_nodes_pob_cannot_see_are_not_offered_for_respec(titan_tree):
    unseen = {b["name"] for b in titan_tree["unseen"]}
    respec = {b["name"] for b in titan_tree["respec"]}
    assert unseen and not unseen & respec
    assert all(all(abs(v) < 0.05 for v in b["changes"].values()) for b in titan_tree["unseen"])
    assert all(b["lossPerPoint"] < titan_tree["bestGrowthPerPoint"] for b in titan_tree["respec"])
