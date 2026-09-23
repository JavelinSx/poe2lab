"""The skills tab: gems per skill, links between skills from the mechanics dictionary, and the levelling plan."""
from pathlib import Path

import pytest

from poe2lab.analysis import skills as sk
from poe2lab.analysis.threats import MapProfile
from poe2lab.engine import PobEngine

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def gem(description="", stats=(), tags=(), support=False, name="X"):
    return {"name": name, "description": description, "stats": list(stats), "tags": list(tags), "support": support}


def test_creating_and_using_a_mechanic_read_from_the_game_text():
    cascade = gem("Frozen enemies hit by the final spike are dealt heavy damage but the Freeze is Consumed. "
                  "Ice Crystals hit by the final spike explode.", ["never_freeze"], ["cold", "attack"])
    assert sk.mechanics_of(cascade) == {"creates": ["combo"], "uses": ["impale", "ice_crystal", "freeze"]}
    locus = gem("Leap backward and crack the ground with your staff to call forth an Ice Crystal", [], ["cold", "attack"])
    assert {"ice_crystal", "freeze"} <= set(sk.mechanics_of(locus)["creates"])
    # a support mentioning an ailment, or tagged with a damage type, does not inflict it
    assert sk.mechanics_of(gem("Culling a Shocked enemy with Supported Skills infuses", support=True)) == \
        {"creates": [], "uses": ["shock"]}
    assert sk.mechanics_of(gem("causing Ignite applied to you to last shorter", tags=["fire"], support=True)) == \
        {"creates": [], "uses": []}
    assert "shock" not in sk.mechanics_of(gem("Hits create a damaging shockwave"))["creates"]
    # the skill that spends Combo is not one of those that build it
    bell = gem("Build Combo by successfully Striking Enemies with other skills. After reaching maximum Combo, use this",
               ["active_skill_required_number_of_combo_stacks"], ["attack"])
    assert sk.mechanics_of(bell) == {"creates": [], "uses": ["impale", "combo"]}


def test_links_pair_different_gems_and_flag_what_nothing_creates():
    def group(i, *gems):
        return {"index": i, "enabled": True, "actives": [{"name": gems[0]["name"]}],
                "gems": [g | {"enabled": True, "mechanics": sk.mechanics_of(g)} for g in gems]}
    locus = gem("call forth an Ice Crystal", tags=["cold", "attack"], name="Frozen Locus")
    cascade = gem("the Freeze is Consumed. Ice Crystals hit by the final spike explode.", ["never_freeze"],
                  ["cold", "attack"], name="Glacial Cascade")
    found = {l["key"]: l for l in sk.links([group(1, cascade), group(2, locus)])}
    assert [r["gem"] for r in found["freeze"]["creates"]] == ["Frozen Locus"]
    assert [r["gem"] for r in found["ice_crystal"]["uses"]] == ["Glacial Cascade"]
    alone = {l["key"]: l for l in sk.links([group(1, cascade)])}
    assert alone["freeze"]["missing"]  # nothing in that build freezes


def test_availability_follows_uncut_gem_drops():
    assert sk.available_level({"support": True, "tier": 3}) == 33
    assert sk.available_level({"support": False, "tier": 7, "reqLevel": 22}) == 23
    assert sk.available_level({"support": False, "tier": 0}) is None  # a weapon's skill or a lineage support


@pytest.fixture(scope="module")
def titan():
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text())
    e.set_main_skill(5)
    return e


def test_build_view(titan):
    v = sk.build_view(titan, MapProfile().config(), titan.mechanics_raw())
    slam = next(g for g in v["groups"] if g["index"] == 5)
    close = next(x for x in slam["gems"] if x["name"] == "Close Combat II")
    assert close["because"] == ["атака"] and close["worth"]["dps"] > 1 and close["lines"]
    rage = next(l for l in v["links"] if l["key"] == "rage")
    assert "Furious Slam" in {r["gem"] for r in rage["uses"]} and rage["creates"]
    assert titan.what_if()["CombinedDPS"] > 0  # the build is left as it was


def test_leveling_view(titan):
    base = titan.what_if()["CombinedDPS"]
    v = sk.leveling_view(titan, MapProfile().config())
    assert [row["level"] for row in v["timeline"]] == sorted(row["level"] for row in v["timeline"])
    slam = next(p for p in v["plans"] if p["skill"] == "Furious Slam")
    first = slam["stages"][0]
    assert first["level"] == 1 and first["later"] and first["options"]
    assert all(o["tier"] == 1 and o["dps"] > 0 for o in first["options"])  # tier 1 supports drop from the start
    assert titan.what_if()["CombinedDPS"] == base  # every tried gem was taken out again


def test_one_option_per_support_family(titan):
    v = sk.leveling_view(titan, MapProfile().config())
    for plan in v["plans"]:
        for stage in plan["stages"]:
            names = [o["name"].rstrip(" I") for o in stage["options"]]
            assert len(names) == len(set(names)), (plan["skill"], stage["level"], names)
