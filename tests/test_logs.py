"""poe2lab's own log (poe2lab.logs): errors with their traceback under a code, the page's errors, the end of the
log to send with a report - the home folder hidden."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poe2lab import logs
from poe2lab.web import server


@pytest.fixture
def client():
    return TestClient(server.app, raise_server_exceptions=False)


def flush():
    for h in logs.log.handlers:
        h.flush()


def test_an_unexpected_error_is_logged_with_a_code(client, monkeypatch):
    def broken():
        raise RuntimeError("nothing expected this")
    monkeypatch.setattr(server, "log_file", broken)
    r = client.get("/api/log", headers={"X-Poe2lab": "1"})
    assert r.status_code == 500
    body = r.json()
    assert body["errorId"] and "RuntimeError: nothing expected this" in body["detail"]
    flush()
    text = logs.log_file().read_text(encoding="utf-8")
    assert f"failed [{body['errorId']}]" in text and "Traceback" in text


def test_the_page_errors_go_into_the_log(client):
    r = client.post("/api/log", json={"message": "x is undefined", "stack": "at draw (app.js:1)", "tab": "overview"},
                    headers={"X-Poe2lab": "1"})
    assert r.status_code == 200
    flush()
    assert "page error on overview: x is undefined" in logs.log_file().read_text(encoding="utf-8")
    r = client.get("/api/log", headers={"X-Poe2lab": "1"})
    assert "x is undefined" in r.json()["text"]


def test_the_tail_hides_the_home_folder_and_starts_on_a_line():
    logs.log.error("open %s", Path.home() / "secret" / "build.txt")
    flush()
    text = logs.tail()
    assert str(Path.home()) not in text and "~" in text
    short = logs.tail(60)
    assert len(short) <= 60 and not short.startswith(" ")


def test_a_failed_part_of_the_report_leaves_the_rest(monkeypatch):
    from poe2lab.analysis import attributes, report
    from poe2lab.analysis.threats import MapProfile
    from poe2lab.profile import open_build
    engine, bp = open_build("titan")

    def broken(*a, **k):
        raise ZeroDivisionError("division by zero")
    monkeypatch.setattr(attributes, "node_swaps", broken)
    r = report.build_report(engine, MapProfile(rage=bp.rage), mode="balanced", steps=1)
    assert r["failed"] == ["nodeSwaps"] and r["baseline"]["dps"] > 0 and r["attributes"]["nodeSwaps"] == []
    flush()
    assert "report part nodeSwaps failed" in logs.log_file().read_text(encoding="utf-8")
