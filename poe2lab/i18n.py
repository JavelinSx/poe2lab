"""Official game texts in other languages, from GGG's trade data (the same wording as the localized client).

Stats share ids across languages, so every stat template maps exactly; currency/runes/essences share ids too;
base types, uniques and gems are listed in the same order per category and are aligned by structure.
Cached on disk for a week."""
import difflib
import json
import re
import time
import urllib.request
from pathlib import Path

from .gamedata import load_names, load_templates

HOSTS = {"en": "https://www.pathofexile.com", "ru": "https://ru.pathofexile.com"}
USER_AGENT = "poe2lab/0.1 (personal build analysis tool; github.com/JavelinSx/poe2lab)"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache" / "trade"
CACHE_SECONDS = 7 * 24 * 3600

_RANGE = r"\(\s*-?\d+(?:\.\d+)?\s*-\s*-?\d+(?:\.\d+)?\s*\)"
_TOKEN = re.compile(rf"[+-]?{_RANGE}|[+-]?\d+(?:\.\d+)?")


def stat_key(text: str) -> str:
    """Template key: numbers and ranges become '#', a leading sign is dropped (the game prints it from the value)."""
    return re.sub(r"\s+", " ", _TOKEN.sub("#", text).replace("+#", "#")).strip().lower()


def fill(template: str, line: str) -> str:
    """Put the numbers of `line` into the translated `template`, in order."""
    tokens = _TOKEN.findall(line)
    if template.count("#") != len(tokens):
        return ""
    out, it = [], iter(tokens)
    for i, ch in enumerate(template):
        if ch != "#":
            out.append(ch)
            continue
        tok = next(it)
        signed_in_template = i > 0 and template[i - 1] in "+-"
        out.append(tok.lstrip("+-") if signed_in_template else tok)
    return "".join(out)


def _get(lang: str, kind: str) -> list:
    path = CACHE_DIR / f"{lang}-{kind}.json"
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_SECONDS:
        return json.loads(path.read_text(encoding="utf-8"))
    request = urllib.request.Request(f"{HOSTS[lang]}/api/trade2/data/{kind}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))["result"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def _stat_pairs(lang: str):
    en = {e["id"]: e["text"] for g in _get("en", "stats") for e in g["entries"]}
    for g in _get(lang, "stats"):
        for e in g["entries"]:
            src = en.get(e["id"])
            if src and "\n" not in src and "\n" not in e["text"]:
                yield src, e["text"]


_SLOT_OR_NUMBER = re.compile(r"#|\d+(?:\.\d+)?")


def _numbers_as_slots(src: str, dst: str) -> str:
    """Trade templates keep fixed numbers ("for 4 seconds"), but the key turns them into '#' like any value; when
    both languages have the same numbers in the same order, make the fixed ones slots too, so a printed line's
    numbers fill the template in order."""
    if _SLOT_OR_NUMBER.findall(src) == _SLOT_OR_NUMBER.findall(dst):
        return _SLOT_OR_NUMBER.sub("#", dst)
    return dst


def _signature(entry: dict) -> tuple:
    return ("name" in entry, entry.get("disc", ""), bool((entry.get("flags") or {}).get("unique")))


def _item_pairs(lang: str):
    en_groups = {g["id"]: g["entries"] for g in _get("en", "items")}
    for g in _get(lang, "items"):
        src = en_groups.get(g["id"])
        if not src:
            continue
        matcher = difflib.SequenceMatcher(None, [_signature(e) for e in src], [_signature(e) for e in g["entries"]],
                                          autojunk=False)
        for block in matcher.get_matching_blocks():
            for k in range(block.size):
                a, b = src[block.a + k], g["entries"][block.b + k]
                for field in ("type", "name"):
                    if a.get(field) and b.get(field):
                        yield a[field], b[field]


def _static_pairs(lang: str):
    en = {e["id"]: e["text"] for g in _get("en", "static") for e in g["entries"] if e.get("text")}
    for g in _get(lang, "static"):
        for e in g["entries"]:
            if e.get("id") in en and e.get("text"):
                yield en[e["id"]], e["text"]


# PoB wordings that the trade data spells differently or does not list (our probe stats, unparsed item lines).
# Official where an equivalent exists; the rest are our own translations.
MANUAL = {
    "ru": {
        "regenerate # life per second": "# к регенерации здоровья в секунду",
        "#% increased area damage": "#% увеличение урона по области",
        "#% of physical damage from hits taken as fire damage": "#% физического урона от ударов получаемого как урон от огня",
        "gain # druidic prowess for every # total rage spent": "Дарует # заряд Друидизма за каждые итоговые # единиц потраченной свирепости",
    },
}


def dictionary(lang: str) -> dict:
    """{"stats": {template key: translated template}, "names": {english name: translated name}}"""
    if lang == "en":
        return {"stats": {}, "names": {}}
    if lang not in HOSTS:
        raise ValueError(f"unsupported language {lang!r}")
    stats = dict(MANUAL.get(lang, {}))
    for src, dst in _stat_pairs(lang):
        stats.setdefault(stat_key(src), _numbers_as_slots(src, dst))
    for key, dst in load_templates(lang).items():  # the game's own descriptions: "reduced" wordings, unparsed lines
        stats.setdefault(key, dst)
    names = dict(_static_pairs(lang))
    for src, dst in _item_pairs(lang):
        names.setdefault(src, dst)
    for src, dst in load_names(lang).items():  # skills from items, areas, buffs: from the installed game
        names.setdefault(src, dst)
    return {"stats": stats, "names": names}


def stat_templates(lang: str = "ru") -> list[dict]:
    """Unique stat templates as the trade filter lists them: {"en": ..., lang: ...} ("en" only for English)."""
    seen, out = set(), []
    pairs = _stat_pairs(lang) if lang != "en" else (
        (e["text"], e["text"]) for g in _get("en", "stats") for e in g["entries"] if "\n" not in e["text"])
    for src, dst in pairs:
        key = stat_key(src)
        if key not in seen:
            seen.add(key)
            out.append({"en": src, lang: dst})
    return out


def pob_line(template: str, values: list[str] | None = None) -> str:
    """Trade template -> PoB mod line: '#' become numbers (default 1), flat additions get the '+' the game prints."""
    values = list(values or [])
    it = iter(values)
    line = re.sub(r"#", lambda _: next(it, "1"), template)
    return re.sub(r"(^|\s)(\d+(?:\.\d+)?)(%?) to ", r"\1+\2\3 to ", line)


def translate_line(line: str, d: dict) -> str | None:
    """A mod line (or several joined with ' / ') in the target language; None if any part is unknown."""
    parts = []
    for part in line.split(" / "):
        template = d["stats"].get(stat_key(part))
        text = fill(template, part) if template else ""
        if not text:
            return None
        parts.append(text)
    return " / ".join(parts)
