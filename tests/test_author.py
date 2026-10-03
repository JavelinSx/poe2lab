"""The build author's constructor: one search over everything the game has, tokens in texts, blocks kept in the
build's profile (a temp copy of the test builds: the fixtures' own profiles stay as they are)."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poe2lab import author

H = {"X-Poe2lab": "1"}
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_tokens_and_blocks_are_checked():
    assert author.tokens("Бей [[gem:Ice Strike]], босса — [[gem:Tempest Bell]]; [[passive:123|Flow Like Water]]") == [
        ("gem", "Ice Strike"), ("gem", "Tempest Bell"), ("passive", "123|Flow Like Water")]
    doc = author.set_block(None, "lv:act1:skills", {"list": ["gem:Ice Strike", "gem:Ice Strike", "unique:Astramentis"]})
    assert doc["blocks"]["lv:act1:skills"] == {"list": ["gem:Ice Strike", "unique:Astramentis"]}
    doc = author.set_block(doc, "sk:Ice Strike", {"text": "  копи комбо  "})
    assert doc["blocks"]["sk:Ice Strike"] == {"text": "копи комбо"}
    # an emptied block goes away
    assert "sk:Ice Strike" not in author.set_block(doc, "sk:Ice Strike", {"text": ""})["blocks"]
    for bad_id, block in (("<script>", {"text": "x"}), ("sk:x", {"list": ["nothing"]}), ("sk:x", {"text": 5}),
                          ("sk:x", {"text": "x" * (author.MAX_TEXT + 1)}), ("sk:x", {"list": ["gem:a"] * 41})):
        with pytest.raises(author.AuthorError):
            author.set_block(doc, bad_id, block)


def test_search_ranks_whole_and_starting_names_first():
    index = author.build_index(
        gems=[{"name": "Ice Strike", "support": False}, {"name": "Ice Nova", "support": False},
              {"name": "Ice Bite", "support": True}],
        uniques=[{"name": "Ice Breaker", "base": "Ring"}], bases=[{"name": "Iron Ring", "type": "Ring"}],
        runes=[], nodes=[{"id": 5, "name": "Price of Ice", "type": "Notable"}, {"id": 6, "name": "Ice", "type": "Normal"}],
        terms={}, names={"Ice Strike": "Ледяной удар", "Ice Nova": "Кольцо льда"})
    assert [r["id"] for r in author.search(index, "ice strike")] == ["Ice Strike"]
    assert author.search(index, "ледяной")[0]["id"] == "Ice Strike"  # the local name too
    found = [r["id"] for r in author.search(index, "ice")]
    assert found[:2] == ["Ice Nova", "Ice Strike"] and "5|Price of Ice" in found and "6|Ice" not in found
    assert [r["kind"] for r in author.search(index, "ice", ["support"])] == ["support"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    from poe2lab import library, pobfiles, profile
    from poe2lab.web import server
    for name in ("titan.txt", "titan.profile.json"):
        if (FIXTURES / name).exists():
            shutil.copy(FIXTURES / name, tmp_path / name)
    for module in (library, pobfiles, profile, server):
        if hasattr(module, "PROJECT_BUILDS"):
            monkeypatch.setattr(module, "PROJECT_BUILDS", tmp_path)
    monkeypatch.setattr(library, "TRASH", tmp_path / ".trash")
    with TestClient(server.app) as c:
        yield c, tmp_path
    server.session.engine = None


def test_the_constructor_on_a_build(client):
    c, folder = client
    assert c.post("/api/load", json={"name": "titan"}, headers=H).status_code == 200
    gems = c.get("/api/lookup", params={"q": "furious slam"}).json()
    assert gems[0] == gems[0] | {"kind": "gem", "id": "Furious Slam"}
    for kind in ("gem", "support", "unique", "base", "rune", "passive", "term"):
        assert c.get("/api/lookup", params={"q": "a", "kinds": kind}).json(), kind
    base = c.get("/api/lookup", params={"q": "quarterstaff", "kinds": "base"}).json()[0]
    assert c.get("/api/lookup/item", params={"kind": "base", "id": base["id"]}).json()["type"] == "Staff"
    uniq = c.get("/api/lookup", params={"q": "astramentis", "kinds": "unique"}).json()
    assert uniq and uniq[0]["kind"] == "unique"
    card = c.get("/api/lookup/item", params={"kind": "unique", "id": uniq[0]["id"]}).json()
    assert card["lines"] and card["base"]
    runes = c.get("/api/lookup", params={"q": "rune", "kinds": "rune"}).json()
    assert runes and c.get("/api/lookup/item", params={"kind": "rune", "id": runes[0]["id"]}).json()["targets"]
    passive = c.get("/api/lookup", params={"q": "a", "kinds": "passive"}).json()[0]
    node = c.get("/api/lookup/item", params={"kind": "passive", "id": passive["id"]}).json()
    assert node["name"] == passive["en"] and "stats" in node
    # a block saved into the profile, the profile's other answers kept
    before = json.loads((folder / "titan.profile.json").read_text(encoding="utf-8"))
    r = c.put("/api/author/block", json={"id": "sk:Furious Slam", "text": "Набери свирепость: [[gem:Furious Slam]]"},
              headers=H)
    assert r.status_code == 200
    assert c.get("/api/author").json()["blocks"]["sk:Furious Slam"]["text"].endswith("[[gem:Furious Slam]]")
    after = json.loads((folder / "titan.profile.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in after.items() if k != "author"} == before
    # what the page saves from the profile tab leaves the author's blocks
    c.put("/api/profile", json=before, headers=H)
    assert c.get("/api/author").json()["blocks"]
    assert c.put("/api/author/block", json={"id": "sk:x", "list": ["bad"]}, headers=H).status_code == 400
