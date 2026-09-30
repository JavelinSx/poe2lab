"""Connecting poe2lab's MCP server (poe2lab.mcpserver) to the player's own AI app: the command the app runs, the
JSON most apps take, the Claude Code command line, and Claude Desktop's config written on request (the player
presses the button; the file is backed up first, other servers in it are kept)."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from .pobfiles import REPO_ROOT

NAME = "poe2lab"
CONFIG_FILE = "claude_desktop_config.json"


class ConnectError(Exception):
    pass


def server_entry() -> dict:
    """How an AI app starts the server: this Python (the .venv's, which has the dependencies) with the project on
    the path, so it runs whatever folder the app starts it in."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":  # a windowless Python has no stdin/stdout for the app to talk over
        exe = exe.with_name("python.exe")
    return {"command": str(exe), "args": ["-m", "poe2lab", "mcp"], "env": {"PYTHONPATH": str(REPO_ROOT)}}


def claude_desktop_config() -> Path | None:
    """Claude Desktop's config file (it may not exist yet), or None without Claude Desktop. The Microsoft Store
    build reads its own copy of the folder under Packages; the usual one is in %APPDATA%."""
    local, roaming = os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")
    dirs = sorted(Path(local, "Packages").glob("Claude_*/LocalCache/Roaming/Claude")) if local else []
    if roaming:
        dirs.append(Path(roaming, "Claude"))
    return next((d / CONFIG_FILE for d in dirs if d.is_dir()), None)


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError) as err:
        raise ConnectError(f"настройки Claude Desktop не читаются ({err}) — добавь poe2lab вручную") from None
    if not isinstance(data, dict):
        raise ConnectError("настройки Claude Desktop не в том формате — добавь poe2lab вручную")
    return data


def _write(path: Path, data: dict):
    if path.exists():  # the player's file as it was, in case anything goes wrong
        path.with_name(CONFIG_FILE + ".poe2lab.bak").write_bytes(path.read_bytes())
    tmp = path.with_name(CONFIG_FILE + ".poe2lab.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def status() -> dict:
    entry = server_entry()
    path = claude_desktop_config()
    connected = False
    if path is not None:
        try:
            connected = NAME in (_read(path).get("mcpServers") or {})
        except ConnectError:
            pass
    env = " ".join(f'-e {k}="{v}"' for k, v in entry["env"].items())
    return {
        "available": importlib.util.find_spec("mcp") is not None,
        "json": json.dumps({"mcpServers": {NAME: entry}}, ensure_ascii=False, indent=2),
        "claudeCode": f'claude mcp add {NAME} --scope user {env} -- "{entry["command"]}" ' + " ".join(entry["args"]),
        "claudeDesktop": {"found": path is not None, "connected": connected},
    }


def connect() -> dict:
    """Add poe2lab to Claude Desktop's servers (replacing an older entry of ours); Claude Desktop reads it when it
    starts again."""
    path = claude_desktop_config()
    if path is None:
        raise ConnectError("Claude Desktop не найден на этом компьютере")
    problem = check()
    if problem:
        raise ConnectError(f"сервер poe2lab не запускается: {problem}")
    data = _read(path)
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        servers = data["mcpServers"] = {}
    servers[NAME] = server_entry()
    _write(path, data)
    return status()


def disconnect() -> dict:
    path = claude_desktop_config()
    if path is not None and path.exists():
        data = _read(path)
        if NAME in (data.get("mcpServers") or {}):
            del data["mcpServers"][NAME]
            _write(path, data)
    return status()


def check() -> str | None:
    """Whether the server starts at all with this Python (the mcp package importable): None, or why not."""
    if importlib.util.find_spec("mcp") is None:
        return "нет пакета mcp: запусти start.bat ещё раз — он поставит недостающее"
    entry = server_entry()
    r = subprocess.run([entry["command"], "-c", "import poe2lab.mcpserver"], env=os.environ | entry["env"],
                       capture_output=True, text=True, timeout=60, cwd=Path.home(),
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # no console flashing up
    return None if r.returncode == 0 else (r.stderr.strip().splitlines() or ["?"])[-1]
