"""Assistant loop with a scripted fake model: context carries the mechanics, tools return engine numbers."""
import json

import pytest

from poe2lab.analysis.threats import MapProfile
from poe2lab.assistant import Assistant, LLMConfig, Toolbox, build_context
from poe2lab.profile import open_build


class FakeClient:
    """Replays assistant messages; records what it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []

    def complete(self, messages, tools=None):
        self.sent.append(json.loads(json.dumps(messages)))
        return self.replies.pop(0)


@pytest.fixture(scope="module")
def titan():
    engine, bp = open_build("titan")
    return engine, bp, MapProfile(rage=bp.rage, mana_sustained=bp.mana_sustained)


def test_context_contains_mechanics_and_confirmed_facts(titan):
    engine, bp, _ = titan
    ctx = build_context(engine, bp)
    assert "Rage regenerated per second" in ctx  # Walking Calamity, from game data
    assert "Druidic Prowess" in ctx  # Amor Mandragora line PoB cannot parse
    assert "мана: держится" in ctx  # player-confirmed fact from the profile
    assert len(ctx) < 60000  # stays a cheap, cacheable prefix


def test_tool_round_trip(titan):
    engine, bp, profile = titan
    fake = FakeClient([
        {"content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {
            "name": "evaluate_mods", "arguments": json.dumps({"mods": ["+13% to Chaos Resistance"]})}}]},
        {"content": "Хаос-резист: +43% к переживаемому удару хаосом."},
    ])
    assistant = Assistant(fake, Toolbox(engine, profile), build_context(engine, bp))
    answer = assistant.ask("Что даст +13% хаос-резиста?")
    assert answer.startswith("Хаос-резист")
    tool_msg = fake.sent[1][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"
    change = json.loads(tool_msg["content"])["percentChange"]["chaos_hit"]
    assert change == pytest.approx(43.3, abs=1.0)


def test_bad_tool_calls_return_errors_not_exceptions(titan):
    engine, _, profile = titan
    box = Toolbox(engine, profile)
    assert "error" in json.loads(box.call("no_such_tool", "{}"))
    assert "error" in json.loads(box.call("evaluate_mods", {"mods": ["not a real mod line"]}))
    assert "error" in json.loads(box.call("propose_profile_change",
                                          {"kind": "correction", "value": "gibberish", "reason": "x"}))
    ok = json.loads(box.call("propose_profile_change", {"kind": "correction", "value": "10% increased Skill Speed",
                                                         "reason": "test"}))
    assert ok["proposal"]["value"] == "10% increased Skill Speed" and box.proposals


def test_config_reads_environment(monkeypatch):
    monkeypatch.delenv("POE2LAB_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert LLMConfig.from_env() is None
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    cfg = LLMConfig.from_env()
    assert cfg.api_key == "k" and cfg.base_url == "https://api.deepseek.com" and cfg.model == "deepseek-flash"
