"""The build list the UI manages: adding a build from a PoB code or a pobb.in link, favourites, removal.

Builds added here are PoB codes in builds/<name>.txt. Removing one moves it (and its profile) to builds/.trash, so a
mistake can be undone by moving the file back. Builds saved inside PoB are PoB's files: they are only hidden from
the list, never deleted. Favourites and hidden builds live next to the other per-user settings
(%APPDATA%/poe2lab/library.json)."""
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

from .engine.pobcode import decode_pob_code
from .pobfiles import PROJECT_BUILDS, list_pob_builds

TRASH = PROJECT_BUILDS / ".trash"
_NAME = re.compile(r"^[\w\- .()]{1,60}$")  # \w covers Cyrillic; no path separators
_POBB = re.compile(r"^https?://pobb\.in/([A-Za-z0-9_-]+)/?$")
USER_AGENT = "poe2lab/0.1 (personal build analysis tool; github.com/JavelinSx/poe2lab)"


class LibraryError(ValueError):
    pass


def _path() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(root) / "poe2lab" / "library.json"


def _load() -> dict:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {"favorites": data.get("favorites", []), "hidden": data.get("hidden", [])}


def _save(data: dict):
    _path().parent.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def entries() -> list[dict]:
    """Every build the UI lists: favourites first, then PoB-saved (newest first) and codes; hidden ones left out."""
    lib = _load()
    out = [{"name": p.stem, "kind": "pob", "file": str(p)} for p in list_pob_builds() if str(p) not in lib["hidden"]]
    out += [{"name": p.stem, "kind": "code", "file": str(p)} for p in sorted(PROJECT_BUILDS.glob("*.txt"))]
    for b in out:
        b["favorite"] = b["name"] in lib["favorites"]
        b["hasProfile"] = (PROJECT_BUILDS / f"{b['name']}.profile.json").exists()
    out.sort(key=lambda b: not b["favorite"])  # stable: keeps the order inside each group
    return out


def hidden_count() -> int:
    return len(_load()["hidden"])


def fetch_code(text: str) -> str:
    """The PoB code itself, or the code behind a pobb.in link."""
    text = text.strip()
    m = _POBB.match(text)
    if not m:
        return text
    req = urllib.request.Request(f"https://pobb.in/{m.group(1)}/raw", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.read().decode("utf-8").strip()
    except OSError as err:
        raise LibraryError(f"не удалось скачать билд с pobb.in: {err}") from None


def describe_code(code: str) -> dict:
    """Class, ascendancy and level from a PoB code; LibraryError if it is not one."""
    try:
        root = ElementTree.fromstring(decode_pob_code(code))
    except Exception:
        raise LibraryError("это не PoB-код: в PoB — Import/Export Build → Generate → Copy") from None
    build = root.find("Build")
    if build is None:
        raise LibraryError("в коде нет билда (раздел Build)")
    return {"class": build.get("className", ""), "ascendancy": build.get("ascendClassName", ""),
            "level": int(build.get("level", 0) or 0)}


def _taken(name: str) -> bool:
    return any(b["name"].lower() == name.lower() for b in entries()) or (PROJECT_BUILDS / f"{name}.txt").exists()


def add(name: str, text: str) -> str:
    """Save a build under `name` (empty: ascendancy and level from the code) and return the name used."""
    code = fetch_code(text)
    info = describe_code(code)
    name = (name or "").strip()
    if not name:
        base = f"{info['ascendancy'] or info['class'] or 'build'} {info['level']}".strip()
        name, n = base, 2
        while _taken(name):
            name, n = f"{base} ({n})", n + 1
    if not _NAME.match(name) or name.startswith("."):
        raise LibraryError("имя: буквы, цифры, пробел, - _ . ( ), до 60 символов")
    if _taken(name):
        raise LibraryError(f"билд «{name}» уже есть — выберите другое имя")
    PROJECT_BUILDS.mkdir(exist_ok=True)
    (PROJECT_BUILDS / f"{name}.txt").write_text(code + "\n", encoding="utf-8")
    return name


def remove(name: str) -> str:
    """A code build goes to builds/.trash with its profile; a PoB-saved build is hidden. Returns what happened."""
    entry = next((b for b in entries() if b["name"] == name), None)
    if entry is None:
        raise LibraryError(f"нет билда «{name}»")
    lib = _load()
    if name in lib["favorites"]:
        lib["favorites"].remove(name)
    if entry["kind"] == "pob":
        lib["hidden"].append(entry["file"])
        _save(lib)
        return "hidden"
    TRASH.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for src in (PROJECT_BUILDS / f"{name}.txt", PROJECT_BUILDS / f"{name}.profile.json"):
        if src.exists():
            src.replace(TRASH / f"{stamp} {src.name}")  # a timestamp prefix: removing twice never overwrites
    _save(lib)
    return "trashed"


def replace(name: str, text: str):
    """A newer PoB code (or pobb.in link) for a code build: the name, profile and favourite stay, the old code goes
    to builds/.trash. PoB-saved builds are updated in PoB itself, so they are refused here."""
    path = PROJECT_BUILDS / f"{name}.txt"
    if not path.exists():
        raise LibraryError(f"«{name}» сохранён в самом PoB: обнови его там (Import → персонаж → Save) и нажми "
                           "«обновить» ещё раз" if any(b["name"] == name for b in entries()) else f"нет билда «{name}»")
    code = fetch_code(text)
    describe_code(code)
    TRASH.mkdir(parents=True, exist_ok=True)
    path.replace(TRASH / f"{time.strftime('%Y%m%d-%H%M%S')} {path.name}")
    path.write_text(code + "\n", encoding="utf-8")


def set_favorite(name: str, favorite: bool):
    lib = _load()
    if favorite and name not in lib["favorites"]:
        lib["favorites"].append(name)
    if not favorite and name in lib["favorites"]:
        lib["favorites"].remove(name)
    _save(lib)


def unhide_all():
    lib = _load()
    lib["hidden"] = []
    _save(lib)
