"""The campaign's rewards (poe2lab.analysis.quests): each option priced in its place on the build, the best one for
the goal, and the player's answer kept in the build profile and counted in every number."""
import json

import pytest
from fastapi.testclient import TestClient

from poe2lab import profile as profile_mod
from poe2lab.analysis import quests
from poe2lab.analysis.threats import MapProfile
from poe2lab.profile import open_build
from poe2lab.web import server
from poe2lab.web.server import app, session

KAOM = "30% increased Global Armour, Evasion and Energy Shield"


@pytest.fixture(scope="module")
def monk():
    return open_build("monk")


def test_each_option_is_priced_in_its_place(monk):
    engine, bp = monk
    r = quests.rewards(engine, MapProfile(rage=bp.rage), "defence")
    by = {c["info"]: c for c in r["choices"]}
    assert {"Tribal Medicine", "Seven Pillars", "Tawhoa's Test", "Venom Draught"} <= set(by)
    shark = by["Tribal Medicine"]
    # the build (imported from the game) took Kaom's Lesson: read as chosen, and priced against nothing, not on top
    assert shark["chosen"] == KAOM
    kaom, rakiata = shark["options"]
    assert kaom["best"] and not rakiata["best"] and kaom["changes"]["ehp"] > max(rakiata["changes"]["ehp"], 0)
    # an option PoB sees nothing in is not a loss: it says what it is for
    charms = by["Medallion"]["options"]
    assert all(o["blind"] == "charms" and not o["best"] for o in charms)
    # the experience pillar costs everything else
    xp = next(o for o in by["Seven Pillars"]["options"] if "Experience" in o["value"])
    assert xp["score"] < 0 and xp["blind"] == "experience"
    fixed = {f["info"]: f for f in r["fixed"]}
    assert fixed["Molten Shrine"]["taken"] and fixed["Molten Shrine"]["changes"]["ehp"] > 0  # 5% increased life


def test_only_real_answers_are_accepted(monk):
    rows = monk[0].quest_rewards()
    var = next(x["var"] for x in rows if x["info"] == "Tribal Medicine")
    beira = next(x["var"] for x in rows if x["info"] == "Beira")
    assert quests.valid(rows, var, KAOM) and quests.valid(rows, var, "None")
    assert not quests.valid(rows, var, "+100 to Strength") and not quests.valid(rows, "questNope", True)
    assert quests.valid(rows, beira, False) and not quests.valid(rows, beira, "yes")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The interface on the monk build, its profile in a temporary folder."""
    monkeypatch.setattr(server, "PROJECT_BUILDS", tmp_path)
    monkeypatch.setattr(profile_mod, "PROJECT_BUILDS", tmp_path)
    with TestClient(app) as c:
        assert c.post("/api/load", json={"name": "monk"}, headers={"X-Poe2lab": "1"}).status_code == 200
        yield c
    session.engine = None


def test_an_answer_counts_in_every_number_and_is_kept(client, tmp_path):
    H = {"X-Poe2lab": "1"}
    var = next(c["var"] for c in client.get("/api/quests").json()["choices"] if c["info"] == "Tribal Medicine")
    es = lambda: client.get("/api/report").json()["baseline"]["es"]  # noqa: E731
    with_kaom = es()
    r = client.post("/api/quests", json={"var": var, "value": "None"}, headers=H).json()
    assert var in r["unchosen"] and es() < with_kaom  # the report counts the answer at once
    assert json.loads((tmp_path / "monk.profile.json").read_text(encoding="utf-8"))["quests"] == {var: "None"}
    # opened again, the build keeps the player's answer, and the profile page's own saves keep it too
    client.put("/api/profile", json={"notes": ["x"]}, headers=H)
    client.post("/api/load", json={"name": "monk"}, headers=H)
    assert next(c for c in client.get("/api/quests").json()["choices"] if c["var"] == var)["chosen"] is None
    assert client.post("/api/quests", json={"var": var, "value": "+1 to everything"}, headers=H).status_code == 400
