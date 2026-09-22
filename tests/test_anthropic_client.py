"""Message conversion for the Anthropic adapter (no network)."""
from poe2lab.assistant.llm import AnthropicClient, LLMConfig


def test_convert_groups_tool_results_and_replays_raw_blocks():
    raw = [{"type": "thinking", "thinking": "", "signature": "s"}, {"type": "tool_use", "id": "t1", "name": "x", "input": {}}]
    messages = [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "t1"}, {"id": "t2"}], "_raw": raw},
        {"role": "tool", "tool_call_id": "t1", "content": "r1"},
        {"role": "tool", "tool_call_id": "t2", "content": "r2"},
        {"role": "assistant", "content": "done"},
    ]
    system, out = AnthropicClient._convert(messages)
    assert system == "rules"
    assert out[1] == {"role": "assistant", "content": raw}  # thinking + tool_use replayed unchanged
    assert out[2]["role"] == "user" and [b["tool_use_id"] for b in out[2]["content"]] == ["t1", "t2"]
    assert out[3] == {"role": "assistant", "content": "done"}


def test_config_kind_by_provider():
    assert LLMConfig("k", provider="anthropic").kind == "anthropic"
    assert LLMConfig("k", provider="deepseek").kind == "openai"
