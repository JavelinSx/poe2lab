"""Web API: open a build, read analyses, compare an item, reject a bad profile, chat without a key."""
import pytest
from fastapi.testclient import TestClient

from poe2lab.web.server import app, session


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    session.engine = None


def test_status_and_build_list(client):
    s = client.get("/api/status").json()
    assert "llm" in s
    names = {b["name"] for b in client.get("/api/builds").json()}
    assert {"titan", "ma95"} <= names


def test_load_report_and_compare(client):
    b = client.post("/api/load", json={"name": "titan"}).json()
    assert b["mainSkill"] == "Furious Slam" and b["info"]["ascendancy"] == "Titan"
    r = client.get("/api/report?mode=balanced").json()
    assert r["damageRange"]["high"] > r["damageRange"]["low"] > 0
    assert any(g["title"] == "Не хватает ловкости" for g in r["gates"])
    text = client.get("/api/item/Weapon 1").json()["text"]
    same = client.post("/api/compare", json={"slot": "Weapon 1", "text": text}).json()
    assert abs(same["dps_pct"]) < 1e-6


def test_mechanics_lists_pob_gaps(client):
    client.post("/api/load", json={"name": "titan"})
    gaps = client.get("/api/mechanics").json()["gaps"]
    assert any("Druidic Prowess" in g["what"] for g in gaps)


def test_bad_profile_is_rejected_without_writing(client):
    client.post("/api/load", json={"name": "titan"})
    r = client.put("/api/profile", json={"corrections": [{"mod": "not a mod", "uptime": 1}]})
    assert r.status_code == 400 and "не понимает" in r.json()["detail"]


def test_chat_without_key_explains(client, monkeypatch):
    monkeypatch.delenv("POE2LAB_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    r = client.post("/api/chat", json={"message": "привет"})
    assert r.status_code == 400 and "DEEPSEEK_API_KEY" in r.json()["detail"]


def test_unknown_build_is_a_clean_error(client):
    r = client.post("/api/load", json={"name": "no such build"})
    assert r.status_code == 400
