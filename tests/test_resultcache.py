"""Results kept on disk between runs: found again by the state they come from, worked out anew when it changes."""
import pytest

from poe2lab import resultcache


def test_kept_by_state_and_key(tmp_path, monkeypatch):
    monkeypatch.setenv("POE2LAB_RESULTS", str(tmp_path))
    resultcache.put("s1", ("report", "balanced"), {"dps": 1})
    assert resultcache.get("s1", ("report", "balanced")) == ({"dps": 1}, False)
    assert resultcache.get("s2", ("report", "balanced")) is resultcache.MISS
    assert resultcache.get("s1", ("report", "tank")) is resultcache.MISS
    # what used poe.ninja's prices is kept for a while only
    resultcache.put("s1", ("gear", "balanced"), [1], priced=True)
    assert resultcache.get("s1", ("gear", "balanced")) == ([1], True)
    now = resultcache.time.time()
    monkeypatch.setattr(resultcache.time, "time", lambda: now + resultcache.PRICED_SECONDS + 1)
    assert resultcache.get("s1", ("gear", "balanced")) is resultcache.MISS
    assert resultcache.get("s1", ("report", "balanced")) == ({"dps": 1}, False)
    # what cannot be kept is just not kept; a broken file is a miss
    resultcache.put("s1", ("x",), lambda: 1)
    assert resultcache.get("s1", ("x",)) is resultcache.MISS
    for f in tmp_path.glob("*.pkl"):
        f.write_bytes(b"broken")
    assert resultcache.get("s1", ("report", "balanced")) is resultcache.MISS


def test_the_newest_stay(tmp_path, monkeypatch):
    monkeypatch.setenv("POE2LAB_RESULTS", str(tmp_path))
    for i in range(5):
        resultcache.put("s", ("k", i), "x" * 1000)
    resultcache.prune(limit=2500)
    assert len(list(tmp_path.glob("*.pkl"))) == 2


def test_off_when_empty(monkeypatch):
    monkeypatch.setenv("POE2LAB_RESULTS", "")
    resultcache.put("s", ("k",), 1)
    assert resultcache.get("s", ("k",)) is resultcache.MISS


def test_a_restart_finds_the_build_counted(tmp_path, monkeypatch):
    """The open build's report comes back from disk after a restart (the memory cache gone) - though the report
    left the engine with other skills picked in some groups; another state - a character level, the engine's
    configuration - is worked out anew."""
    from fastapi.testclient import TestClient
    from poe2lab.web import server
    monkeypatch.setenv("POE2LAB_RESULTS", str(tmp_path))
    snapshot = tmp_path / "titan.min.txt"  # one of the build's files (its Мин), outside the fixtures
    monkeypatch.setattr(server.library, "min_path", lambda name: snapshot)
    client = TestClient(server.app)
    h = {"X-Poe2lab": "1"}
    client.post("/api/load", json={"name": "titan"}, headers=h)
    first = client.get("/api/report").json()
    assert list(tmp_path.glob("*.pkl"))
    client.post("/api/load", json={"name": "titan"}, headers=h)  # the memory cache is cleared as on a restart

    def never(*args, **kwargs):
        raise AssertionError("worked out again")
    monkeypatch.setattr(server, "build_report", never)
    assert client.get("/api/report").json() == first
    # a file of the build changed on disk: anew, though nothing in memory was dropped
    snapshot.write_text("changed", encoding="utf-8")
    server.session.cache.pop(("report", "balanced"))
    with pytest.raises(AssertionError):
        client.get("/api/report")
    snapshot.unlink()
    assert client.get("/api/report").json() == first
    server.session.cache.clear()
    server.session.level = (server.session.level or 1) - 1
    with pytest.raises(AssertionError):
        client.get("/api/report")
    client.post("/api/load", json={"name": "titan"}, headers=h)
    server.session.engine.set_config_input({"multiplierRage": 3})
    server.session.cache.clear()  # as every change of the build does (a quest reward, a tree plan...)
    with pytest.raises(AssertionError):
        client.get("/api/report")
