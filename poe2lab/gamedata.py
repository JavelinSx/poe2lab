"""Official texts in the player's language, read from the installed game.

The game keeps every language side by side: stat descriptions (.csd) carry a `lang "Russian"` block under each
English one, and data/balance/russian/*.datc64 are the translated copies of the tables. PoB ships only the English
side. This module unpacks what we need with bun_extract_file (zao/ooz, the extractor PoB's own exporter uses),
builds Russian copies of PoB's stat-description files so PoB's describer can speak Russian, and an English → Russian
name map for skills, areas, buffs, item bases and leagues."""
import json
import os
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUN = ROOT / "tools" / "ooz" / "bun_extract_file.exe"
SPEC = ROOT / "pob2" / "src" / "Export" / "spec.lua"
GAME_CACHE = ROOT / "data" / "cache" / "game"
RAW = GAME_CACHE / "raw"
STEAM_DIRS = [Path(r"C:\Program Files (x86)\Steam\steamapps\common\Path of Exile 2"),
              Path(r"C:\Program Files (x86)\Grinding Gear Games\Path of Exile 2")]

LANG_NAMES = {"ru": "Russian"}
TABLES = {  # table -> (key column, text columns)
    "activeskills": ("Id", ["DisplayName", "Description"]),
    "worldareas": ("Id", ["Name"]),
    "baseitemtypes": ("Id", ["Name"]),
    "buffdefinitions": ("Id", ["Name"]),
    "leaguenames": ("Id", ["Name1"]),
    "passiveskills": ("Id", ["Name"]),
}
# Names PoB shows that no table holds under the same English text (PoB's own labels for game things).
MANUAL_NAMES = {"ru": {"Thorns": "Шипы"}}
TYPE_SIZE = {"Bool": 1, "Int": 4, "UInt": 4, "UInt16": 2, "Float": 4, "Enum": 4, "Interval": 8, "String": 8,
             "ShortKey": 8, "Key": 16}


class GameDataError(RuntimeError):
    pass


BUN_URL = "https://github.com/zao/ooz/releases/download/v0.2.4/bun-0.2.4-x64-Release.zip"


def ensure_bun() -> Path:
    """The bundle extractor PoB's own exporter uses (zao/ooz); downloaded once into tools/ooz."""
    if BUN.is_file():
        return BUN
    import io
    import urllib.request
    import zipfile
    print(f"downloading {BUN_URL} (~0.3 MB)...")
    with urllib.request.urlopen(urllib.request.Request(BUN_URL, headers={"User-Agent": "poe2lab"}), timeout=120) as res:
        data = res.read()
    BUN.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(BUN.parent)
    if not BUN.is_file():
        raise GameDataError(f"в архиве {BUN_URL} нет {BUN.name}")
    return BUN


def _settings_path() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(root) / "poe2lab" / "game.json"


def saved_game_dir() -> Path | None:
    """The game folder the player chose in the interface, if any."""
    try:
        d = json.loads(_settings_path().read_text(encoding="utf-8")).get("dir")
    except (OSError, ValueError):
        return None
    return Path(d) if d else None


def is_game_dir(d: Path) -> bool:
    return (d / "Bundles2").is_dir() or (d / "Content.ggpk").is_file()


def save_game_dir(d: Path):
    if not is_game_dir(d):
        raise GameDataError(f"в папке {d} нет файлов игры (ни Bundles2, ни Content.ggpk) — нужна папка, где лежит "
                            "PathOfExileSteam.exe или PathOfExile.exe")
    _settings_path().parent.mkdir(parents=True, exist_ok=True)
    _settings_path().write_text(json.dumps({"dir": str(d)}, ensure_ascii=False), encoding="utf-8")


def _steam_libraries() -> list[Path]:
    """Every Steam library folder: Steam's own list (libraryfolders.vdf), found through the registry."""
    roots = [Path(r"C:\Program Files (x86)\Steam")]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            roots.insert(0, Path(winreg.QueryValueEx(key, "SteamPath")[0]))
    except (ImportError, OSError):
        pass
    out = []
    for root in roots:
        vdf = root / "steamapps" / "libraryfolders.vdf"
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            lib = Path(m.group(1).replace("\\\\", "\\"))
            if lib not in out:
                out.append(lib)
    return out


def find_game() -> tuple[Path | None, str | None]:
    """The PoE2 install and where it was found: POE2_DIR, the folder chosen in the interface, any Steam library,
    the standalone client's default folder."""
    candidates = []
    if os.environ.get("POE2_DIR"):
        candidates.append((Path(os.environ["POE2_DIR"]), "env"))
    if saved_game_dir():
        candidates.append((saved_game_dir(), "settings"))
    candidates += [(lib / "steamapps" / "common" / "Path of Exile 2", "steam") for lib in _steam_libraries()]
    candidates += [(d, "steam" if "Steam" in str(d) else "ggg") for d in STEAM_DIRS]
    for d, source in candidates:
        if is_game_dir(d):
            return d, source
    return None, None


def game_dir() -> Path | None:
    return find_game()[0]


last_error: str | None = None  # the last failed unpack, for the interface


def status(lang: str = "ru") -> dict:
    """What the Russian texts need and what is missing, for the interface to explain."""
    game, source = find_game()
    return {"game": str(game) if game else None, "gameSource": source, "extractor": BUN.is_file(),
            "unpacked": available(lang) and names_path(lang).is_file(),
            "stale": bool(game) and stale(lang, game), "error": last_error}


def extract(game: Path, lang: str = "ru"):
    """Unpack stat descriptions and the name tables (English and `lang`) into data/cache/game/raw."""
    if not BUN.is_file():
        raise GameDataError(f"нет {BUN.relative_to(ROOT)} — скачайте bun с github.com/zao/ooz/releases")
    folder = LANG_NAMES[lang].lower()
    names = "|".join(TABLES)
    patterns = [r"^data/statdescriptions/.*\.csd$", rf"^data/balance/({folder}/)?({names})\.datc64$"]
    RAW.mkdir(parents=True, exist_ok=True)
    res = subprocess.run([str(BUN), "extract-files", "--regex", str(game), str(RAW), *patterns],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise GameDataError(f"bun_extract_file: {res.stderr.strip() or res.stdout.strip()}")


# ---------- .datc64 tables ----------

def _spec(table: str) -> list[tuple[str, str, bool]]:
    text = SPEC.read_text(encoding="utf-8")
    m = re.search(rf"\n\t{table}=\{{(.*?)\n\t\}},?\n", text, re.S)
    if not m:
        raise GameDataError(f"в spec.lua нет таблицы {table}")
    cols = re.findall(r'list=(true|false),\s*name="([^"]*)",\s*refTo="[^"]*",\s*type="([^"]+)"', m.group(1))
    return [(name, typ, lst == "true") for lst, name, typ in cols]


def _read_string(raw: bytes, pos: int) -> str:
    end = pos
    while end + 1 < len(raw) and raw[end:end + 2] != b"\0\0":
        end += 2
    return raw[pos:end].decode("utf-16-le", errors="replace")


def read_table(path: Path, columns: list[str]) -> list[dict]:
    """Rows of a .datc64 file, only the requested String columns."""
    table = path.stem
    offsets, off = {}, 0
    for name, typ, is_list in _spec(table):
        offsets[name] = (off, typ, is_list)
        off += 16 if is_list else TYPE_SIZE[typ]
    raw = path.read_bytes()
    rows = struct.unpack_from("<I", raw)[0]
    data = raw.find(b"\xbb" * 8, 4)
    if rows == 0 or data < 0:
        return []
    size = (data - 4) // rows
    out = []
    for i in range(rows):
        base = 4 + i * size
        row = {}
        for c in columns:
            o, typ, is_list = offsets[c]
            if typ != "String" or is_list:
                raise GameDataError(f"{table}.{c}: читаю только строки")
            if o + 8 > size:  # the game has fewer columns than the spec: schema drift
                raise GameDataError(f"{table}: схема spec.lua не совпадает с файлом игры")
            row[c] = _read_string(raw, data + struct.unpack_from("<Q", raw, base + o)[0])
        out.append(row)
    return out


def build_names(lang: str = "ru") -> dict[str, str]:
    """English display name → name in `lang`, joined by row id across the two copies of each table."""
    folder = LANG_NAMES[lang].lower()
    out = {}
    for table, (key, cols) in TABLES.items():
        en_path, loc_path = RAW / "data/balance" / f"{table}.datc64", RAW / "data/balance" / folder / f"{table}.datc64"
        if not en_path.is_file() or not loc_path.is_file():
            continue
        loc = {r[key]: r for r in read_table(loc_path, [key, *cols])}
        for r in read_table(en_path, [key, *cols]):
            for col in cols:
                en, tr = _unescape(r[col]).strip(), _unescape(loc.get(r[key], {}).get(col, "")).strip()
                if en and tr and en != tr:
                    out.setdefault(en, tr)
                    if en.startswith("The "):  # PoB drops the article from area names: "Act 2: Spires of Deshar"
                        out.setdefault(en[4:], tr)
    for en, tr in MANUAL_NAMES.get(lang, {}).items():
        out.setdefault(en, tr)
    return out


# ---------- stat descriptions ----------

def _unescape(text: str) -> str:
    """GGG markup → plain text, like PoB's escapeGGGString: [Tag|shown] → shown, [Tag] → Tag."""
    text = re.sub(r"<[^>]+>\{([^}]+)\}", r"\1", text)
    text = re.sub(r"\[([^|\]]+)\]", r"\1", text)
    return re.sub(r"\[[^|\]]+\|([^|\]]+)\]", r"\1", text)


_LINE = re.compile(r'^([\d\-#| !]+?)\s*([A-Za-z_]\w*)?\s*"(.*)"\s*(.*)$')


def _parse_limit(token: str):
    if token == "#":
        return ["#", "#"]
    if re.fullmatch(r"-?\d+", token):
        return [int(token), int(token)]
    m = re.fullmatch(r"!(-?\d+)", token)
    if m:
        return ["!", int(m.group(1))]
    lo, hi = token.split("|", 1)
    num = lambda x: int(x) if re.fullmatch(r"-?\d+", x) else "#"  # a stray "-" in game data means "any"
    return [num(lo), num(hi)]


def parse_csd(text: str, lang: str) -> dict:
    """A .csd file in PoB's Data/StatDescriptions layout, texts taken from `lang` (English where it has none)."""
    want = LANG_NAMES[lang]
    out: dict = {"entries": [], "index": {}, "parent": None}
    cur = None  # current descriptor
    block = None  # "en", "want" or None (another language)
    pending = ""
    for line in text.splitlines():
        line = (pending + line).strip() if pending else line.strip()
        pending = ""
        if not line:
            continue
        m = re.match(r'include "Data/StatDescriptions/(.+)\.csd"$', line, re.I)
        if m:
            out["parent"] = m.group(1).replace("\\", "/").replace("/statset", "_statset")
            continue
        m = re.match(r"no_description ([\w+\-%]+)", line)
        if m:
            out["entries"].append({"stats": [m.group(1)]})
            out["index"][m.group(1)] = len(out["entries"])
            continue
        if line.startswith("handed_description") or line == "description" or line.startswith("description "):
            cur = {"en": [], "want": None, "stats": None}
            out["entries"].append(cur)
            block = "en"
            continue
        if cur is None:
            continue
        if cur["stats"] is None:
            m = re.match(r"\d+\s+([\w+\-% ]+)$", line)
            if m:
                cur["stats"] = m.group(1).split()
                for s in cur["stats"]:
                    out["index"][s] = len(out["entries"])
            else:
                pending = line + " "
            continue
        m = re.match(r'lang "(.+)"', line)
        if m:
            block = "want" if m.group(1) == want else None
            if block == "want":
                cur["want"] = []
            continue
        if block is None or "table_only" in line:
            continue
        m = _LINE.match(line)
        if not m:
            continue
        limits, quality, body, special = m.groups()
        desc = {"text": _unescape(body).replace("\\n", "\n"), "limit": [_parse_limit(t) for t in limits.split()]}
        tokens = special.split()
        specs, i = [], 0
        while i < len(tokens):
            if tokens[i] == "canonical_line":
                specs.append({"k": "canonical_line", "v": True})
                i += 1
            elif i + 1 < len(tokens):
                v = tokens[i + 1]
                specs.append({"k": tokens[i], "v": int(v) if re.fullmatch(r"-?\d+", v) else v})
                i += 2
            else:
                i += 1
        desc["specs"] = specs
        if quality and "gem_quality" in quality:
            desc["gem_quality"] = True
        cur[block].append(desc)
    return out


def _lua(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def to_lua(parsed: dict) -> str:
    """Same shape as PoB's generated files, so PoB's StatDescriber reads them unchanged."""
    parts = ["return {"]
    if parsed["parent"]:
        parts.append(f"parent={_lua(parsed['parent'])},")
    for i, e in enumerate(parsed["entries"], 1):
        stats = "{" + ",".join(_lua(s) for s in (e.get("stats") or [])) + "}"
        if "en" not in e:  # no_description
            parts.append(f"[{i}]={{stats={stats}}},")
            continue
        lines = e["want"] if e["want"] else e["en"]
        descs = []
        for d in lines:
            limit = "{" + ",".join("{" + ",".join(_lua(x) for x in lim) + "}" for lim in d["limit"]) + "}"
            specs = "".join(f"{{k={_lua(s['k'])},v={_lua(s['v'])}}}," for s in d["specs"])
            q = "gem_quality=true," if d.get("gem_quality") else ""
            descs.append(f"{{{specs}{q}limit={limit},text={_lua(d['text'])}}}")
        parts.append(f"[{i}]={{[1]={{{','.join(descs)}}},stats={stats}}},")
    for stat, idx in parsed["index"].items():
        parts.append(f"[{_lua(stat)}]={idx},")
    parts.append("}")
    return "\n".join(parts)


def statdesc_dir(lang: str) -> Path:
    return GAME_CACHE / lang / "StatDescriptions"


def build_statdesc(lang: str = "ru") -> int:
    """Russian copies of PoB's Data/StatDescriptions (same file names, Specific_Skill_Stat_Descriptions flattened
    like PoB's exporter does)."""
    src = RAW / "data" / "statdescriptions"
    dst = statdesc_dir(lang)
    count = 0
    for csd in src.rglob("*.csd"):
        rel = csd.relative_to(src).with_suffix("").as_posix()
        if rel.startswith("specific_skill_stat_descriptions/"):
            rest = rel.split("/", 1)[1]
            nested = "/" in rest
            out = dst / "Specific_Skill_Stat_Descriptions" / (rest.replace("/", "_") + ".lua")
            if not nested:
                out = dst / "Specific_Skill_Stat_Descriptions" / (rest + ".lua")
        else:
            out = dst / (rel + ".lua")
        out.parent.mkdir(parents=True, exist_ok=True)
        text = csd.read_bytes().decode("utf-16")
        out.write_text(to_lua(parse_csd(text, lang)), encoding="utf-8")
        count += 1
    return count


_PLACEHOLDER = re.compile(r"\{(\d*)(?::[+-]?d)?\}")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _tokens(text: str) -> list:
    """Placeholders and literal numbers in reading order: what a printed line's numbers correspond to."""
    out = []
    for m in re.finditer(rf"{_PLACEHOLDER.pattern}|{_NUMBER.pattern}", text):
        out.append(("p", int(m.group(1) or 0)) if m.group(0).startswith("{") else ("n", m.group(0)))
    return out


def _hashed(text: str) -> str:
    return _NUMBER.sub("#", _PLACEHOLDER.sub("#", text))


def build_templates(lang: str = "ru") -> dict[str, str]:
    """Line templates from the game's own descriptions, in the trade-template form the UI already uses
    ({stat_key(English): translated with '#'}). Kept only where the translation has the same numbers in the same
    order, so filling a printed line's numbers in order is exact; that covers "reduced" wordings the trade data
    lacks and lines PoB cannot parse."""
    from .i18n import stat_key  # i18n imports this module; import here to keep the dependency one-way at load
    out: dict[str, str] = {}
    for csd in sorted((RAW / "data" / "statdescriptions").rglob("*.csd")):
        parsed = parse_csd(csd.read_bytes().decode("utf-16"), lang)
        for e in parsed["entries"]:
            if not e.get("want"):
                continue
            for en in e["en"]:
                same = [w for w in e["want"] if w["limit"] == en["limit"] and w["specs"] == en["specs"]]
                if not same:
                    continue
                en_lines, tr_lines = en["text"].split("\n"), same[0]["text"].split("\n")
                # PoB prints a multi-line description either as one line or line by line: keep both forms
                pairs = [(" ".join(en_lines), " ".join(tr_lines))]
                if len(en_lines) > 1 and len(en_lines) == len(tr_lines):
                    pairs += list(zip(en_lines, tr_lines))
                for en_text, tr_text in pairs:
                    if _tokens(en_text) == _tokens(tr_text):
                        out.setdefault(stat_key(_hashed(en_text)), _hashed(tr_text))
    return out


def templates_path(lang: str) -> Path:
    return GAME_CACHE / lang / "templates.json"


def load_templates(lang: str) -> dict[str, str]:
    p = templates_path(lang)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def names_path(lang: str) -> Path:
    return GAME_CACHE / lang / "names.json"


def build(lang: str = "ru", game: Path | None = None) -> dict:
    """Unpack from the game and rebuild everything for `lang`."""
    game = game or game_dir()
    if game is None:
        raise GameDataError("не нашёл установленную Path of Exile 2 (задайте POE2_DIR)")
    extract(game, lang)
    files = build_statdesc(lang)
    names = build_names(lang)
    names_path(lang).parent.mkdir(parents=True, exist_ok=True)
    templates = build_templates(lang)
    templates_path(lang).write_text(json.dumps(templates, ensure_ascii=False, indent=0, sort_keys=True),
                                    encoding="utf-8")
    from . import icons  # icons read this module's tables; imported here to keep the dependency one-way
    icon_info = icons.build(game)
    # names.json last: its time marks a finished unpack (see stale)
    names_path(lang).write_text(json.dumps(names, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    return {"statFiles": files, "names": len(names), "templates": len(templates), "icons": icon_info["icons"],
            "game": str(game)}


def load_names(lang: str) -> dict[str, str]:
    p = names_path(lang)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def available(lang: str) -> bool:
    return (statdesc_dir(lang) / "stat_descriptions.lua").is_file()


def stale(lang: str, game: Path | None = None) -> bool:
    """Not unpacked yet, or the game was patched after unpacking (its bundle index is newer)."""
    if not available(lang) or not names_path(lang).is_file():
        return True
    game = game or game_dir()
    index = game / "Bundles2" / "_.index.bin" if game else None
    return bool(index and index.is_file() and index.stat().st_mtime > names_path(lang).stat().st_mtime)
