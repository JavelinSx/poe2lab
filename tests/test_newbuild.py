"""The build constructor's first step: a class, its ascendancy and a stage's level, as an empty PoB build."""
import pytest
from fastapi.testclient import TestClient

from poe2lab import library, newbuild, pobfiles, profile
from poe2lab.engine.pob import PobEngine

H = {"X-Poe2lab": "1"}


@pytest.fixture(scope="module")
def engine():
    return PobEngine()


def test_the_classes_and_their_ascendancies(engine):
    classes = {c["name"]: c for c in newbuild.classes(engine)}
    assert len(classes) >= 8 and {"Monk", "Witch", "Warrior", "Ranger"} <= set(classes)
    monk = classes["Monk"]
    assert [a["name"] for a in monk["ascendancies"]][:2] == ["Martial Artist", "Invoker"]
    assert next(a["id"] for a in monk["ascendancies"] if a["name"] == "Invoker") == "Monk2"
    assert classes["Warrior"]["str"] > classes["Warrior"]["int"]  # a class's attributes lean its way


def test_an_empty_build_of_an_ascendancy_at_a_level(engine):
    engine.load_xml(newbuild.empty_build(engine, "Monk2", 80), "new")
    info = engine.info()
    assert (info["class"], info["ascendancy"], info["level"]) == ("Monk", "Invoker", 80)
    assert engine.skill_groups() == [] and engine.equipped_items() == [] and engine.skill_damage() == []
    with pytest.raises(ValueError):
        newbuild.empty_build(engine, "Nobody9", 80)


def test_stage_levels():
    assert newbuild.level_of("endgame") == 92 and newbuild.level_of("campaign") == 60
    assert newbuild.level_of("custom", 150) == 100 and newbuild.level_of("maps", 71) == 71
    with pytest.raises(ValueError):
        newbuild.level_of("nowhere")


def test_made_from_the_interface_and_saved_into_itself(tmp_path, monkeypatch):
    from poe2lab.web import server
    for module in (library, pobfiles, profile, server):
        if hasattr(module, "PROJECT_BUILDS"):
            monkeypatch.setattr(module, "PROJECT_BUILDS", tmp_path)
    monkeypatch.setattr(library, "TRASH", tmp_path / ".trash")
    with TestClient(server.app) as client:
        classes = client.get("/api/new/classes").json()
        assert classes["stages"]["endgame"] == 92 and classes["classes"]
        b = client.post("/api/builds/new", json={"ascendancy": "Warrior1", "stage": "maps", "name": "С нуля"}, headers=H).json()
        assert b["name"] == "С нуля" and b["info"]["ascendancy"] == "Titan" and b["info"]["level"] == 80
        assert b["profileRaw"]["constructor"] == {"stage": "maps", "level": 80}
        assert (tmp_path / "С нуля.txt").is_file() and (tmp_path / "С нуля.profile.json").is_file()
        r = client.post("/api/builds/new", json={"ascendancy": "Warrior1", "name": "С нуля"}, headers=H)
        assert r.status_code == 400  # the name is taken
        assert client.post("/api/builds/new", json={"ascendancy": "Nobody9"}, headers=H).status_code == 400
        # an edit of the plan written into the build itself: the old code to the trash
        node = client.get("/api/tree?mode=balanced&points=6").json()["growth"][0]
        client.post("/api/tree/add", json={"id": node["id"], "name": node["name"]}, headers=H)
        # a node taken into weapon set II: the plan says which set
        near = next(n for n in client.get("/api/tree/graph").json()["nodes"]
                    if not n["alloc"] and n["type"] == "Normal" and not n["asc"] and n["cost"] == 1)
        plan = client.post("/api/tree/add", json={"id": near["id"], "name": near["name"], "set": 2}, headers=H).json()
        assert plan["log"][-1]["set"] == 2 and "set" not in plan["log"][0]
        assert client.post("/api/tree/add", json={"id": near["id"], "set": 3}, headers=H).status_code == 422
        saved = client.post("/api/builds/commit", headers=H).json()
        assert saved["name"] == "С нуля" and client.get("/api/plan").json() is None  # the edit is the build now
        assert any((tmp_path / ".trash").iterdir())
        assert client.get("/api/builds/code").json()["code"]
    server.session.engine = None


def test_the_tree_s_points_and_what_a_click_does(engine):
    """The points a level gives, and a node's cost (its path) before a click takes it, what drops with it after."""
    engine.load_xml(newbuild.empty_build(engine, "Monk2", 92), "new")
    budget = engine.points_budget()
    assert budget == {"used": 0, "total": 115, "asc": 0, "ascTotal": 8,  # 91 by level, 24 from the acts' quests
                      "ws1": 0, "ws2": 0, "wsTotal": 24}  # a weapon set's nodes: up to the quests' 24
    graph = engine.tree_graph()
    assert graph["budget"] == budget
    node = next(n for n in graph["nodes"] if not n["alloc"] and n["type"] == "Notable" and not n["asc"] and 0 < n["cost"] <= 8)
    assert len(engine.tree_add(node["id"])) == node["cost"] and engine.points_budget()["used"] == node["cost"]
    after = {n["id"]: n for n in engine.tree_graph()["nodes"]}[node["id"]]
    assert after["alloc"] and after["cost"] == 0 and after["drop"] >= 1
    assert len(engine.tree_remove(node["id"])) == after["drop"]
