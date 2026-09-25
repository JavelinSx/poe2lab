"""A build in the game's own build planner format (a .build file, JSON: what Mobalytics and PoB's exporter write) as a
Path of Building build, so it can be opened, compared and followed like any other.

The format keeps the passives by the game's node names (stringId), the items as their base with mod lines, the gems
by their game ids; PoB's own data resolves all three. What the format does not keep is filled in plainly:
- an attribute node ("+5 to any attribute") takes the attribute of its name (dexterity..., intelligence...,
  strength...); a neutral one (attributes...) goes where the build's requirements still fall short, then to the
  build's most used attribute;
- a rare item: the mods listed, its base's implicits at the middle of their range, item level 82; a unique: PoB's own
  copy of it;
- skill gems level 20 unless the gem's text says otherwise ("Level 21, 20% Quality"), supports as their tier;
- the character level: from the passive points spent, as PoB estimates it."""
import json
import re
from xml.sax.saxutils import quoteattr

from .data.moddb import pattern
from .engine.pob import lua_string

ITEM_LEVEL = 82
GEM_LEVEL = 20
_MARKUP = re.compile(r"<[^<>{}]*>\{")  # the planner's text markup: <bold>{text}, <rgb(r,g,b)>{text}
_NUMBERED = re.compile(r"^\s*\d+\.\s*(.+)$")  # "1. +34 to maximum Energy Shield"
_GEM_TEXT = re.compile(r"Level (\d+)(?:,\s*(\d+)% Quality)?")


class BuildPlannerError(ValueError):
    pass


def parse(text: str) -> dict | None:
    """The planner file's JSON, or None when the text is something else (a PoB code, a link)."""
    text = (text or "").strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) and "passives" in data and "skills" in data else None


def _plain(text: str) -> str:
    return _MARKUP.sub("", text or "").replace("}", "").replace("{", "")


def item_lines(additional_text: str) -> list[str]:
    """The planner's item text as plain lines: markup and mod numbering ("1. ") taken off."""
    out = []
    for raw in _plain(additional_text).splitlines():
        line = raw.strip()
        if line:
            m = _NUMBERED.match(line)
            out.append(m.group(1).strip() if m else line)
    return out


def _middle(line: str) -> str:
    """"+(20-30) to maximum Life" -> "+25 to maximum Life": an implicit at the middle of its range."""
    def mid(m):
        lo, hi = float(m.group(1)), float(m.group(2))
        v = (lo + hi) / 2
        return str(int(v)) if v == int(v) else f"{v:.1f}"
    return re.sub(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)", mid, line)


_RESOLVE = r"""
local tree = build.spec.tree
local byString = {}
for id, node in pairs(tree.nodes) do if node.stringId then byString[node.stringId] = node end end
local nodes = _poe2lab_array({})
for _, sid in ipairs({ %(sids)s }) do
  local n = byString[sid]
  nodes[#nodes + 1] = { sid = sid, id = n and n.id or 0, attribute = n and n.isAttribute and true or false }
end
local a = tree.internalAscendNameMap[ %(asc)s ]
local slots = _poe2lab_array({})
for pobSlot, m in pairs(data.buildFileInventorySlotMap or {}) do
  slots[#slots + 1] = { slot = pobSlot, id = m.id, x = m.slot_x or 0 }
end
local gems = {}
for _, gid in ipairs({ %(gids)s }) do
  local key = data.gems[gid] and gid or nil
  if not key then
    local alt = gid:gsub("/Gem/", "/Gems/")
    if data.gems[alt] then key = alt end
  end
  if not key then
    for k, g in pairs(data.gems) do if g.gameId == gid then key = k break end end
  end
  local g = key and data.gems[key]
  gems[gid] = g and { key = key, name = g.name, support = g.grantedEffect and g.grantedEffect.support and true or false } or false
end
return _poe2lab_json({ nodes = nodes, slots = slots, gems = gems, treeVersion = tree.treeVersion,
  class = a and { classInternalId = a.class.integerId, className = a.class.name, ascendClassName = a.ascendClass.name } or nil })
"""


def _resolve(engine, data: dict) -> dict:
    sids = list(dict.fromkeys(p["id"] for p in data.get("passives", []) if p.get("id")))
    gids = []
    for s in data.get("skills", []):
        gids += [_gem(g)[0] for g in [s] + list(s.get("support_skills", []))]
    gids = [g for g in dict.fromkeys(gids) if g]
    return engine._json(_RESOLVE % {
        "sids": ", ".join(lua_string(s) for s in sids) or "",
        "gids": ", ".join(lua_string(g) for g in gids) or "",
        "asc": lua_string(data.get("ascendancy") or ""),
    })


def _gem(entry) -> tuple[str, str]:
    """(game id, its text) of a gem entry: an object, or a bare id (PoB's export writes supports so)."""
    if isinstance(entry, str):
        return entry, ""
    return entry.get("id", ""), entry.get("additional_text", "")


def _gem_xml(gem: dict, level: int, quality: int) -> str:
    return (f'<Gem gemId={quoteattr(gem["key"])} nameSpec={quoteattr(gem["name"])} level="{level}" '
            f'quality="{quality}" enabled="true" enableGlobal1="true" enableGlobal2="true" count="1"/>')


def skeleton(data: dict, resolved: dict) -> tuple[str, list[str]]:
    """The build as PoB XML without its items (they are put on by PoB itself afterwards), and what could not be
    resolved."""
    missing = []
    cls = resolved.get("class")
    if not cls:
        raise BuildPlannerError(f"неизвестное возвышение {data.get('ascendancy')!r} — файл от другой версии игры?")
    ids = {n["sid"]: n for n in resolved["nodes"]}
    normal, weapon_sets = [], {}
    listed_normally = {p["id"] for p in data.get("passives", []) if not p.get("weapon_set")}
    for p in data.get("passives", []):
        n = ids.get(p.get("id"))
        if not n or not n["id"]:
            missing.append(f"пассивка {p.get('id')}")
            continue
        ws = int(p.get("weapon_set") or 0)
        if ws and p["id"] not in listed_normally:
            weapon_sets.setdefault(ws, []).append(n["id"])
        elif n["id"] not in normal:
            normal.append(n["id"])
    by_prefix = {"strength": "str", "dexterity": "dex", "intelligence": "int"}
    attrs = {"str": [], "dex": [], "int": []}
    for sid, n in ids.items():
        if n["attribute"] and n["id"] in normal:
            kind = next((v for k, v in by_prefix.items() if sid.startswith(k)), None)
            if kind:
                attrs[kind].append(n["id"])
    spec = [f'<Spec treeVersion={quoteattr(resolved["treeVersion"])} classInternalId="{cls["classInternalId"]}" '
            f'ascendancyInternalId={quoteattr(data.get("ascendancy") or "")} secondaryAscendClassId="nil" '
            f'nodes="{",".join(str(i) for i in normal + [n for ns in weapon_sets.values() for n in ns])}">']
    # a weapon set's nodes are allocated like the others; the WeaponSet elements say which set they belong to
    for ws, nodes in sorted(weapon_sets.items()):
        spec.append(f'<WeaponSet{ws} nodes="{",".join(str(i) for i in nodes)}"/>')
    spec.append(f'<Overrides><AttributeOverride strNodes="{",".join(map(str, attrs["str"]))}" '
                f'dexNodes="{",".join(map(str, attrs["dex"]))}" intNodes="{",".join(map(str, attrs["int"]))}"/></Overrides>')
    spec.append("</Spec>")

    groups = []
    for s in data.get("skills", []):
        gems = []
        for g in [s] + list(s.get("support_skills", [])):
            gid, gtext = _gem(g)
            info = resolved["gems"].get(gid) if gid else None
            if not info:
                missing.append(f"камень {gid}")
                continue
            m = _GEM_TEXT.search(_plain(gtext))
            level = int(m.group(1)) if m else (1 if info["support"] else GEM_LEVEL)
            quality = int(m.group(2)) if m and m.group(2) else 0
            gems.append(_gem_xml(info, level, quality))
        if gems:
            groups.append('<Skill enabled="true" mainActiveSkill="1" label="" slot="">' + "".join(gems) + "</Skill>")

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<PathOfBuilding2>'
           f'<Build className={quoteattr(cls["className"])} ascendClassName={quoteattr(cls["ascendClassName"])} '
           'level="90" mainSocketGroup="1" characterLevelAutoMode="true" targetVersion="0_1" viewMode="TREE"/>'
           f'<Tree activeSpec="1">{"".join(spec)}</Tree>'
           '<Skills activeSkillSet="1"><SkillSet id="1">' + "".join(groups) + "</SkillSet></Skills>"
           '<Items activeItemSet="1"><ItemSet id="1"/></Items>'
           "</PathOfBuilding2>")
    return xml, missing


def item_text(entry: dict, bases: dict, uniques: dict) -> str | None:
    """The item a slot entry describes, as text PoB reads; None when there is nothing to put on. The text has its
    base on a line of its own (a name may stand above it); a unique is known by its name (PoB's export gives no
    unique_name); the base's implicits come from the text when it lists them (PoB's export does), else at the middle
    of their range."""
    lines = item_lines(entry.get("additional_text", ""))
    name = entry.get("unique_name") or ""
    at = next((i for i, l in enumerate(lines) if l in bases), None)
    if not name and at:
        name = lines[at - 1] if lines[at - 1] in uniques else ""
    if name:
        raw = uniques.get(name)
        return f"Rarity: UNIQUE\n{raw}" if raw else None
    rarity, title = "RARE", "Guide item"
    if at is None:
        # a magic item's name holds its base: "Vibrant Thawing Charm of the Medic"
        for i, line in enumerate(lines):
            found = max((b for b in bases if b in line), key=len, default=None)
            if found:
                at, rarity, title = i, "MAGIC", line
                break
        if at is None:
            return None
    base = lines[at] if rarity == "RARE" else max((b for b in bases if b in lines[at]), key=len)
    mods = lines[at + 1:]
    implicit = []
    for template in (l for l in (bases[base].get("implicit") or "").split("\n") if l.strip()):
        rolled = next((m for m in mods if pattern(m) == pattern(template)), None)
        if rolled is not None:
            mods.remove(rolled)
        implicit.append(rolled or _middle(template))
    head = [f"Rarity: {rarity}", title] + ([base] if rarity == "RARE" else []) + [
        f"Item Level: {ITEM_LEVEL}", f"Implicits: {len(implicit)}"]
    return "\n".join(head + implicit + mods)


_BALANCE = r"""
local spec = build.spec
local index = { Str = 1, Dex = 2, Int = 3 }
local function recalc() build.buildFlag = true build.calcsTab:BuildOutput() return build.calcsTab.mainOutput end
local function short(o, a) return (o["Req" .. a] or 0) - (o[a] or 0) end
-- each neutral attribute node, one at a time, to the attribute that falls shortest of the requirements now
local out = recalc()
local chosen = { Str = 0, Dex = 0, Int = 0 }
for _, id in ipairs({ %(neutral)s }) do
  local best, gap = "Dex", -1e9
  for _, a in ipairs({ "Str", "Dex", "Int" }) do
    if short(out, a) > gap then best, gap = a, short(out, a) end
  end
  spec:SwitchAttributeNode(id, index[best])
  spec:BuildAllDependsAndPaths()  -- puts the switched node in place of the allocated one
  chosen[best] = chosen[best] + 1
  out = recalc()
end
build.characterLevelAutoMode = true
pcall(function() build:EstimatePlayerProgress() end)
out = recalc()
return _poe2lab_json({ chosen = chosen, level = build.characterLevel,
  short = { Str = short(out, "Str"), Dex = short(out, "Dex"), Int = short(out, "Int") } })
"""


def to_code(text: str, engine) -> tuple[str, dict]:
    """(a PoB code of the build, a report: name, what could not be resolved, attributes, level). `engine` is a
    PobEngine the build can be loaded into (it replaces what it held)."""
    data = parse(text)
    if data is None:
        raise BuildPlannerError("это не файл планировщика билдов (.build)")
    resolved = _resolve(engine, data)
    xml, missing = skeleton(data, resolved)
    engine.load_xml(xml, data.get("name") or "guide")
    exported = engine.export_item_data()
    bases = {b["name"]: b for b in exported["bases"]}
    uniques = {u["name"]: u["raw"] for u in engine.unique_catalog()}
    slots = {(s["id"], s["x"]): s["slot"] for s in resolved["slots"]}
    worn = []
    for entry in data.get("inventory_slots", []):
        slot = slots.get((entry.get("inventory_id"), int(entry.get("slot_x") or 0)))
        text_ = item_text(entry, bases, uniques) if slot else None
        if not text_:
            missing.append(f"предмет {entry.get('unique_name') or next(iter(item_lines(entry.get('additional_text', ''))), '') or entry.get('inventory_id')}")
            continue
        engine.equip_item(slot, text_)
        worn.append(slot)
    neutral = [n["id"] for n in resolved["nodes"] if n["attribute"] and n["id"]
               and not re.match(r"(strength|dexterity|intelligence)", n["sid"])]
    balance = engine._json(_BALANCE % {"neutral": ", ".join(str(i) for i in neutral)})
    # the format does not say which skill is the main one: the one PoB finds dealing the most damage
    strongest = next(iter(engine.skill_damage()), None)
    if strongest and strongest["dps"] > 0:
        engine.set_main_skill(strongest["group"], strongest["skill"])
    report = {"name": data.get("name") or "", "author": data.get("author") or "", "link": data.get("link") or "",
              "missing": missing, "worn": worn, "level": balance["level"], "attributes": balance}
    return engine.export_code(), report


def export(engine, name: str = "") -> str:
    """The build open in `engine` in the planner format (PoB's own exporter): for the game's build planner
    (Documents/My Games/Path of Exile 2/BuildPlanner) or another tool."""
    return engine._lua(f"""
local exporter = LoadModule("Modules/BuildExportPoE2")
local json, err = exporter.Export(build, {{ name = {lua_string(name)} }}, {{ specIndex = build.treeTab.activeSpec,
  skillSetId = build.skillsTab.activeSkillSetId, itemSetId = build.itemsTab.activeItemSetId }})
if not json then error(err, 0) end
return json""")
