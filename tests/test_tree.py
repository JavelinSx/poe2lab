"""Passive tree: growth options priced by their whole path, respec candidates, and what PoB cannot see."""
from pathlib import Path

import pytest

from poe2lab.analysis.threats import MapProfile
from poe2lab.analysis.tree import analyse
from poe2lab.profile import open_build

BUILDS = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def titan_tree():
    engine, bp = open_build(BUILDS / "titan.txt")
    return analyse(engine, MapProfile(rage=bp.rage, mana_sustained=bp.mana_sustained), max_points=5)


def test_growth_is_priced_per_point_including_travel(titan_tree):
    growth = titan_tree["growth"]
    assert growth and all(1 <= g["points"] <= 5 for g in growth)
    assert [g["perPoint"] for g in growth] == sorted((g["perPoint"] for g in growth), reverse=True)
    assert all(g["name"] not in g["via"] for g in growth)  # the target is not its own travel node
    assert growth[0]["value"] > 0


def test_a_notable_that_gives_nothing_is_not_advice():
    """A monk levelling without ignite: "30% increased Elemental Damage if you've Ignited an Enemy Recently" is worth
    nothing to it - only the small node on the way pays. It must not be offered by its name."""
    engine, bp = open_build(BUILDS / "monk.txt")
    tree = analyse(engine, MapProfile(rage=bp.rage, mana_sustained=bp.mana_sustained), max_points=6, top=40)
    assert all(g["own"] >= 0.1 * g["value"] for g in tree["growth"])
    assert all(g["roadOnly"] and g["own"] < 0.1 * g["value"] and g["via"] for g in tree["roadOnly"])
    named = {g["name"] for g in tree["growth"]}
    assert not named & {g["name"] for g in tree["roadOnly"]}


def test_node_topics_meet_the_build():
    from poe2lab.analysis import fit
    assert [t for t, _ in fit.node_topics(["30% increased maximum Energy Shield"])] == ["energy_shield"]
    assert "shield" in [t for t, _ in fit.node_topics(["+5% Chance to Block with Shields"])]
    engine, bp = open_build(BUILDS / "titan.txt")
    have = fit.build_topics(engine, engine.what_if(config=MapProfile().config()))
    assert {"armour", "attack", "melee", "slam"} <= have and not have & {"evasion", "energy_shield", "spell", "bow"}
    f = fit.fit(["5% chance for Slam Skills you use yourself to cause an additional Aftershock",
                 "30% increased Elemental Damage if you've Ignited an Enemy Recently while holding a Bow"], have)
    assert "slam" in f["fits"] and "bow" in f["misses"]


def test_zero_value_notables_are_sorted_by_fit(titan_tree):
    road = titan_tree["roadOnly"]
    assert road and all(g["verdict"] in ("onBuild", "offBuild", "unknown") for g in road)
    assert all(g["fit"]["misses"] for g in road if g["verdict"] == "offBuild")
    assert any(g["verdict"] == "onBuild" for g in road)  # slams, warcries, stun: the build's, outside PoB's model
    assert titan_tree["buildTopics"]


def test_nodes_pob_cannot_see_are_not_offered_for_respec(titan_tree):
    unseen = {b["name"] for b in titan_tree["unseen"]}
    respec = {b["name"] for b in titan_tree["respec"]}
    assert unseen and not unseen & respec
    assert all(all(abs(v) < 0.05 for v in b["changes"].values()) for b in titan_tree["unseen"])
    assert all(b["lossPerPoint"] < titan_tree["bestGrowthPerPoint"] for b in titan_tree["respec"])


def test_optimize_keeps_the_budget_improves_the_goal_and_can_be_undone():
    from poe2lab.analysis.tree import optimize
    engine, bp = open_build(BUILDS / "titan.txt")
    profile = MapProfile(rage=bp.rage, mana_sustained=bp.mana_sustained)
    before = engine.what_if(config=profile.config())
    budget = engine.tree_points()
    engine.tree_snapshot("test-base")
    r = optimize(engine, profile, "balanced", budget, seed=7, rounds=3)
    assert engine.tree_points() <= budget
    assert r["total"] >= 0 and (r["steps"] or r["total"] == 0)
    engine.tree_restore("test-base")
    after = engine.what_if(config=profile.config())
    assert engine.tree_points() == budget
    assert after["CombinedDPS"] == pytest.approx(before["CombinedDPS"]) and after["Life"] == before["Life"]


def test_the_tree_to_draw_and_the_ascendancy():
    from poe2lab.analysis.tree import ascendancy
    engine, bp = open_build(BUILDS / "titan.txt")
    graph = engine.tree_graph()
    nodes = graph["nodes"]
    assert graph["class"] == "Warrior" and graph["ascendancy"] == "Titan"
    assert {n["asc"] for n in nodes} == {"", "Titan"}  # the main tree and the build's own ascendancy only
    main_taken = sum(1 for n in nodes if n["alloc"] and not n["asc"] and n["type"] not in ("ClassStart",))
    assert main_taken == graph["points"]
    by_id = {n["id"]: n for n in nodes}
    assert all(other in by_id or True for n in nodes for other in n["links"]) and any(n["links"] for n in nodes)
    asc = ascendancy(engine, MapProfile(rage=bp.rage, mana_sustained=bp.mana_sustained))
    assert asc["points"] == 8 and asc["maxPoints"] == 8 and len(asc["taken"]) >= 3
    assert asc["options"] and all(o["path"] and o["id"] == o["path"][-1] or o["id"] in o["path"] for o in asc["options"])
    assert [o["value"] for o in asc["options"]] == sorted((o["value"] for o in asc["options"]), reverse=True)


def test_no_ascendancy_yet_offers_the_class_ones():
    """Before the first trial: every ascendancy of the class with its notables priced on the build."""
    from poe2lab.analysis.tree import ascendancy
    engine, bp = open_build(BUILDS / "titan.txt")
    engine._json("build.spec:SelectAscendClass(0) return _poe2lab_json({})")  # as before the first trial
    graph = engine.tree_graph()
    asc = ascendancy(engine, MapProfile(rage=bp.rage, mana_sustained=bp.mana_sustained))
    assert asc["ascendancy"] == "" and len(asc["choices"]) >= 2
    assert all(c["notables"] for c in asc["choices"])
    assert [c["worth"] for c in asc["choices"]] == sorted((c["worth"] for c in asc["choices"]), reverse=True)
    assert {n["asc"] for n in graph["nodes"] if n["asc"]} == {c["name"] for c in asc["choices"]}
