"""A build against a reference: characteristics side by side, their items tried in my build, and a full-gear
try-on that must leave my build exactly as it was."""
from pathlib import Path

import pytest

from poe2lab.analysis.threats import MapProfile
from poe2lab.analysis.versus import versus
from poe2lab.profile import open_build

BUILDS = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def pair():
    mine, bp = open_build(BUILDS / "titan.txt")
    ref, ref_bp = open_build(BUILDS / "monk.txt")
    return mine, MapProfile(rage=bp.rage), ref, MapProfile(rage=ref_bp.rage)


def test_foreign_weapon_try_on_is_fully_undone(pair):
    mine, profile, ref, _ = pair
    before = mine.what_if(config=profile.config())
    # Furious Slam cannot use a quarterstaff: PoB moves socket groups to the other weapon set
    with mine.swapped_items({"Weapon 1 Swap": ref.item_text("Weapon 1"), "Belt": None}):
        worn = mine.what_if(config=profile.config())
    after = mine.what_if(config=profile.config())
    assert worn["CombinedDPS"] < before["CombinedDPS"]
    assert {k: v for k, v in after.items() if isinstance(v, (int, float))} == \
           {k: v for k, v in before.items() if isinstance(v, (int, float))}


def test_versus_lists_stats_and_slots(pair):
    titan, titan_profile, monk, monk_profile = pair
    v = versus(monk, monk_profile, titan, titan_profile)  # the Monk against the Titan as a reference
    rows = {r["key"]: r for r in v["rows"]}
    assert rows["es"]["mine"] > 4000 and rows["es"]["ref"] == 0  # the Monk stands on energy shield
    assert {"hit_Physical", "res_Chaos", "Str", "dps"} <= rows.keys()
    slots = {s["slot"]: s for s in v["slots"]}
    assert slots["Weapon 1"]["swap"]["dps_pct"] <= -99  # a talisman does not fit Whirling Assault
    assert "Weapon 1 Swap" in slots  # weapon sets are compared too
    assert slots["Ring 1"]["swap"] is not None and slots["Ring 1"]["ref"]["name"]
    assert v["allGear"]["es"] < rows["es"]["mine"]
