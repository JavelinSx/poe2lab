"""Updating a build after the character changed in the game: a newer code replaces the old one, the profile and
main skill stay, and the answer lists what changed."""
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poe2lab import library, pobfiles, profile as profile_mod
from poe2lab.analysis.changes import capture, diff
from poe2lab.analysis.threats import MapProfile
from poe2lab.engine import PobEngine
from poe2lab.web import server

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TITAN = (FIXTURES / "titan.txt").read_text().strip()
MONK = (FIXTURES / "monk.txt").read_text().strip()
H = {"X-Poe2lab": "1"}


@pytest.fixture
def builds(tmp_path, monkeypatch):
    """A writable build folder with the titan (and its profile), so tests never touch the fixtures."""
    d = tmp_path / "builds"
    d.mkdir()
    shutil.copy(FIXTURES / "titan.txt", d / "mine.txt")
    shutil.copy(FIXTURES / "titan.profile.json", d / "mine.profile.json")
    for module in (pobfiles, library, profile_mod, server):
        monkeypatch.setattr(module, "PROJECT_BUILDS", d)
    monkeypatch.setattr(library, "TRASH", d / ".trash")
    monkeypatch.setattr(library, "list_pob_builds", lambda: [])
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    return d


def test_replace_keeps_the_name_and_profile(builds):
    library.replace("mine", MONK)
    assert (builds / "mine.txt").read_text().strip() == MONK
    assert (builds / "mine.profile.json").exists()
    (old,) = (builds / ".trash").glob("*mine.txt")
    assert old.read_text().strip() == TITAN
    with pytest.raises(library.LibraryError):
        library.replace("mine", "not a pob code")
    assert (builds / "mine.txt").read_text().strip() == MONK  # a bad code leaves the build alone
    with pytest.raises(library.LibraryError):
        library.replace("nobody", TITAN)


def test_diff_lists_gear_tree_and_stats():
    a, b = PobEngine(), PobEngine()
    a.load_code(TITAN)
    b.load_code(MONK)
    p = MapProfile()
    before = capture(a, p)
    same = diff(before, capture(a, p))
    assert not (same["items"] or same["nodesAdded"] or same["nodesRemoved"] or same["gemsAdded"] or same["gemsRemoved"])
    assert all(r["before"] == r["after"] for r in same["rows"])
    other = diff(before, capture(b, p))
    assert other["class"][0] == "Titan" and other["class"][1] != "Titan"
    assert other["items"] and other["nodesAdded"] and other["nodesRemoved"] and other["gemsAdded"]
    dps = next(r for r in other["rows"] if r["key"] == "dps")
    assert dps["before"] != dps["after"]


def test_reload_endpoint_keeps_profile_and_skill(builds):
    client = TestClient(server.app)
    r = client.post("/api/load", json={"name": "mine"}, headers=H).json()
    assert r["kind"] == "code" and r["mainSkill"] == "Furious Slam"
    assert client.get("/api/status").json()["buildChanged"] is False

    same = client.post("/api/reload", json={}, headers=H).json()  # nothing new: read the file again
    assert same["changes"]["items"] == [] and same["changes"]["skillKept"]

    new = client.post("/api/reload", json={"code": MONK}, headers=H)
    assert new.status_code == 200, new.text
    body = new.json()
    assert body["name"] == "mine" and body["hasProfile"]  # same name, profile kept
    assert body["changes"]["class"][0] == "Titan" and body["changes"]["items"]
    assert body["changes"]["skillBefore"] == "Furious Slam"
    bad = client.post("/api/reload", json={"code": "garbage"}, headers=H)
    assert bad.status_code == 400
