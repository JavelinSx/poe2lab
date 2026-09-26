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
- the character level: from the passive points spent, as PoB estimates it.

What the format has no field for rides in its notes (additional_text), where the game shows it on hover: poe2lab's
export puts each jewel on its socket and the attribute chosen on each "+5 to any attribute" node, and reads them back.
When to take each gem, item and passive (level_interval) is kept with the build as the guide's plan."""
import json
import os
import re
from pathlib import Path
from xml.sax.saxutils import quoteattr

from .data.moddb import pattern
from .engine.pob import lua_string

ITEM_LEVEL = 82
GEM_LEVEL = 20
_MARKUP = re.compile(r"<[^<>{}]*>\{")  # the planner's text markup: <bold>{text}, <rgb(r,g,b)>{text}
_NUMBERED = re.compile(r"^\s*\d+\.\s*(.+)$")  # "1. +34 to maximum Energy Shield"
_GEM_TEXT = re.compile(r"Level (\d+)(?:,\s*(\d+)% Quality)?")


PLANNER_ENV = "POE2LAB_BUILDPLANNER"  # another folder than the game's (tests)
# the fields of the format (pathofexile.com/developer/docs/game#buildplanner); anything else is reported
KNOWN = {
    "": {"name", "author", "link", "description", "ascendancy", "passives", "skills", "inventory_slots"},
    "passives": {"id", "level_interval", "weapon_set", "additional_text"},
    "skills": {"id", "level_interval", "additional_text", "support_skills"},
    "support_skills": {"id", "level_interval", "additional_text"},
    "inventory_slots": {"inventory_id", "slot_x", "slot_y", "level_interval", "unique_name", "additional_text"},
}
_ATTRIBUTE_WORDS = {"str": r"\b(strength|сил)", "dex": r"\b(dexterity|ловк)", "int": r"\b(intelligence|интел)"}
ATTRIBUTE_NOTE = {"ru": {"Strength": "+5 к силе", "Dexterity": "+5 к ловкости", "Intelligence": "+5 к интеллекту"},
                  "en": {"Strength": "+5 to Strength", "Dexterity": "+5 to Dexterity", "Intelligence": "+5 to Intelligence"}}
META_NOTE = {"ru": "вставлен в «{}»", "en": "socketed in {}"}


class BuildPlannerError(ValueError):
    pass


def planner_dir() -> Path:
    """The game's build planner folder. The game watches it: a .build written there shows in game at once."""
    if os.environ.get(PLANNER_ENV):
        return Path(os.environ[PLANNER_ENV])
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    return home / "Documents" / "My Games" / "Path of Exile 2" / "BuildPlanner"


def parse(text: str) -> dict | None:
    """The planner file's JSON, or None when the text is something else (a PoB code, a link). Passives and skills
    may be bare ids in the format: they come back as {"id": ...}."""
    text = (text or "").lstrip("\ufeff").strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or not any(k in data for k in ("passives", "skills", "inventory_slots")):
        return None
    for key in ("passives", "skills", "inventory_slots"):
        data[key] = [e if isinstance(e, dict) else {"id": e} for e in data.get(key) or [] if isinstance(e, (dict, str))]
    return data


def interval(value) -> list[int] | None:
    """A level_interval (a level, or [from, to]) as [from, to]; None when there is none."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return [int(value), 100]
    if isinstance(value, list) and value and all(isinstance(v, (int, float)) for v in value):
        return [int(value[0]), int(value[1]) if len(value) > 1 else 100]
    return None


def attribute_choice(note: str) -> str | None:
    """The attribute a node's note names ("+5 to Dexterity", "+5 к ловкости"): str, dex or int; None if none or
    several."""
    text = _plain(note).lower()
    found = [k for k, rx in _ATTRIBUTE_WORDS.items() if re.search(rx, text)]
    return found[0] if len(found) == 1 else None


def unknown_fields(data: dict) -> list[str]:
    """Fields of the file this reader does not know (a newer format, another tool's extras): reported, not lost
    silently."""
    out = {k for k in data if k not in KNOWN[""]}
    for section in ("passives", "skills", "inventory_slots"):
        for entry in data.get(section) or []:
            out.update(f"{section}.{k}" for k in entry if k not in KNOWN[section])
            for sup in entry.get("support_skills") or [] if section == "skills" else []:
                if isinstance(sup, dict):
                    out.update(f"support_skills.{k}" for k in sup if k not in KNOWN["support_skills"])
    return sorted(out)


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


def skeleton(data: dict, resolved: dict, choices: dict[str, str] | None = None) -> tuple[str, list[str]]:
    """The build as PoB XML without its items (they are put on by PoB itself afterwards), and what could not be
    resolved. `choices`: the attribute a node's note names (str / dex / int), by the node's id in the format."""
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
            kind = (choices or {}).get(sid) or next((v for k, v in by_prefix.items() if sid.startswith(k)), None)
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
    if rarity == "RARE" and at:
        title = lines[at - 1]  # a rare's own name, above its base (PoB's export, poe2lab's jewel notes)
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


def _gem_entry(entry, gems: dict) -> dict:
    gid, text = _gem(entry)
    info = gems.get(gid) or {}
    m = _GEM_TEXT.search(_plain(text))
    iv = interval(entry.get("level_interval")) if isinstance(entry, dict) else None
    note = _plain(text).strip()
    return {"name": info.get("name") or gid, "known": bool(info), "level": int(m.group(1)) if m else None,
            "quality": int(m.group(2)) if m and m.group(2) else None, "from": iv and iv[0], "to": iv and iv[1],
            "note": None if not note or (m and m.group(0) == note) else note}


def to_code(text: str, engine) -> tuple[str, dict]:
    """(a PoB code of the build, a report of everything the file holds and what became of it: the passives, gems and
    items with their levels, the notes, what could not be resolved, the attributes, the level, fields unknown to
    this reader, and `plan` - the guide's own levels and notes, to keep with the build). `engine` is a PobEngine the
    build can be loaded into (it replaces what it held)."""
    data = parse(text)
    if data is None:
        raise BuildPlannerError("это не файл планировщика билдов (.build)")
    resolved = _resolve(engine, data)
    notes = {p["id"]: p["additional_text"] for p in data["passives"] if p.get("id") and p.get("additional_text")}
    choices = {sid: c for sid, note in notes.items() if (c := attribute_choice(note))}
    xml, missing = skeleton(data, resolved, choices)
    engine.load_xml(xml, data.get("name") or "guide")
    exported = engine.export_item_data()
    bases = {b["name"]: b for b in exported["bases"]}
    uniques = {u["name"]: u["raw"] for u in engine.unique_catalog()}
    slots = {(s["id"], s["x"]): s["slot"] for s in resolved["slots"]}
    worn, items = [], []
    for entry in data.get("inventory_slots", []):
        slot = slots.get((entry.get("inventory_id"), int(entry.get("slot_x") or 0)))
        text_ = item_text(entry, bases, uniques) if slot else None
        lines = item_lines(entry.get("additional_text", ""))
        name = entry.get("unique_name") or (lines[0] if lines else "") or entry.get("inventory_id") or ""
        iv = interval(entry.get("level_interval"))
        kind = text_.split("\n", 1)[0].removeprefix("Rarity: ").lower() if text_ else "missing"
        items.append({"slot": slot or entry.get("inventory_id"), "name": name, "kind": kind,
                      "from": iv and iv[0], "to": iv and iv[1]})
        if not text_:
            missing.append(f"предмет {name}")
            continue
        engine.equip_item(slot, text_)
        worn.append(slot)
    # jewels written as the notes of their sockets (poe2lab's export does so): put back into the sockets
    node_ids = {n["sid"]: n["id"] for n in resolved["nodes"] if n["id"]}
    jewels = []
    for sid, note in notes.items():
        if sid.startswith("jewel_slot") and sid in node_ids:
            jewel = item_text({"additional_text": note}, bases, uniques)
            if jewel:
                engine.equip_item(f"Jewel {node_ids[sid]}", jewel)
                jewels.append(item_lines(note)[0])
    neutral = [n["id"] for n in resolved["nodes"] if n["attribute"] and n["id"] and n["sid"] not in choices
               and not re.match(r"(strength|dexterity|intelligence)", n["sid"])]
    balance = engine._json(_BALANCE % {"neutral": ", ".join(str(i) for i in neutral)})
    # the format does not say which skill is the main one: the one PoB finds dealing the most damage
    strongest = next(iter(engine.skill_damage()), None)
    if strongest and strongest["dps"] > 0:
        engine.set_main_skill(strongest["group"], strongest["skill"])
    skills = []
    for s in data.get("skills", []):
        entry = _gem_entry(s, resolved["gems"])
        entry["supports"] = [_gem_entry(x, resolved["gems"]) for x in s.get("support_skills") or []]
        skills.append(entry)
    ids = [p["id"] for p in data["passives"] if p.get("id")]
    attribute_nodes = {n["sid"] for n in resolved["nodes"] if n["attribute"]}
    passives = {
        "total": len(set(ids)),
        "ascendancy": len({i for i in ids if i.startswith("Ascendancy")}),
        "weaponSets": {str(ws): len({p["id"] for p in data["passives"] if int(p.get("weapon_set") or 0) == ws})
                       for ws in (1, 2) if any(int(p.get("weapon_set") or 0) == ws for p in data["passives"])},
        "attributes": len(attribute_nodes & set(ids)), "attributesChosen": len(choices),
        "jewelSockets": len({i for i in ids if i.startswith("jewel_slot")}), "jewels": jewels,
        "notes": len(notes), "levels": sum(1 for p in data["passives"] if interval(p.get("level_interval"))),
    }
    plan = {
        "source": {k: _plain(data.get(k) or "").strip() for k in ("name", "author", "link", "description")},
        "skills": skills, "items": items,
        "passives": [{"id": p["id"], "from": iv[0], "to": iv[1]} for p in data["passives"]
                     if p.get("id") and (iv := interval(p.get("level_interval")))],
        "notes": {sid: _plain(n).strip() for sid, n in notes.items()},
    }
    report = {"name": data.get("name") or "", "author": data.get("author") or "", "link": data.get("link") or "",
              "description": plan["source"]["description"], "missing": missing, "worn": worn,
              "level": balance["level"], "attributes": balance, "passives": passives, "skills": skills,
              "items": items, "unknown": unknown_fields(data), "plan": plan}
    return engine.export_code(), report


_EXTRAS = r"""
local exporter = LoadModule("Modules/BuildExportPoE2")
local out = { jewels = {}, attrs = {}, items = {}, metas = {}, names = {} }
for nodeId, slot in pairs(build.itemsTab.sockets) do
  local node = build.spec.nodes[nodeId]
  local item = build.itemsTab.items[slot.selItemId]
  if item and node and node.stringId and build.spec.allocNodes[nodeId] then
    out.jewels[node.stringId] = exporter.ItemAdditionalText(item)
  end
end
for id, node in pairs(build.spec.hashOverrides or {}) do
  local base = build.spec.tree.nodes[id]
  if base and base.stringId and build.spec.allocNodes[id] then out.attrs[base.stringId] = node.dn or "" end
end
for pobSlot, m in pairs(data.buildFileInventorySlotMap) do
  local slot = build.itemsTab.slots[pobSlot]
  local item = slot and slot.selItemId and build.itemsTab.items[slot.selItemId]
  if item then
    out.items[m.id .. ":" .. (m.slot_x or 0)] = { slot = pobSlot,
      req = item.requirements and item.requirements.level or 0,
      unique = (item.rarity == "UNIQUE" or item.rarity == "RELIC") and (item.title or "") or "" }
  end
end
-- the meta gem a skill goes into: the planner has no meta gems, the skill's note says where it is socketed
for _, group in ipairs(build.skillsTab.socketGroupList) do
  local meta
  for _, gem in ipairs(group.gemList or {}) do
    local gd = gem.gemData
    if gd and gd.gameId then out.names[gd.gameId] = gd.name end
    local ge = gd and gd.grantedEffect
    if ge and not ge.support and ge.skillTypes and ge.skillTypes[SkillType.Meta] then meta = gd.name end
  end
  if meta then
    for _, gem in ipairs(group.gemList or {}) do
      local gd = gem.gemData
      if gd and gd.gameId and gd.name ~= meta and not (gd.grantedEffect and gd.grantedEffect.support) then
        out.metas[gd.gameId] = meta
      end
    end
  end
end
return _poe2lab_json(out)
"""


def export_rich(engine, name: str, *, levels: dict[str, int] | None = None, plan: dict | None = None,
                description: str = "", lang: str = "ru", names: dict[str, str] | None = None) -> str:
    """The build open in `engine` for the game's planner, with what the format has no field for put where the game
    shows it: each jewel as the note of its socket, the attribute chosen on each "+5 to any attribute" node, the meta
    gem a skill is socketed in; when each gem and item comes - the guide's own levels when the build came from one
    (`plan`), else when the gem can be had (`levels`, by gem name) and the item's level requirement; the unique's
    name, the guide's author and link, a description. `names`: official translations for the notes."""
    lang = lang if lang in ATTRIBUTE_NOTE else "en"
    tr = (names or {}).get if lang != "en" else None
    data = json.loads(export(engine, name))
    extras = engine._json(_EXTRAS)
    jewels, attrs, items, metas, gem_names = (extras.get(k) if isinstance(extras.get(k), dict) else {}
                                              for k in ("jewels", "attrs", "items", "metas", "names"))
    plan = plan or {}
    guide_gems = {}
    for s in plan.get("skills", []):
        for g in [s] + list(s.get("supports", [])):
            if g.get("from") and (g is s or g["from"] > 1):
                guide_gems.setdefault(g["name"], [g["from"], g.get("to") or 100])
    guide_items = {i["slot"]: [i["from"], i.get("to") or 100] for i in plan.get("items", []) if i.get("from")}
    guide_passives = {p["id"]: [p["from"], p.get("to") or 100] for p in plan.get("passives", []) if p.get("from")}
    guide_notes = plan.get("notes") or {}

    for p in data.get("passives", []):
        sid = p.get("id")
        if sid in jewels:
            p["additional_text"] = jewels[sid]
        elif sid in attrs and attrs[sid] in ATTRIBUTE_NOTE[lang]:
            p["additional_text"] = ATTRIBUTE_NOTE[lang][attrs[sid]]
        elif guide_notes.get(sid) and "additional_text" not in p:
            p["additional_text"] = guide_notes[sid]
        if sid in guide_passives:
            p["level_interval"] = guide_passives[sid]

    def gem_interval(gid):
        gem = gem_names.get(gid)
        if gem in guide_gems:
            return guide_gems[gem]
        lv = (levels or {}).get(gem)
        return [lv, 100] if lv and lv > 1 else None

    for s in data.get("skills", []):
        iv = gem_interval(s.get("id"))
        if iv:
            s["level_interval"] = iv
        meta = metas.get(s.get("id"))
        if meta:
            note = META_NOTE[lang].format((tr(meta) if tr else None) or meta)
            s["additional_text"] = f"{s['additional_text']}\n{note}" if s.get("additional_text") else note
        supports = []
        for sup in s.get("support_skills") or []:
            obj = dict(sup) if isinstance(sup, dict) else {"id": sup}
            iv = gem_interval(obj["id"])
            if iv:
                obj["level_interval"] = iv
            supports.append(obj if len(obj) > 1 else obj["id"])
        if supports:
            s["support_skills"] = supports
    for entry in data.get("inventory_slots", []):
        info = items.get(f"{entry.get('inventory_id')}:{entry.get('slot_x') or 0}")
        if not info:
            continue
        iv = guide_items.get(info["slot"]) or ([info["req"], 100] if (info.get("req") or 0) > 1 else None)
        if iv:
            entry["level_interval"] = iv
        if info.get("unique"):
            entry["unique_name"] = info["unique"]
    source = plan.get("source") or {}
    for key in ("author", "link"):
        if source.get(key):
            data[key] = source[key]
    if description:
        data["description"] = description
    return json.dumps(data, ensure_ascii=False, indent=1)


def export(engine, name: str = "") -> str:
    """The build open in `engine` in the planner format (PoB's own exporter): for the game's build planner
    (Documents/My Games/Path of Exile 2/BuildPlanner) or another tool."""
    return engine._lua(f"""
local exporter = LoadModule("Modules/BuildExportPoE2")
local json, err = exporter.Export(build, {{ name = {lua_string(name)} }}, {{ specIndex = build.treeTab.activeSpec,
  skillSetId = build.skillsTab.activeSkillSetId, itemSetId = build.itemsTab.activeItemSetId }})
if not json then error(err, 0) end
return json""")
