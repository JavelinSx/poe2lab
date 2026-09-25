"""Web API: open a build, read analyses, compare an item, reject a bad profile, AI settings, local-only guard."""
import json

import pytest
from fastapi.testclient import TestClient

from poe2lab.web.server import app, session

H = {"X-Poe2lab": "1"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    session.engine = None


@pytest.fixture
def settings_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("POE2LAB_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    return tmp_path


def test_status_and_build_list(client):
    s = client.get("/api/status").json()
    assert "llm" in s
    names = {b["name"] for b in client.get("/api/builds").json()}
    assert {"titan", "monk"} <= names


def test_page_versions_its_scripts(client):
    html = client.get("/").text
    assert "/static/app.js?v=" in html and "/static/i18n.js?v=" in html


def test_load_report_and_compare(client):
    b = client.post("/api/load", json={"name": "titan"}, headers=H).json()
    assert b["mainSkill"] == "Furious Slam" and b["info"]["ascendancy"] == "Titan"
    r = client.get("/api/report?mode=balanced").json()
    assert r["damageRange"]["high"] > r["damageRange"]["low"] > 0
    assert any(g["title"] == "Слабость к физическим ударам" for g in r["gates"])
    text = client.get("/api/item/Weapon 1 Swap").json()["text"]
    same = client.post("/api/compare", json={"slot": "Weapon 1 Swap", "text": text}, headers=H).json()
    assert abs(same["dps_pct"]) < 1e-6


def test_mechanics_lists_pob_gaps(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    gaps = client.get("/api/mechanics").json()["gaps"]
    assert any("Druidic Prowess" in g["what"] for g in gaps)


def test_bad_profile_is_rejected_without_writing(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    r = client.put("/api/profile", json={"corrections": [{"mod": "not a mod", "uptime": 1}]}, headers=H)
    assert r.status_code == 400 and "не понимает" in r.json()["detail"]


def test_state_changes_need_the_header_and_a_local_host(client):
    assert client.post("/api/load", json={"name": "titan"}).status_code == 403
    assert client.put("/api/llm", json={"provider": "deepseek"}).status_code == 403
    assert client.get("/api/status", headers={"host": "evil.example"}).status_code == 403


def test_llm_settings_store_key_privately(client, settings_dir):
    r = client.put("/api/llm", json={"provider": "deepseek", "api_key": "sk-test-1234567890"}, headers=H).json()
    ds = next(p for p in r["providers"] if p["id"] == "deepseek")
    assert ds["keyHint"] == "…7890" and "sk-test" not in json.dumps(r)
    assert r["active"]["configured"] and r["active"]["model"] == "deepseek-flash"
    stored = json.loads((settings_dir / "poe2lab" / "llm.json").read_text(encoding="utf-8"))
    assert stored["keys"]["deepseek"] == "sk-test-1234567890"
    # empty key keeps the stored one; clear removes it
    client.put("/api/llm", json={"provider": "deepseek", "model": "deepseek-v4-pro"}, headers=H)
    assert json.loads((settings_dir / "poe2lab" / "llm.json").read_text())["keys"]["deepseek"] == "sk-test-1234567890"
    r = client.put("/api/llm", json={"provider": "deepseek", "clear_key": True}, headers=H).json()
    assert not r["active"]["configured"]


def test_llm_settings_validation(client, settings_dir):
    assert client.put("/api/llm", json={"provider": "nope"}, headers=H).status_code == 400
    assert client.put("/api/llm", json={"provider": "custom", "base_url": "ftp://x"}, headers=H).status_code == 400
    ok = client.put("/api/llm", json={"provider": "ollama", "model": "llama3"}, headers=H).json()
    assert ok["active"]["configured"] and ok["active"]["provider"] == "ollama"  # no key needed


def test_chat_without_configuration_explains(client, settings_dir):
    r = client.post("/api/chat", json={"message": "привет"}, headers=H)
    assert r.status_code == 400 and "Ассистент" in r.json()["detail"]


def test_mod_search_finds_parseable_mods_in_both_languages(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    ru = client.get("/api/mods/search", params={"q": "скорость умений"}).json()["results"]
    assert ru[0]["en"] == "#% increased Skill Speed" and ru[0]["line"] == "1% increased Skill Speed"
    en = client.get("/api/mods/search", params={"q": "maximum life"}).json()["results"]
    assert any(r["line"] == "+1 to maximum Life" for r in en)


def test_stale_build_requests_are_refused(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    assert client.get("/api/mechanics", params={"build": "monk"}).status_code == 409
    assert client.get("/api/mechanics", params={"build": "titan"}).status_code == 200


def test_unknown_build_is_a_clean_error(client):
    r = client.post("/api/load", json={"name": "no such build"}, headers=H)
    assert r.status_code == 400


def test_tree_art_is_sent_packed_for_the_browser_to_unpack(client):
    """PoB's tree textures go out as they are, zstd-packed: the browser unpacks them (Content-Encoding)."""
    from poe2lab.web.server import TREE_DATA
    version = sorted(p.name for p in TREE_DATA.iterdir() if (p / "tree.lua").is_file())[-1]
    file = next(p.name for p in (TREE_DATA / version).glob("background_*.dds.zst"))
    url = f"/api/tree/art/{version}/{file}"
    assert client.get(url, headers={"Accept-Encoding": "gzip"}).status_code == 406  # the page then draws without art
    with client.stream("GET", url, headers={"Accept-Encoding": "gzip, deflate, br, zstd"}) as res:
        assert res.status_code == 200 and res.headers["content-encoding"] == "zstd"
        assert b"".join(res.iter_raw())[:4] == bytes.fromhex("28b52ffd")  # a zstd frame, not re-packed
    assert client.get(f"/api/tree/art/{version}/tree.lua").status_code == 404
    assert client.get(f"/api/tree/art/..%2F..%2Fsrc/{file}").status_code == 404
