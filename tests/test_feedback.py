"""Bug reports: what the app sends to the feedback relay, and the relay's own checks (worker/, run with node)."""
import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poe2lab import feedback
from poe2lab.engine.pobcode import decode_pob_code
from poe2lab.web import server

ROOT = Path(__file__).resolve().parents[1]
PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 32).decode()
H = {"X-Poe2lab": "1"}


@pytest.fixture
def relay(monkeypatch):
    """A stand-in for the relay: records what would be posted."""
    sent = []

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"ok":true}'

    def urlopen(req, timeout):
        sent.append({"url": req.full_url, "headers": dict(req.header_items()), "body": json.loads(req.data)})
        return Reply()

    monkeypatch.setenv("POE2LAB_FEEDBACK_URL", "https://relay.test/feedback")
    monkeypatch.setattr(feedback.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(feedback, "_last_sent", 0.0)
    return sent


def test_checks_before_sending():
    with pytest.raises(feedback.FeedbackError, match="опиши"):
        feedback.compose(" ", "", [], {}, None, {})
    with pytest.raises(feedback.FeedbackError, match="PNG"):
        feedback.compose("число урона не то", "", ["data:image/png;base64," + base64.b64encode(b"GIF89a").decode()],
                         {}, None, {})
    with pytest.raises(feedback.FeedbackError, match="не больше"):
        feedback.compose("число урона не то", "", [PNG] * 4, {}, None, {})


def test_report_carries_the_open_build(relay):
    client = TestClient(server.app)
    client.post("/api/load", json={"name": "titan"}, headers=H)
    assert client.get("/api/feedback").json()["configured"]
    r = client.post("/api/feedback", headers=H, json={"message": "DPS на вкладке урон не сходится с PoB",
                                                      "contact": "me@example.com", "images": [PNG],
                                                      "tab": "damage", "mode": "balanced", "lang": "ru"})
    assert r.status_code == 200, r.text
    (sent,) = relay
    body = sent["body"]
    assert sent["url"] == "https://relay.test/feedback" and sent["headers"]["X-poe2lab-feedback"] == "1"
    assert body["build"]["name"] == "titan" and "<PathOfBuilding2>" in decode_pob_code(body["build"]["code"])
    assert "planCode" not in body["build"]  # no tree plan open
    assert body["profile"]["corrections"]  # titan has a profile with corrections
    assert body["context"]["tab"] == "damage" and body["context"]["mainSkill"] == "Furious Slam"
    assert body["images"] == [{"type": "png", "data": PNG.split(",", 1)[1]}]
    # a second report right away is held back on this side
    again = client.post("/api/feedback", headers=H, json={"message": "ещё одно сообщение"})
    assert again.status_code == 400 and "через" in again.json()["detail"]


def test_not_configured(monkeypatch):
    monkeypatch.delenv("POE2LAB_FEEDBACK_URL", raising=False)
    monkeypatch.setattr(feedback, "RELAY_URL", "")
    with pytest.raises(feedback.FeedbackError, match="не настроена"):
        feedback.send({})


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_relay_worker():
    res = subprocess.run(["node", "--test", "worker/feedback.test.mjs"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stdout + res.stderr
