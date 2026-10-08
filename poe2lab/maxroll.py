"""A build from a maxroll.gg planner (its build guides embed one) as the game's build planner file, so
poe2lab.buildplanner makes it a Path of Building build like any other guide.

The planner (planners.maxroll.gg/profiles/poe2/<id>, the JSON its page loads) keeps a guide's stages as profiles
("Campaign", "Early", "Endgame"...), each with its passive tree (PoB's node ids, the weapon-set nodes, the "+5 to any
attribute" choices 0 = strength, 1 = dexterity, 2 = intelligence, the jewels by their socket), its skill groups (the
game's gem ids with level and quality) and its gear (an item: the game's base id, its mods by PoB's mod ids with the
rolled stat values, its runes, a unique by its art id). PoB's data and the game's own tables (poe2lab.gamedata)
turn the ids into the names and lines the build planner format holds; a rolled value that does not fit its line's
range as it is (a per-minute or per-ten-thousand stat) is scaled to fit, else the middle of the range is taken."""
import json
import re
import urllib.request
from pathlib import Path

from . import gamedata
from .data.moddb import ModDB
from .engine.pob import lua_string

PLANNER_URL = "https://planners.maxroll.gg/profiles/poe2/{}"
USER_AGENT = "poe2lab (https://github.com/JavelinSx/poe2lab)"
_PLANNER = re.compile(r"maxroll\.gg/poe2/planner/([a-z0-9]{6,12})", re.I)
_GUIDE = re.compile(r"https?://(?:www\.)?maxroll\.gg/poe2/build-guides/[\w-]+", re.I)
ATTRIBUTES = {0: "Strength", 1: "Dexterity", 2: "Intelligence"}
# maxroll's gear slots -> PoB's
SLOTS = {"Weapon": "Weapon 1", "Offhand": "Weapon 2", "Weapon2": "Weapon 1 Swap", "Offhand2": "Weapon 2 Swap",
         "Helm": "Helmet", "BodyArmour": "Body Armour", "Gloves": "Gloves", "Boots": "Boots", "Amulet": "Amulet",
         "Ring": "Ring 1", "Ring2": "Ring 2", "Belt": "Belt", "Flask1": "Flask 1", "Flask2": "Flask 2",
         "Charm1": "Charm 1", "Charm2": "Charm 2", "Charm3": "Charm 3"}
_RANGE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")
SCALES = (1, 1 / 60, 1 / 100, 1 / 10, 1 / 1000, 60, 100)  # per minute -> per second, permyriad -> %...


class MaxrollError(ValueError):
    pass


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except OSError as err:
        raise MaxrollError(f"maxroll.gg не ответил: {err}") from err


def planner_id(text: str) -> str | None:
    """The planner's id in a maxroll planner link, or in the page of a maxroll build guide (its embedded planner);
    None for anything else."""
    text = (text or "").strip()
    m = _PLANNER.search(text)
    if m:
        return m.group(1)
    g = _GUIDE.match(text)
    if g:
        m = _PLANNER.search(_get(g.group(0)).decode("utf-8", "replace"))
        if not m:
            raise MaxrollError("на странице гайда нет планировщика maxroll")
        return m.group(1)
    return None


def fetch(pid: str) -> dict:
    """The planner as maxroll keeps it: {"id", "name", "data": {"profiles", "items", "author", ...}}."""
    try:
        outer = json.loads(_get(PLANNER_URL.format(pid)))
        outer["data"] = json.loads(outer["data"]) if isinstance(outer.get("data"), str) else outer.get("data") or {}
    except (ValueError, KeyError) as err:
        raise MaxrollError(f"не разобрал планировщик maxroll {pid}: {err}") from err
    if not outer["data"].get("profiles"):
        raise MaxrollError(f"в планировщике maxroll {pid} нет билдов")
    return outer


def profiles(planner: dict) -> list[str]:
    return [p.get("name") or f"#{i + 1}" for i, p in enumerate(planner["data"]["profiles"])]


_IDS = r"""
local tree = build.spec.tree
local nodes = {}
for _, id in ipairs({ %(ids)s }) do
  local n = tree.nodes[id]
  nodes[tostring(id)] = n and n.stringId or false
end
local slots = {}
for pobSlot, m in pairs(data.buildFileInventorySlotMap or {}) do slots[pobSlot] = { id = m.id, x = m.slot_x or 0 } end
return _poe2lab_json({ nodes = nodes, slots = slots })
"""


def _tables() -> tuple[dict, dict]:
    """(the game's base item id -> its name, a unique's art id -> its name), from the unpacked game files."""
    bal = gamedata.RAW / "data/balance"
    need = [bal / f"{t}.datc64" for t in ("baseitemtypes", "itemvisualidentity", "words", "uniquestashlayout")]
    if not all(p.is_file() for p in need):
        raise MaxrollError("нужны тексты игры (меню «Тексты игры» — распаковать из установленной игры)")
    bases = {r["Id"]: r["Name"].strip() for r in gamedata.read_table(need[0], ["Id", "Name"])}
    vis = [r["Id"] for r in gamedata.read_table(need[1], ["Id"])]
    words = [r["Text"] for r in gamedata.read_table(need[2], ["Text"])]
    uniques = {}
    for r in gamedata.read_table(need[3], ["WordsKey", "ItemVisualIdentity"]):
        w, v = r["WordsKey"], r["ItemVisualIdentity"]
        if w is not None and v is not None and w < len(words) and v < len(vis):
            uniques.setdefault(vis[v], words[w].strip())
    return bases, uniques


def _number(v: float, decimal: bool) -> str:
    return f"{v:g}" if decimal and v != int(v) else str(int(round(v)))


def mod_lines(template_lines: list[str], values: list[float]) -> list[str]:
    """A mod's lines with its rolled stat values, in order, each scaled to fit its range when it does not as it is
    (the middle of the range when no scale fits)."""
    left = list(values)
    out = []
    for template in template_lines:
        def one(m):
            lo, hi = sorted((float(m.group(1)), float(m.group(2))))
            decimal = "." in m.group(0)
            if left:
                v = left.pop(0)
                for s in SCALES:
                    x = v * s
                    if lo - 1e-6 <= x <= hi + 1e-6:
                        return _number(x, decimal)
            return _number((lo + hi) / 2, decimal)
        out.append(_RANGE.sub(one, template))
    return out


def item_text(item: dict, by_id: dict, bases: dict, uniques: dict, unknown: list | None = None) -> tuple[str, str | None]:
    """(the planner format's additional_text for an item, its unique name or None); ValueError when the base is not
    known. Mods PoB does not know go to `unknown`."""
    unknown = unknown if unknown is not None else []
    if item.get("rarity") == "unique":
        name = uniques.get(item.get("unique") or "")
        if not name:
            raise ValueError(f"уник {item.get('unique')}")
        return name, name
    base = bases.get(item.get("base") or "")
    if not base:
        raise ValueError(f"основа {item.get('base')}")
    lines = ["Guide item", base]
    socketed = [bases.get(s) for s in item.get("sockets") or [] if s]
    if item.get("sockets"):
        lines.append("Sockets: " + " ".join("S" for _ in item["sockets"]))
        lines += [f"Rune: {r}" for r in socketed if r]  # PoB gives each rune's lines for the item's kind itself
    mods = item.get("mods") or {}
    for kind in ("implicit", "explicit", "fractured", "crafted", "desecrated"):
        for mid, stats in (mods.get(kind) or {}).items():
            mod = by_id.get(mid)
            if mod is None:
                if "Implicit" not in mid:  # a base's implicit: the build planner puts the base's own on
                    unknown.append(mid)
                continue
            values = [float(v) for v in (stats or {}).values() if isinstance(v, (int, float))]
            lines += mod_lines(list(mod.lines), values)
    return "\n".join(lines), None


def allocation(history: list) -> list[tuple[int, int]]:
    """The tree a planner's history ends with, as (node id, weapon set: 0 for both) in the order taken: a history is
    steps - a node id (taken), {"id", "set"} (taken for one weapon set), {"remove": [ids]} (given back)."""
    taken: dict[tuple[int, int], None] = {}
    for step in history:
        if isinstance(step, dict) and "remove" in step:
            gone = {int(i) for i in step.get("remove") or []}
            taken = {k: None for k in taken if k[0] not in gone}
        elif isinstance(step, dict) and "id" in step:
            taken[(int(step["id"]), int(step.get("set") or 0))] = None
        elif isinstance(step, (int, float)):
            taken[(int(step), 0)] = None
    return list(taken)


def to_planner(planner: dict, index: int, engine) -> dict:
    """One profile of the planner as the game's build planner file (the JSON poe2lab.buildplanner reads), with what
    could not be carried over under "_missing"."""
    data = planner["data"]
    profs = data["profiles"]
    if not 0 <= index < len(profs):
        raise MaxrollError(f"в планировщике нет билда №{index + 1}")
    prof = profs[index]
    tree_v = prof["passives"]["variants"][-1]  # the stage's last tree: its full allocation
    hist = allocation(tree_v.get("history") or [])
    ids = [nid for nid, _ in hist]
    jewels = {int(k): v for k, v in (tree_v.get("jewels") or {}).items()}
    looked = engine._json(_IDS % {"ids": ", ".join(str(int(i)) for i in dict.fromkeys(ids + list(jewels)))})
    sid = looked["nodes"]
    bases, uniques = _tables()
    by_id = {m.id: m for m in ModDB.from_engine(engine, sets=("Item", "Desecrated", "Jewel", "Flask", "Charm")).mods}
    unknown: list[str] = []
    items = {str(k): v for k, v in data.get("items", {}).items()}
    missing = []

    passives, seen = [], set()
    attributes = {int(k): v for k, v in (tree_v.get("attributes") or {}).items()}
    for nid, ws in hist:
        s = sid.get(str(nid))
        if not s:
            missing.append(f"узел дерева {nid}")
            continue
        if (s, ws) in seen:
            continue
        seen.add((s, ws))
        entry = {"id": s}
        if ws:
            entry["weapon_set"] = ws
        if nid in attributes and attributes[nid] in ATTRIBUTES:
            entry["additional_text"] = f"+5 to {ATTRIBUTES[attributes[nid]]}"
        if nid in jewels:
            jewel = items.get(str(jewels[nid]))
            try:
                text, name = item_text(jewel or {}, by_id, bases, uniques)
                entry["additional_text"] = f"{name}\n{bases.get(jewel.get('base'), '')}" if name else text
            except ValueError as err:
                missing.append(f"самоцвет: {err}")
        passives.append(entry)

    steps = prof.get("skills", {}).get("steps") or []
    skills = []
    for group in (steps[-1].get("skills") if steps else []) or []:
        gems = [g for g in group.get("gems") or [] if g and g.get("id")]
        if not gems:
            continue
        head, *sups = gems
        ws = int(group.get("weaponSet") or 0)
        text = f"Level {head.get('level') or 20}, {head.get('quality') or 0}% Quality"
        if ws in (1, 2):  # the group is used with that weapon set only (PoB's skill text says it so)
            text += f"\nWeapon Set: Set {ws}"
        skills.append({"id": head["id"], "additional_text": text,
                       "support_skills": [{"id": g["id"], "additional_text": f"Level {g.get('level') or 1}"} for g in sups]})

    gear = prof.get("equipment", {}).get("variants") or []
    slots = []
    for slot, idx in ((gear[0].get("items") if gear else None) or {}).items():
        pob = SLOTS.get(slot)
        where = looked["slots"].get(pob) if pob else None
        item = items.get(str(idx))
        if not where or not item:
            missing.append(f"слот {slot}")
            continue
        try:
            text, name = item_text(item, by_id, bases, uniques, unknown)
        except ValueError as err:
            missing.append(f"{slot}: {err}")
            continue
        entry = {"inventory_id": where["id"], "slot_x": where["x"], "additional_text": text}
        if name:
            entry["unique_name"] = name
        slots.append(entry)

    return {"name": f"{planner.get('name') or 'maxroll'} — {prof.get('name') or index + 1}",
            "author": (data.get("author") or {}).get("name", "") if isinstance(data.get("author"), dict) else str(data.get("author") or ""),
            "link": f"https://maxroll.gg/poe2/planner/{planner.get('id')}",
            "description": f"maxroll.gg, {prof.get('name') or ''}".strip(", "),
            "ascendancy": prof.get("ascendancy") or "", "passives": passives, "skills": skills, "inventory_slots": slots,
            "_missing": missing + [f"мод {m}" for m in dict.fromkeys(unknown)]}


def to_code(planner: dict, index: int, engine) -> tuple[str, dict]:
    """One profile of the planner as a PoB code and poe2lab.buildplanner's report (its main skill: the guide's first
    skill group), with what the planner could not carry over added to the report's "missing"."""
    from . import buildplanner  # it imports the engine's helpers this module needs too
    data = to_planner(planner, index, engine)
    missing = data.pop("_missing")
    code, report = buildplanner.to_code(json.dumps(data, ensure_ascii=False), engine, main_first=True)
    report["missing"] = missing + report["missing"]
    report["variant"] = profiles(planner)[index]
    return code, report
