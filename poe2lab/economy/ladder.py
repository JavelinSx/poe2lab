"""poe.ninja's PoE2 build ladder: which ascendancies players pick, the top characters of one, and a character's PoB
code - to start a build from a proven one instead of from nothing.

Two answers are JSON: the leagues with their ladder snapshots (data/index-state) and a character with its PoB code
(builds/<snapshot>/character).

The builds search answers in protobuf. Its field numbers were found by reading the answer. It is one search result
(field 1) with:
- the number of characters (1);
- dimensions (2): an id, the dictionary its keys are in, and counts {key 1, count 2} - key 0 is left out;
- dictionary references (6): an id and the dictionary file's hash;
- columns of the characters shown (12): an id, then packed numbers (6) or one string per character (7).

A dictionary's names come from its own file: b"NDIC", a header with the entry count at byte 12, each entry's length
(a varint), and the entries one after another to the end.

Answers are cached on disk: an hour for the ladder (poe.ninja refreshes it about hourly), for good for a dictionary
(its file is named by its hash)."""
import hashlib
import json
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = "https://poe.ninja/poe2/api"
USER_AGENT = "poe2lab (https://github.com/JavelinSx/poe2lab)"
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "ladder"
CACHE_SECONDS = 3600


def _fetch(url: str, forever: bool = False, max_age: int = CACHE_SECONDS) -> bytes:
    """poe.ninja's answer, cached (`max_age` seconds, or for good). OSError when it cannot be had (no connection, an
    error page)."""
    key = CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".bin")
    if key.exists() and (forever or time.time() - key.stat().st_mtime < max_age):
        return key.read_bytes()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=30) as r:
        body = r.read()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key.write_bytes(body)
    return body


# ---- the protobuf wire format, without a schema ----

def varint(b: bytes, i: int) -> tuple[int, int]:
    x = s = 0
    while True:
        c = b[i]
        i += 1
        x |= (c & 0x7F) << s
        s += 7
        if c < 0x80:
            return x, i


def fields(b: bytes) -> list[tuple[int, int, object]]:
    """(field number, wire type, value): a varint as int, a length-delimited value as bytes."""
    i, out = 0, []
    while i < len(b):
        key, i = varint(b, i)
        num, wt = key >> 3, key & 7
        if wt == 0:
            v, i = varint(b, i)
        elif wt == 2:
            n, i = varint(b, i)
            v, i = b[i:i + n], i + n
        elif wt == 5:
            v, i = b[i:i + 4], i + 4
        elif wt == 1:
            v, i = b[i:i + 8], i + 8
        else:
            raise ValueError(f"protobuf wire type {wt}")
        out.append((num, wt, v))
    return out


def packed(b: bytes) -> list[int]:
    out, i = [], 0
    while i < len(b):
        v, i = varint(b, i)
        out.append(v)
    return out


def dictionary(body: bytes) -> list[str]:
    """A poe.ninja dictionary file's entries in order (see the module's note)."""
    if body[:4] != b"NDIC":
        raise ValueError("not a poe.ninja dictionary")
    n = struct.unpack_from("<I", body, 12)[0]
    for start in range(16, len(body)):  # past the header (and a block table in big ones): the lengths
        lengths, i = [], start
        try:
            for _ in range(n):
                v, i = varint(body, i)
                lengths.append(v)
        except IndexError:
            continue
        if i + sum(lengths) == len(body):
            out = []
            for length in lengths:
                out.append(body[i:i + length].decode("utf-8"))
                i += length
            return out
    raise ValueError("poe.ninja dictionary layout not understood")


# ---- the ladder ----

def snapshot(league: str | None = None) -> dict:
    """The league's ladder snapshot: {"name", "url", "version", "snapshotName"}; the current league's by default."""
    state = json.loads(_fetch(f"{ROOT}/data/index-state"))
    snaps = state.get("snapshotVersions") or []
    if not snaps:
        raise OSError("poe.ninja не отдал список лиг")
    return next((s for s in snaps if league and league in (s["name"], s["url"])), snaps[0])


def _dictionary(hash_: str) -> list[str]:
    return dictionary(_fetch(f"{ROOT}/builds/dictionary/{hash_}", forever=True))


def parse_search(body: bytes, names_of) -> dict:
    """A search answer as {"total", "ascendancies": {name: count}, "items": {unique: count}, "characters": [...]}:
    names_of(dictionary id) -> the dictionary's entries (the class, gem and item names)."""
    result = next(v for n, wt, v in fields(body) if n == 1)
    parts = fields(result)
    total = next((v for n, wt, v in parts if n == 1 and wt == 0), 0)
    refs = {}
    for n, wt, v in parts:
        if n == 6:
            f = fields(v)
            refs[f[0][2].decode()] = next(x.decode() for a, _, x in f[1:] if a == 2)
    def dimension(dim: bytes) -> dict[str, int]:
        """A dimension's counts by name: how many characters pick each class, wear each unique..."""
        out = {}
        for n, wt, v in parts:
            if n != 2:
                continue
            f = fields(v)
            if f[0][2] != dim:
                continue
            names = names_of(refs[next(x.decode() for a, _, x in f if a == 2)])
            for a, _, c in f:
                if a == 3:
                    entry = dict((k, x) for k, _, x in fields(c))
                    if entry.get(1, 0) < len(names):
                        out[names[entry.get(1, 0)]] = entry.get(2, 0)
        return out
    counts = dimension(b"class")
    columns = {}
    for n, wt, v in parts:
        if n == 12:
            f = fields(v)
            nums = next((packed(x) for a, _, x in f if a == 6), None)
            columns[f[0][2].decode()] = nums if nums is not None else [x.decode() for a, _, x in f if a == 7]
    classes = names_of(refs["class"]) if "class" in refs else []
    gems = names_of(refs["gem"]) if "gem" in refs else []
    col = lambda name, i, default=None: (columns.get(name) or [])[i] if i < len(columns.get(name) or []) else default  # noqa: E731
    chars = []
    for i, name in enumerate(columns.get("name") or []):
        cls, skill = col("class", i), col("dps.skill", i)
        chars.append({"name": name, "account": col("account", i, ""), "level": col("level", i, 0),
                      "class": classes[cls] if cls is not None and cls < len(classes) else "",
                      "skill": gems[skill] if skill is not None and skill < len(gems) else "",
                      "life": col("life", i, 0), "es": col("energyshield", i, 0),
                      "ehp": col("ehp__str", i, ""), "dps": col("dps.total", i, "")})
    # the uniques the characters wear (poe.ninja's "items" filter), when the answer has them
    return {"total": total, "ascendancies": counts, "items": dimension(b"items") if "item" in refs else {},
            "characters": chars}


def search(ascendancy: str | None = None, league: str | None = None) -> dict:
    """The league's ladder, of one ascendancy or of all: how many pick each ascendancy and the top characters (by
    experience, as poe.ninja lists them), each with a link to its page there."""
    snap = snapshot(league)
    params = {"overview": snap["snapshotName"], "type": "exp"}
    if ascendancy:
        params["class"] = ascendancy
    body = _fetch(f"{ROOT}/builds/{snap['version']}/search?" + urllib.parse.urlencode(params))
    out = parse_search(body, _dictionary)
    for c in out["characters"]:
        c["url"] = character_url(snap, c["account"], c["name"])
    return out | {"league": snap["name"]}


def character_url(snap: dict, account: str, name: str) -> str:
    return (f"https://poe.ninja/poe2/builds/{snap['url']}/character/"
            f"{urllib.parse.quote(account)}/{urllib.parse.quote(name)}")


DAY = 86400
TOP_PER_CLASS = 5
# a slot of the character's gear (GGG's inventory ids) that is worn gear, not flasks or jewels
GEAR_SLOTS = {"Weapon", "Weapon2", "Offhand", "Offhand2", "Helm", "BodyArmour", "Gloves", "Boots", "Amulet", "Ring",
              "Ring2", "Belt"}
RARE, UNIQUE = 2, 3  # GGG's frame types


def character(account: str, name: str, league: str | None = None) -> dict:
    """A ladder character as poe.ninja gives it: its items (GGG's item data: base, rarity, item level, mods), skills,
    PoB code. Kept a day (a top character's gear changes slowly)."""
    snap = snapshot(league)
    query = urllib.parse.urlencode({"account": account, "name": name, "overview": snap["snapshotName"]})
    return json.loads(_fetch(f"{ROOT}/builds/{snap['version']}/character?{query}", max_age=DAY))


def top_bases(classes: dict[str, list[str]], per_class: int = TOP_PER_CLASS, league: str | None = None,
              pause: float = 0.3) -> dict:
    """What the top characters of each class wear rare: the ladder's best `per_class` of each class (of all its
    ascendancies, by level, then as poe.ninja lists them), each one's rare gear by base. `classes`: class -> its
    ascendancies' names (PoB's tree). {"league", "characters": [{"name", "account", "class", "asc", "level"}],
    "bases": [{"base", "n" (characters wearing it rare), "classes", "ilvl": [lowest, highest]}]}, the most worn first.
    About one search per ascendancy and one request per character - the answers are cached (an hour, a day)."""
    snap_league = None
    picked = []
    for cls, ascs in classes.items():
        found = []
        for asc in ascs:
            try:
                res = search(asc, league)
            except (OSError, ValueError, StopIteration):
                continue
            snap_league = res["league"]
            found += [c | {"cls": cls, "asc": asc, "rank": i} for i, c in enumerate(res["characters"]) if c["class"] == asc]
            time.sleep(pause)
        found.sort(key=lambda c: (-(c["level"] or 0), c["rank"]))
        picked += found[:per_class]
    bases: dict[str, dict] = {}
    chars = []
    for c in picked:
        try:
            data = character(c["account"], c["name"], league)
        except (OSError, ValueError):
            continue
        chars.append({k: c[k] for k in ("name", "account", "cls", "asc", "level")})
        seen = set()
        for it in data.get("items") or []:
            d = it.get("itemData") or {}
            if d.get("inventoryId") not in GEAR_SLOTS or d.get("frameType") != RARE or not d.get("baseType"):
                continue
            b = bases.setdefault(d["baseType"], {"base": d["baseType"], "n": 0, "classes": [], "ilvl": [100, 0]})
            if d["baseType"] not in seen:  # two rare rings of one base: one character still
                seen.add(d["baseType"])
                b["n"] += 1
                if c["cls"] not in b["classes"]:
                    b["classes"].append(c["cls"])
            lvl = d.get("ilvl") or 0
            b["ilvl"] = [min(b["ilvl"][0], lvl), max(b["ilvl"][1], lvl)]
        time.sleep(pause)
    return {"league": snap_league, "characters": chars,
            "bases": sorted(bases.values(), key=lambda b: (-b["n"], b["base"]))}


def top_bases_cached(classes: dict[str, list[str]], league: str | None = None, per_class: int = TOP_PER_CLASS) -> dict:
    """top_bases kept a day as a whole: the next filter is made at once."""
    key = CACHE_DIR / f"top-bases-{hashlib.sha1(f'{league}|{per_class}|{sorted(classes.items())}'.encode()).hexdigest()[:12]}.json"
    if key.exists() and time.time() - key.stat().st_mtime < DAY:
        try:
            return json.loads(key.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    out = top_bases(classes, per_class, league)
    if out["characters"]:  # nothing came (no connection): asked again next time
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        key.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def character_code(account: str, name: str, league: str | None = None) -> str:
    """A ladder character's PoB code, as poe.ninja exports it."""
    snap = snapshot(league)
    query = urllib.parse.urlencode({"account": account, "name": name, "overview": snap["snapshotName"]})
    data = json.loads(_fetch(f"{ROOT}/builds/{snap['version']}/character?{query}"))
    code = data.get("pathOfBuildingExport")
    if not code:
        raise OSError("poe.ninja не отдал PoB-код этого персонажа")
    return code
