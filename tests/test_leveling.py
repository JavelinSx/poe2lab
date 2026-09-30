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
