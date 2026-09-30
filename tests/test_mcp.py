"""poe2lab over MCP: the assistant's tools for the player's own AI app (poe2lab.mcpserver), and connecting it to
Claude Desktop (poe2lab.mcpconnect) - on a temporary settings folder, never the machine's own."""
import json
import os
import sys
from pathlib import Path

import anyio
import pytest
from fastapi.testclient import TestClient

from poe2lab import library, mcpconnect
from poe2lab.assistant.tools import SPECS
from poe2lab.mcpserver import OWN_TOOLS, TOOL_SPECS, Workbench
from poe2lab.pobfiles import REPO_ROOT
from poe2lab.web.server import app

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_the_tools_are_the_assistant_s():
    names = [s["name"] for s in OWN_TOOLS + TOOL_SPECS]
    assert names[:2] == ["list_builds", "open_build"]
    # the one that proposes a profile change is the interface's: nothing here confirms it
    assert set(names[2:]) == {s["function"]["name"] for s in SPECS} - {"propose_profile_change"}


def test_a_build_is_opened_then_computed():
    bench = Workbench()
    text, error = bench.call("build_report", {})
    assert error and "open_build" in text
    builds = json.loads(bench.call("list_builds", {})[0])
    assert {"titan", "monk"} <= {b["name"] for b in builds}
    # the library's builds only, not any file on the disk
    assert bench.call("open_build", {"name": str(FIXTURES / "titan.txt")})[1]
    text, error = bench.call("open_build", {"name": "titan"})
    assert not error and text.startswith("Opened: titan") and "Furious Slam" in text
    report = json.loads(bench.call("build_report", {"goal": "defence"})[0])
    assert report["baseline"]["dps"] > 0 and set(report["resistances"]) == {"Fire", "Cold", "Lightning", "Chaos"}
    change = json.loads(bench.call("evaluate_mods", {"mods": ["50% increased Attack Speed"]})[0])
    assert change["percentChange"]["dps"] > 10
    text, error = bench.call("slot_plan", {"slot": "Nope"})
    assert error and "Nope" in text


def test_the_player_s_character_follows_its_build(monkeypatch):
    """A build with the player's character in it: the tools compute the character, the build is its guide."""
    monkeypatch.setattr(library, "main_path", lambda name: FIXTURES / ("monk.txt" if name == "titan" else "none.txt"))
    bench = Workbench()
    text, error = bench.call("open_build", {"name": "titan", "lang": "en"})
    assert not error and "the build is its guide" in text and "Whirling Assault" in text
    target = json.loads(bench.call("target_report", {})[0])
    assert target["target"]["name"] == "titan (гайд)" and target["now"]["mainSkill"] != target["target"]["mainSkill"]


def test_an_ai_app_talks_to_it_over_stdio():
    """As Claude Desktop runs it: the command from the settings, in another folder, JSON-RPC over stdin/stdout -
    nothing else may reach stdout."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    entry = mcpconnect.server_entry()
    env = os.environ | entry["env"] | {"POE2LAB_BUILDS": str(FIXTURES)}

    async def talk():
        params = StdioServerParameters(command=entry["command"], args=entry["args"], env=env, cwd=str(Path.home()))
        async with stdio_client(params) as (read, write), ClientSession(read, write) as s:
            init = await s.initialize()
            assert init.server_info.name == "poe2lab" and "Path of Building" in init.instructions
            tools = (await s.list_tools()).tools
            assert all(t.annotations.read_only_hint for t in tools)
            opened = await s.call_tool("open_build", {"name": "monk"})
            assert not opened.is_error and "Whirling Assault" in opened.content[0].text
            found = await s.call_tool("find_mod", {"text": "to Chaos Resistance"})
            assert not found.is_error and json.loads(found.content[0].text)["found"]
            missing = await s.call_tool("compare_item", {"slot": "Helmet"})
            assert missing.is_error

    anyio.run(talk)


@pytest.fixture
def claude_dir(tmp_path, monkeypatch):
    """Claude Desktop's settings folder, in a temporary place."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setattr(mcpconnect, "check", lambda: None)  # the server's own start is the stdio test's
    return tmp_path / "Roaming" / "Claude"


def test_connecting_to_claude_desktop_keeps_the_player_s_settings(claude_dir):
    with pytest.raises(mcpconnect.ConnectError):  # no Claude Desktop here
        mcpconnect.connect()
    claude_dir.mkdir(parents=True)
    config = claude_dir / "claude_desktop_config.json"
    theirs = {"mcpServers": {"other": {"command": "x"}}, "preferences": {"a": 1}}
    config.write_text(json.dumps(theirs), encoding="utf-8")
    assert mcpconnect.status()["claudeDesktop"] == {"found": True, "connected": False}

    st = mcpconnect.connect()
    assert st["claudeDesktop"]["connected"]
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["preferences"] == {"a": 1} and data["mcpServers"]["other"] == {"command": "x"}
    ours = data["mcpServers"]["poe2lab"]
    assert ours["args"] == ["-m", "poe2lab", "mcp"] and ours["env"]["PYTHONPATH"] == str(REPO_ROOT)
    assert json.loads((claude_dir / "claude_desktop_config.json.poe2lab.bak").read_text(encoding="utf-8")) == theirs
    assert "poe2lab" in json.loads(st["json"])["mcpServers"] and "claude mcp add poe2lab" in st["claudeCode"]

    mcpconnect.connect()  # again: still one entry
    assert list(json.loads(config.read_text(encoding="utf-8"))["mcpServers"]) == ["other", "poe2lab"]
    assert not mcpconnect.disconnect()["claudeDesktop"]["connected"]
    assert json.loads(config.read_text(encoding="utf-8")) == theirs


def test_a_settings_file_it_cannot_read_is_left_alone(claude_dir):
    claude_dir.mkdir(parents=True)
    config = claude_dir / "claude_desktop_config.json"
    config.write_text("{broken", encoding="utf-8")
    with pytest.raises(mcpconnect.ConnectError):
        mcpconnect.connect()
    assert config.read_text(encoding="utf-8") == "{broken"


def test_the_store_build_s_folder_comes_first(claude_dir, tmp_path):
    claude_dir.mkdir(parents=True)
    store = tmp_path / "Local" / "Packages" / "Claude_abc" / "LocalCache" / "Roaming" / "Claude"
    store.mkdir(parents=True)
    assert mcpconnect.claude_desktop_config() == store / "claude_desktop_config.json"


def test_the_interface_connects_and_disconnects(claude_dir):
    claude_dir.mkdir(parents=True)
    client = TestClient(app)
    H = {"X-Poe2lab": "1"}
    assert client.get("/api/mcp").json()["claudeDesktop"] == {"found": True, "connected": False}
    assert client.post("/api/mcp/claude-desktop", headers=H).json()["claudeDesktop"]["connected"]
    assert not client.delete("/api/mcp/claude-desktop", headers=H).json()["claudeDesktop"]["connected"]
    assert client.post("/api/mcp/claude-desktop").status_code == 403  # another site's page cannot do it
