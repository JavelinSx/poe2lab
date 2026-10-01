"""Levelling up to a build (poe2lab.analysis.leveling): the ways a class levels, when to switch to the build and
why, the roadmap by acts, and the player's answers kept in the build profile."""
import json

import pytest
from fastapi.testclient import TestClient

from poe2lab.analysis import leveling
from poe2lab.profile import open_build
from poe2lab.web import server
from poe2lab.web.server import app, session


@pytest.fixture(scope="module")
def titan():
    return open_build("titan")


@pytest.fixture(scope="module")
def monk():
    return open_build("monk")


def test_a_class_levels_with_the_skills_of_its_attributes(titan, monk):
    w = leveling.ways(monk[0])
    ids = [x["id"] for x in w["ways"]]
    assert w["attributes"] == ["dexterity", "intelligence"] and ids[0] == "build"
    # the Monk's quarterstaff, one way per element, the build's own weapon and element before the others
    assert {"quarterstaff:physical", "quarterstaff:cold", "quarterstaff:lightning"} <= set(ids)
    assert ids.index("quarterstaff:physical") < ids.index("quarterstaff:cold")
    for x in w["ways"][1:]:
        assert x["from"] <= leveling.EARLY_LEVEL and x["skills"] == sorted(x["skills"], key=lambda s: (s["level"], s["name"]))
    # a Warrior (strength only) levels with maces; talismans need intelligence too (the Druid's)
    wt = leveling.ways(titan[0])
    assert wt["attributes"] == ["strength"]
    assert "mace:physical" in [x["id"] for x in wt["ways"]] and not any(x["weapon"] == "talisman" for x in wt["ways"][1:])


def test_the_switch_waits_for_what_carries_the_build(titan):
    engine, bp = titan
    config = leveling.MapProfile(rage=bp.rage).config()
    sw = leveling.switch(engine, config, trade=True)
    parts = {p["name"]: p for p in sw["parts"]}
    main = parts["Furious Slam"]
    assert main["kind"] == "skill" and main["level"] == 1
    # a support counts from its family's first tier: "Close Combat I" drops long before the build's "II"
    cc = parts["Close Combat II"]
    assert cc["firstName"] == "Close Combat I" and cc["level"] < cc["full"]
    # trading: the helmet worth ~40% of the damage sets the switch
    helmet = parts["Constricting Command, Viper Cap"]
    assert helmet["core"] and helmet["decisive"] and sw["level"] == helmet["level"] == 38
    assert all(p["level"] <= sw["level"] for p in sw["parts"] if p["core"] and p["level"])
    # SSF: a unique may never drop, the switch does not wait for it
    ssf = leveling.switch(engine, config, trade=False)
    assert ssf["level"] < sw["level"] and not any(p["decisive"] for p in ssf["parts"] if p["kind"] == "unique")


def test_the_roadmap_goes_act_by_act(titan):
    engine, bp = titan
    r = leveling.roadmap(engine, bp.rage, bp.mana_sustained, {"way": "mace:physical", "trade": True, "pace": "safe"},
                         character_level=20)
    keys = [s["key"] for s in r["stages"]]
    assert keys == ["act1", "act2", "act3", "act4", "interlude", "maps"]
    assert [s["key"] for s in r["stages"] if s["switch"]] == [r["switch"]["stage"]] == ["act3"]
    assert [s["key"] for s in r["stages"] if s["here"]] == ["act2"]
    assert r["stages"][0]["skills"][0]["name"] == "Boneshatter" and r["stages"][1]["penalty"] == -10
    points = [n["points"] for s in r["stages"] for n in s["tree"]]
    assert points == sorted(points) and len(points) == len(leveling.tree_order(engine))
    trials = [a["trial"] for s in r["stages"] for a in s["ascendancy"]]
    assert trials == list(range(1, len(trials) + 1)) and r["mode"] == "defence"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The interface on the test builds, the profile it writes in a temporary folder."""
    monkeypatch.setattr(server, "PROJECT_BUILDS", tmp_path)
    with TestClient(app) as c:
        assert c.post("/api/load", json={"name": "titan"}, headers={"X-Poe2lab": "1"}).status_code == 200
        yield c
    session.engine = None


def test_the_answers_are_kept_in_the_build_profile(client, tmp_path):
    H = {"X-Poe2lab": "1"}
    first = client.get("/api/leveling").json()
    assert first["answers"] is None and first["roadmap"] is None and first["ways"]["ways"][0]["id"] == "build"
    r = client.post("/api/leveling", json={"way": "mace:physical", "trade": False, "pace": "fast", "novice": True},
                    headers=H).json()
    assert r["answers"]["way"] == "mace:physical" and r["roadmap"]["switch"]["trade"] is False
    saved = json.loads((tmp_path / "titan.profile.json").read_text(encoding="utf-8"))
    assert saved["leveling"] == {"way": "mace:physical", "trade": False, "pace": "fast", "novice": True}
    # the profile page does not send them: saving it keeps them
    client.put("/api/profile", json={"notes": ["x"]}, headers=H)
    assert json.loads((tmp_path / "titan.profile.json").read_text(encoding="utf-8"))["leveling"]["way"] == "mace:physical"
    assert client.post("/api/leveling", json={"way": "build", "pace": "slow"}, headers=H).status_code == 400


def test_the_switch_waits_for_what_the_main_skill_stands_on(titan, monk):
    """Besides its own gems the main skill needs buffs worth its damage, what it spends from other skills, and the
    Spirit all of them reserve."""
    engine, bp = monk
    sw = leveling.switch(engine, leveling.MapProfile(rage=bp.rage).config(), trade=True)
    parts = {p["name"]: p for p in sw["parts"]}
    reg = parts["Charge Regulation"]
    assert reg["kind"] == "buff" and reg["core"] and reg["spirit"] > 0 and reg["dps"] >= leveling.CORE_SUPPORT
    assert reg["decisive"] and sw["level"] == reg["level"] > parts["Whirling Assault"]["level"]
    spirit = parts["Spirit"]
    assert spirit["need"] >= reg["spirit"] and not spirit["short"] and spirit["level"] <= sw["level"]
    assert {x["level"] for x in spirit["sources"] if x["kind"] == "quest"} == {11, 36, 61}  # +30, +30, +40
    # starting with the main skill's gems alone: earlier, without the buff, for less damage
    early = sw["early"]
    assert early["level"] < sw["level"] and early["without"] == ["Charge Regulation"] and 0 < early["dps"] < 100
    # the Titan's Rage comes from its own passives and supports: no other skill to wait for
    engine, bp = titan
    sw = leveling.switch(engine, leveling.MapProfile(rage=bp.rage).config(), trade=True)
    assert not [p for p in sw["parts"] if p["kind"] == "source"]


def test_spirit_from_body_armour():
    line = "+1 to Spirit for every 8 Item Energy Shield on Equipped Body Armour"
    m = leveling._ARMOUR_SPIRIT.search(line)
    assert m and m.group(1) == "8" and m.group(2) == "Energy Shield"
    assert leveling._ARMOUR_SPIRIT.search("+1 to Spirit for every 20 Evasion Rating on Equipped Body Armour").group(2) == "Evasion Rating"
    assert leveling._NO_GEAR_SPIRIT.search("Cannot gain Spirit from Equipment")


def test_the_build_as_a_character_of_a_level_has_it(monk):
    """A snapshot: PoB calculates the build with the passive points, gems, gear and quests of a level, and puts the
    build back as it was."""
    engine, bp = monk
    config = leveling.MapProfile(rage=bp.rage).config()
    before = engine.what_if(config=config)
    graph = engine.tree_graph()
    asc = leveling.ascendancy_order(engine, config, "damage")
    quests = engine.quest_rewards()
    gone = set(leveling._not_taken_yet(graph, 45, asc, quests))
    main_tree = [n for n in graph["nodes"] if n["alloc"] and not n["asc"] and n["type"] != "ClassStart" and not n.get("mode")]
    assert len([n for n in main_tree if n["id"] not in gone]) <= 44  # level 45: 44 points
    # the ascendancy: the first trial (act 2) gives 2 points by level 45; none by level 10
    asc_nodes = [n for n in graph["nodes"] if n["alloc"] and n["asc"] and n["type"] != "AscendClassStart"]
    assert 0 < len([n for n in asc_nodes if n["id"] not in gone]) <= 2
    early = set(leveling._not_taken_yet(graph, 10, asc, quests))
    assert all(n["id"] in early for n in asc_nodes)
    levels, equipped = engine.item_levels(), engine.equipped_bases()
    gear = leveling._gear_at(45, levels, equipped, engine.item_bases(), trade=True)
    assert gear and all(levels[slot] > 45 for slot in gear)
    for slot, text in gear.items():
        assert text is None or text.startswith("Rarity: Normal")
    low = engine.at_level(45, leveling._gems_not_yet(engine.skill_groups(), engine.gem_catalog(), 45), gone, gear, config)
    assert 0 < low["CombinedDPS"] < before["CombinedDPS"] and low["Life"] < before["Life"]
    assert engine.what_if(config=config)["CombinedDPS"] == before["CombinedDPS"]  # put back
    # the switch is checked as a character of its level would have it: Spirit and mana work there
    sw = leveling.switch(engine, config, trade=True, rage=bp.rage)
    assert sw["snapshot"]["level"] == sw["level"] and sw["snapshot"]["ok"]
    assert all(set(a) == {"attr", "need", "have"} for a in sw["snapshot"]["attributes"])
