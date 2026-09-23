import json
import re
from contextlib import contextmanager
from pathlib import Path

from .luahost import DEFAULT_POB_ROOT, LuaError, LuaHost, lua_string
from .pobcode import decode_pob_code, encode_pob_code

_HELPERS = r"""
local dkjson = require "dkjson"

function _poe2lab_json(value)
  return dkjson.encode(value)
end

local function _poe2lab_finite(v) return type(v) == "number" and v == v and v ~= math.huge and v ~= -math.huge end

function _poe2lab_numbers(t)
  local res = {}
  for k, v in pairs(t) do
    if _poe2lab_finite(v) then
      res[k] = v
    elseif v == math.huge and type(k) == "string" and k:match("MaximumHitTaken$") then
      res[k] = 1e9  -- immune to the damage type (e.g. Chaos Inoculation); poe2lab.analysis.threats.IMMUNE_HIT
    end
  end
  -- A minion skill as the main skill: the player's own DPS is 0 and the damage lives in output.Minion (per
  -- minion). Every analysis reads CombinedDPS, so there it becomes the army's damage: one minion times the
  -- active limit. The player's own number stays as PlayerCombinedDPS.
  local m = t.Minion
  if type(m) == "table" then
    for k, v in pairs(m) do
      if _poe2lab_finite(v) then res["Minion." .. k] = v end
    end
    local per = m.CombinedDPS or m.TotalDPS or 0
    if (res.CombinedDPS or 0) < 1e-6 and _poe2lab_finite(per) and per > 0 then
      local count = (_poe2lab_finite(t.ActiveMinionLimit) and t.ActiveMinionLimit > 0) and t.ActiveMinionLimit or 1
      res.PlayerCombinedDPS = res.CombinedDPS or 0
      res.CombinedDPS = per * count
      res.MinionCount = count
      res.DpsFromMinions = 1
    end
  end
  return dkjson.encode(res)
end

function _poe2lab_nodeset(ids)
  if #ids == 0 then return nil end
  local set = {}
  for _, id in ipairs(ids) do
    local node = build.spec.nodes[id]
    if not node then error("unknown passive node " .. tostring(id)) end
    set[node] = true
  end
  return set
end

function _poe2lab_array(t)
  return setmetatable(t, { __jsontype = "array" })
end

local function extendModList(base, lines)
  if #lines == 0 then return base end
  local modList = new("ModList"):ModList()
  modList:AddList(base)
  for _, line in ipairs(lines) do
    local mods, extra = modLib.parseMod(line)
    if not mods or extra then error("PoB cannot parse mod: " .. line, 0) end
    for i = 1, #mods do
      if mods[i] then modList:AddMod(modLib.setSource(mods[i], "Custom:poe2lab")) end
    end
  end
  return modList
end

function _poe2lab_item(text)
  local item = new("Item"):Item(text)
  if not item.base then error("PoB could not read the item (unknown base?)", 0) end
  item:NormaliseQuality()
  return item
end

function _poe2lab_item_runes(text, names)
  local item = _poe2lab_item(text)
  for i = 1, item.itemSocketCount do item.runes[i] = names[i] or "None" end
  item:UpdateRunes()
  item:BuildAndParseRaw()
  item:NormaliseQuality()
  return item
end

function _poe2lab_with_gems_disabled(pairsList, fn)
  if #pairsList == 0 then return fn() end
  local saved = {}
  for _, p in ipairs(pairsList) do
    local group = build.skillsTab.socketGroupList[p[1]]
    local gem = group and group.gemList[p[2]]
    if not gem then error("no gem " .. p[1] .. "." .. p[2], 0) end
    saved[#saved + 1] = { gem = gem, enabled = gem.enabled }
    gem.enabled = false
  end
  local ok, res = pcall(fn)
  for _, s in ipairs(saved) do s.gem.enabled = s.enabled end
  if not ok then error(res, 0) end
  return res
end

-- The what-if calculator re-reads the config tab (inputs, modList, enemyModList) on every call, so
-- config values and extra player/enemy mods are applied temporarily and everything is restored after.
function _poe2lab_with_setup(config, lines, enemyLines, fn)
  local configTab = build.configTab
  local savedInput, savedPlaceholder = {}, {}
  local hasConfig = next(config) ~= nil
  if hasConfig then
    for k, v in pairs(configTab.placeholder) do savedPlaceholder[k] = v end
    for k, v in pairs(config) do
      savedInput[k] = { value = configTab.input[k] }
      configTab.input[k] = v
    end
    configTab:BuildModList()
  end
  local baseMods, baseEnemyMods = configTab.modList, configTab.enemyModList
  local ok, res = pcall(function()
    configTab.modList = extendModList(baseMods, lines)
    configTab.enemyModList = extendModList(baseEnemyMods, enemyLines)
    return fn()
  end)
  configTab.modList, configTab.enemyModList = baseMods, baseEnemyMods
  if hasConfig then
    for k, saved in pairs(savedInput) do configTab.input[k] = saved.value end
    for k in pairs(configTab.placeholder) do configTab.placeholder[k] = nil end
    for k, v in pairs(savedPlaceholder) do configTab.placeholder[k] = v end
    configTab:BuildModList()
  end
  if not ok then error(res, 0) end
  return res
end
"""


class PobError(RuntimeError):
    pass


def _lua_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return lua_string(str(v))


class PobEngine:
    """One headless Path of Building instance holding one loaded build."""

    def __init__(self, pob_root: Path = DEFAULT_POB_ROOT):
        self._host = LuaHost(pob_root)
        self._host.run('dofile("HeadlessWrapper.lua")')
        startup_error = self._host.run("return __mainObject__.promptMsg")
        if startup_error:
            raise PobError(f"PoB failed to start: {startup_error}")
        self._host.run(_HELPERS)

    def _lua(self, code: str):
        try:
            return self._host.run(code)
        except LuaError as e:
            raise PobError(str(e)) from None

    def _json(self, code: str):
        return json.loads(self._lua(code))

    def load_code(self, code: str, name: str = "build"):
        self.load_xml(decode_pob_code(code), name)

    def load_xml(self, xml: str, name: str = "build"):
        self._xml = xml
        self._lua(f"loadBuildFromXML({lua_string(xml)}, {lua_string(name)})")
        self._check_loaded()

    def unread_items(self) -> list[dict]:
        """Items the build file puts in a slot that PoB dropped while loading - typically a base renamed in a later
        game version (an old guide), so everything is computed without them and PoB says nothing."""
        xml = getattr(self, "_xml", None)
        if not xml:
            return []
        items = {}
        for m in re.finditer(r"<Item\s([^>]*)>(.*?)</Item>", xml, re.S):
            item_id = re.search(r'\bid="(\d+)"', m.group(1))
            if not item_id:
                continue
            lines = [l.strip() for l in m.group(2).strip().splitlines() if l.strip() and not l.strip().startswith("<")]
            body = [l for l in lines if not l.startswith(("Rarity:", "Unique ID", "Item Level", "Quality", "Sockets"))]
            rarity = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Rarity:")), "")
            name = body[0] if body else ""
            base = body[1] if rarity in ("RARE", "UNIQUE") and len(body) > 1 else name
            items[item_id.group(1)] = {"name": name, "base": base, "rarity": rarity}
        slotted = {}
        for tag in re.findall(r"<Slot\b[^>]*>", xml):  # attribute order differs between PoB versions
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', tag))
            if "name" in attrs and "itemId" in attrs and "nodeId" not in attrs:
                slotted[attrs["name"]] = attrs["itemId"]
        loaded = {i["slot"] for i in self.equipped_items()}
        return [{"slot": slot, **items[iid]} for slot, iid in slotted.items()
                if iid != "0" and iid in items and slot not in loaded and "Swap" not in slot]

    def load_character_json(self, character_json: str):
        """Load a character as returned by the official PoE API (characters endpoint)."""
        self._lua(f"loadBuildFromJSON({lua_string(character_json)})")
        self.recalc()
        self._check_loaded()

    def _check_loaded(self):
        if self._lua("return build.calcsTab and build.calcsTab.mainOutput and 'ok'") != "ok":
            raise PobError("build did not produce calculation output")

    def recalc(self):
        self._lua("build.calcsTab:BuildOutput()")

    def info(self) -> dict:
        return self._json("""
return _poe2lab_json({
  class = build.spec.curClassName,
  ascendancy = build.spec.curAscendClassName,
  level = build.characterLevel,
  mainSocketGroup = build.mainSocketGroup,
})""")

    def socket_groups(self) -> list[dict]:
        return self._json("""
local out = _poe2lab_array({})
for i, g in ipairs(build.skillsTab.socketGroupList) do
  local skills = _poe2lab_array({})
  for _, s in ipairs(g.displaySkillList or {}) do
    skills[#skills + 1] = s.activeEffect.grantedEffect.name
  end
  out[#out + 1] = { index = i, label = g.label or "", slot = g.slot or "",
                    enabled = g.enabled and true or false, skills = skills }
end
return _poe2lab_json(out)""")

    def set_main_skill(self, socket_group_index: int, active_skill_index: int = 1):
        """Pick the skill PoB reports DPS for: a socket group and, within it, one of its active skills."""
        groups = self.socket_groups()
        if not 1 <= socket_group_index <= len(groups):
            raise PobError(f"socket group {socket_group_index} out of range 1..{len(groups)}")
        skills = groups[socket_group_index - 1]["skills"]
        if not 1 <= active_skill_index <= len(skills):
            raise PobError(f"active skill {active_skill_index} out of range 1..{len(skills)} for group {socket_group_index}")
        self._lua(
            f"build.mainSocketGroup = {socket_group_index}\n"
            f"build.skillsTab.socketGroupList[{socket_group_index}].mainActiveSkill = {active_skill_index}"
        )
        self.recalc()

    def skill_damage(self, config: dict | None = None) -> list[dict]:
        """Damage of every active skill of every enabled socket group if it were the main skill (the build's choice
        is restored). For a main skill PoB cannot compute (0 DPS) this shows where the damage actually is."""
        group = int(self._lua("return build.mainSocketGroup"))
        active = int(self._lua(f"return build.skillsTab.socketGroupList[{group}].mainActiveSkill or 1"))
        out = []
        try:
            for g in self.socket_groups():
                if not g["enabled"]:
                    continue
                for i, name in enumerate(g["skills"], 1):
                    self.set_main_skill(g["index"], i)
                    dps = self.what_if(config=config)["CombinedDPS"]
                    out.append({"group": g["index"], "skill": i, "name": name, "dps": dps})
        finally:
            self.set_main_skill(group, active)
        return sorted(out, key=lambda x: -x["dps"])

    def monster_damage(self, level: int) -> float:
        """PoB's base monster damage for an area level (data.monsterDamageTable)."""
        return float(self._lua(f"return data.monsterDamageTable[{int(level)}]"))

    def main_skill(self) -> str | None:
        return self._lua("""
local g = build.skillsTab.socketGroupList[build.mainSocketGroup]
local s = g and g.displaySkillList and g.displaySkillList[g.mainActiveSkill or 1]
return s and s.activeEffect.grantedEffect.name""")

    def stats(self) -> dict[str, float]:
        """All numeric outputs of the last full calculation."""
        return self._json("return _poe2lab_numbers(build.calcsTab.mainOutput)")

    def allocated_nodes(self) -> list[dict]:
        return self._json("""
local out = _poe2lab_array({})
for id, node in pairs(build.spec.allocNodes) do
  out[#out + 1] = { id = id, name = node.dn or node.name or "", type = node.type or "",
                    ascendancy = node.ascendancyName or "" }
end
return _poe2lab_json(out)""")

    def tree_reach(self, max_points: int = 6) -> list[dict]:
        """Unallocated notables and keystones of the main tree reachable within max_points, with the path PoB
        would allocate (its shortest path from the current tree, target included) and the target's stat lines."""
        return self._json(f"""
local out = _poe2lab_array({{}})
for id, node in pairs(build.spec.nodes) do
  if not node.alloc and (node.type == "Notable" or node.type == "Keystone") and not node.ascendancyName
     and node.path and #node.path > 0 and #node.path <= {int(max_points)} then
    local path, names = _poe2lab_array({{}}), _poe2lab_array({{}})
    for i, n in ipairs(node.path) do path[i] = n.id; names[i] = n.dn or "" end
    out[#out + 1] = {{ id = id, name = node.dn or "", type = node.type, path = path, pathNames = names,
                      stats = _poe2lab_array(node.sd or {{}}) }}
  end
end
return _poe2lab_json(out)""")

    def tree_branches(self) -> list[dict]:
        """Allocated nodes of the main tree with what would be unallocated along with each (PoB's `depends`: the
        node itself and everything only reachable through it) - the points a respec of that node frees."""
        return self._json("""
local out = _poe2lab_array({})
for id, node in pairs(build.spec.allocNodes) do
  if node.type ~= "ClassStart" and node.type ~= "AscendClassStart" and not node.ascendancyName
     and (node.allocMode or 0) == 0 then
    local deps, names = _poe2lab_array({}), _poe2lab_array({})
    for i, n in ipairs(node.depends or { node }) do
      deps[i] = n.id
      if n ~= node then names[#names + 1] = n.dn or "" end
    end
    out[#out + 1] = { id = id, name = node.dn or "", type = node.type or "", depends = deps, dependNames = names,
                      stats = _poe2lab_array(node.sd or {}) }
  end
end
return _poe2lab_json(out)""")

    # ---- editing the passive tree (for tree plans; the build file is never touched) ----

    def export_code(self) -> str:
        """The build as it is now in the engine (tree plans included), as a PoB code."""
        return encode_pob_code(self._lua('return build:SaveDB("poe2lab")'))

    def tree_points(self) -> int:
        """Main-tree points in use: allocated nodes without class/ascendancy starts, ascendancy and weapon-set nodes."""
        return int(self._lua("""
local n = 0
for _, node in pairs(build.spec.allocNodes) do
  if node.type ~= "ClassStart" and node.type ~= "AscendClassStart" and not node.ascendancyName
     and (node.allocMode or 0) == 0 then n = n + 1 end
end
return n"""))

    def tree_snapshot(self, name: str):
        """Remember the current allocation (and attribute choices) under `name`."""
        self._lua(f"""
_poe2lab_tree_snaps = _poe2lab_tree_snaps or {{}}
local snap = {{ nodes = {{}}, overrides = copyTable(build.spec.hashOverrides or {{}}, true) }}
for id, node in pairs(build.spec.allocNodes) do snap.nodes[id] = node.allocMode or 0 end
_poe2lab_tree_snaps[ {lua_string(name)} ] = snap""")

    def tree_restore(self, name: str):
        """Put back an allocation remembered by tree_snapshot, exactly, and recalculate."""
        self._lua(f"""
local snap = _poe2lab_tree_snaps and _poe2lab_tree_snaps[ {lua_string(name)} ]
if not snap then error("no tree snapshot {name}", 0) end
local spec = build.spec
for id, node in pairs(copyTable(spec.allocNodes, true)) do
  if snap.nodes[id] == nil then spec:DeallocSingleNode(spec.nodes[id]) end
end
for id, mode in pairs(snap.nodes) do
  local node = spec.nodes[id]
  if node and not node.alloc then
    node.alloc = true
    node.allocMode = mode
    spec.allocNodes[id] = node
  end
end
spec.hashOverrides = copyTable(snap.overrides, true)
spec:BuildAllDependsAndPaths()
build.buildFlag = true
build.calcsTab:BuildOutput()""")

    def tree_add(self, node_id: int) -> list[str]:
        """Allocate a node along PoB's shortest path from the tree; returns the names of the nodes allocated."""
        return self._json(f"""
local spec = build.spec
local node = spec.nodes[{int(node_id)}]
if not node then error("no passive node {int(node_id)}", 0) end
if node.alloc then return _poe2lab_json(_poe2lab_array({{}})) end
if not node.path or #node.path == 0 then error("node cannot be reached from the tree", 0) end
local before = {{}}
for id in pairs(spec.allocNodes) do before[id] = true end
spec:AllocNode(node)
spec:BuildAllDependsAndPaths()
build.buildFlag = true
build.calcsTab:BuildOutput()
local added = _poe2lab_array({{}})
for id, n in pairs(spec.allocNodes) do if not before[id] then added[#added + 1] = n.dn or "" end end
return _poe2lab_json(added)""")

    def tree_remove(self, node_id: int) -> list[str]:
        """Deallocate a node and everything only reachable through it; returns the names removed."""
        return self._json(f"""
local spec = build.spec
local node = spec.nodes[{int(node_id)}]
if not node or not node.alloc then return _poe2lab_json(_poe2lab_array({{}})) end
if node.type == "ClassStart" or node.type == "AscendClassStart" then error("the class start cannot be removed", 0) end
local removed = _poe2lab_array({{}})
for _, n in ipairs(node.depends or {{ node }}) do removed[#removed + 1] = n.dn or "" end
spec:DeallocNode(node)
spec:BuildAllDependsAndPaths()
build.buildFlag = true
build.calcsTab:BuildOutput()
return _poe2lab_json(removed)""")

    def what_if(self, add_nodes=(), remove_nodes=(), mods=(), enemy_mods=(), config=None,
                remove_slot: str | None = None, disable_gems=(), main_socket_group: int | None = None,
                replace_item: tuple[str, str] | None = None,
                replace_runes: tuple[str, list[str]] | None = None) -> dict[str, float]:
        """Recalculate without changing the build, as if:
        - passive nodes were added/removed,
        - extra player mod lines were present (e.g. "10% increased Attack Speed"),
        - extra enemy mod lines were present (e.g. "50% increased Damage"),
        - Configuration tab values were set (e.g. {"enemyLevel": 79, "enemyCritChance": 100}),
        - the item in remove_slot (e.g. "Ring 1") was taken off,
        - gems given as (socket group, gem index) pairs were disabled,
        - offence was reported for main_socket_group instead of the build's main skill,
        - replace_item = (slot, item text) was equipped instead (PoB format or text copied from the game),
        - replace_runes = (slot, [rune / soul core names per socket]) were socketed into the equipped item."""
        add = ", ".join(str(int(n)) for n in add_nodes)
        remove = ", ".join(str(int(n)) for n in remove_nodes)
        lines = ", ".join(lua_string(m) for m in mods)
        enemy_lines = ", ".join(lua_string(m) for m in enemy_mods)
        cfg = ", ".join(f"[ {lua_string(k)} ] = {_lua_value(v)}" for k, v in (config or {}).items())
        extra = ""
        if sum(x is not None for x in (remove_slot, replace_item, replace_runes)) > 1:
            raise PobError("use only one of remove_slot, replace_item, replace_runes")
        if replace_runes:
            slot_name, names = replace_runes
            runes = ", ".join(lua_string(n) for n in names)
            extra += (f", repSlotName = {lua_string(slot_name)}, repItem = _poe2lab_item_runes("
                      f"{lua_string(self.item_text(slot_name))}, {{ {runes} }})")
        if remove_slot:
            extra += f", repSlotName = {lua_string(remove_slot)}"
        if replace_item:
            slot_name, text = replace_item
            extra += f", repSlotName = {lua_string(slot_name)}, repItem = _poe2lab_item({lua_string(text)})"
        if main_socket_group:
            extra += f", mainSocketGroup = {int(main_socket_group)}"
        gems = ", ".join(f"{{ {int(g)}, {int(i)} }}" for g, i in disable_gems)
        return self._json(f"""
local calcFunc = build.calcsTab:GetMiscCalculator()
local override = {{ addNodes = _poe2lab_nodeset({{ {add} }}), removeNodes = _poe2lab_nodeset({{ {remove} }}){extra} }}
local out = _poe2lab_with_gems_disabled({{ {gems} }}, function()
  return _poe2lab_with_setup({{ {cfg} }}, {{ {lines} }}, {{ {enemy_lines} }},
    function() return calcFunc(override, false) end)
end)
return _poe2lab_numbers(out)""")

    def gems(self) -> list[dict]:
        """Every gem in every socket group; color is PoB's colour code (green = dexterity, blue = int, red = str)."""
        return self._json("""
local out = _poe2lab_array({})
for gi, g in ipairs(build.skillsTab.socketGroupList) do
  for i, gem in ipairs(g.gemList) do
    local d = gem.gemData
    if d then
      out[#out + 1] = { group = gi, index = i, name = d.name, support = d.grantedEffect.support and true or false,
                        enabled = gem.enabled ~= false, color = tostring(gem.color or d.color or "") }
    end
  end
end
return _poe2lab_json(out)""")

    def equipped_items(self) -> list[dict]:
        """Items in gear slots (jewels excluded)."""
        return self._json("""
local out = _poe2lab_array({})
for _, slot in ipairs(build.itemsTab.orderedSlots) do
  local item = not slot.nodeId and build.itemsTab.items[slot.selItemId]
  if item then
    out[#out + 1] = { slot = slot.slotName, name = item.name or "", rarity = item.rarity or "" }
  end
end
return _poe2lab_json(out)""")

    def export_item_data(self, mod_sets=("Item", "Desecrated")) -> dict:
        """Item affixes (per set) and item bases from PoB's game data."""
        sets = ", ".join(lua_string(s) for s in mod_sets)
        return self._json(f"""
local function arr(t)
  local out = _poe2lab_array({{}})
  for i, v in ipairs(t or {{}}) do out[i] = v end
  return out
end
local mods = _poe2lab_array({{}})
for _, setName in ipairs({{ {sets} }}) do
  for id, m in pairs(data.itemMods[setName] or {{}}) do
    local hashes = _poe2lab_array({{}})
    for h in pairs(m.tradeHashes or {{}}) do hashes[#hashes + 1] = tostring(h) end
    mods[#mods + 1] = {{ id = id, set = setName, type = m.type or "", affix = m.affix or "", lines = arr(m),
      level = m.level or 0, group = m.group or id, weightKey = arr(m.weightKey), weightVal = arr(m.weightVal),
      tags = arr(m.modTags), tradeHashes = hashes }}
  end
end
local bases = _poe2lab_array({{}})
for name, b in pairs(data.itemBases) do
  local tags = _poe2lab_array({{}})
  for t, on in pairs(b.tags or {{}}) do if on then tags[#tags + 1] = t end end
  bases[#bases + 1] = {{ name = name, type = b.type or "", subType = b.subType or "", tags = tags,
    implicit = b.implicit or "", level = (b.req and b.req.level) or 0 }}
end
return _poe2lab_json({{ mods = mods, bases = bases }})""")

    def equipped_item_details(self) -> list[dict]:
        """Equipped gear with base tags, item level, corruption and explicit lines (for affix analysis)."""
        return self._json("""
local out = _poe2lab_array({})
for _, slot in ipairs(build.itemsTab.orderedSlots) do
  local item = not slot.nodeId and build.itemsTab.items[slot.selItemId]
  if item and item.base then
    local tags = _poe2lab_array({})
    for t, on in pairs(item.base.tags or {}) do if on then tags[#tags + 1] = t end end
    local explicit = _poe2lab_array({})
    for _, ml in ipairs(item.explicitModLines or {}) do
      explicit[#explicit + 1] = { line = ml.line, crafted = ml.crafted and true or false,
        fractured = ml.fractured and true or false, desecrated = ml.desecrated and true or false }
    end
    out[#out + 1] = { slot = slot.slotName, name = item.name or "", baseName = item.baseName or "",
      type = item.type or "", rarity = item.rarity or "", itemLevel = item.itemLevel or 0,
      corrupted = item.corrupted and true or false, tags = tags, explicit = explicit }
  end
end
return _poe2lab_json(out)""")

    def export_essences(self) -> list[dict]:
        """Essences: name, tier level and the mod id they guarantee per item class."""
        essences = self._raw_essences()
        for e in essences:
            if not isinstance(e["mods"], dict):  # an empty Lua table encodes as []
                e["mods"] = {}
        return essences

    def _raw_essences(self) -> list[dict]:
        return self._json("""
local out = _poe2lab_array({})
for id, e in pairs(data.essences) do
  local mods = {}
  for itemClass, modId in pairs(e.mods or {}) do mods[itemClass] = modId end
  out[#out + 1] = { id = id, name = e.name, type = e.type or "", tierLevel = e.tierLevel or 0, mods = mods }
end
return _poe2lab_json(out)""")

    def socket_info(self, slot: str) -> dict:
        """Sockets of the equipped item, the runes / soul cores in them and which augments fit it."""
        return self._json(f"""
local slot = build.itemsTab.slots[ {lua_string(slot)} ]
local item = slot and build.itemsTab.items[slot.selItemId]
if not item then error("no item in slot", 0) end
local runes = _poe2lab_array({{}})
for i = 1, item.itemSocketCount do runes[i] = item.runes[i] or "None" end
local baseType, specificType = item:GetSocketedAugmentTypes()
local options = _poe2lab_array({{}})
for name, rune in pairs(data.itemMods.Runes) do
  local mod = (baseType and rune[baseType]) or rune[specificType]
  if mod then
    local lines = _poe2lab_array({{}})
    for i, l in ipairs(mod) do lines[i] = l end
    options[#options + 1] = {{ name = name, type = mod.type or "", limit = mod.limit or 0, levelReq = mod.levelReq or 0,
      corrupted = mod.canSocketInCorruptedSanctified and true or false,
      unique = mod.canSocketInUniqueItems and true or false, lines = lines }}
  end
end
return _poe2lab_json({{ sockets = item.itemSocketCount, runes = runes, corrupted = item.corrupted and true or false,
  rarity = item.rarity or "", baseType = baseType or "", specificType = specificType or "", options = options }})""")

    def _local_describer(self, statdesc_dir: Path) -> bool:
        """A second copy of PoB's StatDescriber reading description files from `statdesc_dir` (same layout as
        Data/StatDescriptions, texts in another language). Kept per directory; False if it cannot be built."""
        path = statdesc_dir.resolve().as_posix()
        return self._lua(f"""
_poe2lab_describers = _poe2lab_describers or {{}}
local dir = {lua_string(path)}
if not _poe2lab_describers[dir] then
  local f = io.open("Modules/StatDescriber.lua", "rb")
  if not f then return "no" end
  local src = f:read("*a"); f:close()
  src = src:gsub('"Data/StatDescriptions/', function() return '"' .. dir .. '/' end)
  local chunk = loadstring(src, "StatDescriberLocal")
  if not chunk then return "no" end
  _poe2lab_describers[dir] = chunk()
end
_poe2lab_localDescribe = _poe2lab_describers[dir]
return 'yes'""") == "yes"

    def mechanics_raw(self, statdesc_dir: Path | None = None) -> dict:
        """Per skill (every gem effect in every socket group): description, readable stat lines, and the stats PoB
        has no mapping for (silently ignored in calculations). Per item: lines PoB could not parse, and the full text
        of unique items. Filtering and interpretation live in poe2lab.knowledge.

        With `statdesc_dir` (stat descriptions in the player's language, see poe2lab.gamedata) every readable line
        also comes in that language: `linesLocal` / `textLocal`."""
        local = bool(statdesc_dir) and self._local_describer(statdesc_dir)
        if not local:
            self._lua("_poe2lab_localDescribe = nil")
        return self._json("""
local function arr(t) return _poe2lab_array(t or {}) end
local function run(fn, stats, scope)
  if not fn then return arr({}) end
  local ok, lines = pcall(fn, stats, scope)
  if not ok or not lines then return arr({}) end
  local out = arr({})
  for i, l in ipairs(lines) do out[i] = StripEscapes(l) end
  return out
end
local function describe(stats, scope) return run(data.describeStats, stats, scope) end
local function describeLocal(stats, scope) return run(_poe2lab_localDescribe, stats, scope) end
local skills = arr({})
local seen = {}
for gi, g in ipairs(build.skillsTab.socketGroupList) do
  for _, gem in ipairs(g.gemList) do
    local d = gem.gemData
    if d and gem.enabled ~= false then
      for _, ge in ipairs({ d.grantedEffect, d.secondaryGrantedEffect }) do
        local key = gi .. ":" .. ge.id
        if not seen[key] then
          seen[key] = true
          local sets = arr({})
          for _, set in ipairs(ge.statSets or {}) do
            local ok, stats = pcall(calcLib.buildSkillInstanceStats, gem, ge, set, false)
            stats = ok and stats or {}
            local unmapped = arr({})
            for stat, value in pairs(stats) do
              if not set.statMap[stat] then
                unmapped[#unmapped + 1] = { stat = stat, value = value,
                  text = describe({ [stat] = value }, set.statDescriptionScope),
                  textLocal = describeLocal({ [stat] = value }, set.statDescriptionScope) }
              end
            end
            sets[#sets + 1] = { label = set.label or "", lines = describe(stats, set.statDescriptionScope),
                                linesLocal = describeLocal(stats, set.statDescriptionScope), unmapped = unmapped }
          end
          skills[#skills + 1] = { group = gi, name = ge.name, support = ge.support and true or false,
            description = ge.description or "", statSets = sets }
        end
      end
    end
  end
end
local items = arr({})
for _, slot in ipairs(build.itemsTab.orderedSlots) do
  local item = not slot.nodeId and build.itemsTab.items[slot.selItemId]
  if item then
    local unparsed = arr({})
    for _, list in ipairs({ item.implicitModLines or {}, item.explicitModLines or {}, item.runeModLines or {} }) do
      for _, ml in ipairs(list) do
        if ml.extra or not ml.modList or #ml.modList == 0 then unparsed[#unparsed + 1] = StripEscapes(ml.line) end
      end
    end
    local text = arr({})
    if item.rarity == "UNIQUE" or item.rarity == "RELIC" then
      for _, list in ipairs({ item.implicitModLines or {}, item.explicitModLines or {} }) do
        for _, ml in ipairs(list) do text[#text + 1] = StripEscapes(ml.line) end
      end
    end
    items[#items + 1] = { slot = slot.slotName, name = item.name or "", rarity = item.rarity or "",
                          type = item.type or "", unparsed = unparsed, uniqueText = text }
  end
end
return _poe2lab_json({ skills = skills, items = items })""")

    def set_custom_mods(self, title: str, lines: list[str]):
        """Put mod lines into a Custom Modifiers block of the Configuration tab (replacing a block with the same
        title; empty list removes it) and recalculate. Unlike what_if(mods=...) this persists for every later call."""
        for line in lines:
            if not self.can_parse_mod(line):
                raise PobError(f"PoB cannot parse mod: {line}")
        text = "\n".join(lines)
        self._lua(f"""
local configTab = build.configTab
local list = configTab.configSets[configTab.activeConfigSetId].customModsList
for i = #list, 1, -1 do
  if list[i].title == {lua_string(title)} then table.remove(list, i) end
end
if {lua_string(text)} ~= "" then
  list[#list + 1] = {{ title = {lua_string(title)}, enabled = true, text = {lua_string(text)} }}
end
configTab:BuildModList()
build.calcsTab:BuildOutput()""")

    def equip_item(self, slot: str, item_text: str):
        """Really equip an item (in memory) and recalculate. Unlike what_if(replace_item=...) this persists,
        so several slots can be changed together; equip the old text again to undo."""
        self._lua(f"""
local itemsTab = build.itemsTab
local item = _poe2lab_item({lua_string(item_text)})
itemsTab:AddItem(item, true)
itemsTab.slots[ {lua_string(slot)} ]:SetSelItemId(item.id)
itemsTab:PopulateSlots()
build.calcsTab:BuildOutput()""")

    @contextmanager
    def swapped_items(self, items: dict[str, str | None]):
        """Temporarily wear several items at once (slot -> item text, None = empty slot), recalculated; everything
        is put back on exit. what_if(replace_item=...) changes one slot only."""
        entries = ", ".join(f"[ {lua_string(slot)} ] = {lua_string(text) if text else 'false'}"
                            for slot, text in items.items())
        self._lua(f"""
local itemsTab = build.itemsTab
_poe2lab_swap = {{ saved = {{}}, temp = {{}}, sets = {{}}, main = build.mainSocketGroup }}
-- a weapon the skills cannot use makes PoB move socket groups to the other weapon set; remember the assignment
for i, g in ipairs(build.skillsTab.socketGroupList) do _poe2lab_swap.sets[i] = {{ g.set1, g.set2 }} end
for slotName, text in pairs({{ {entries} }}) do
  local slot = itemsTab.slots[slotName]
  if slot then
    _poe2lab_swap.saved[slotName] = slot.selItemId
    if text then
      local item = _poe2lab_item(text)
      itemsTab:AddItem(item, true)
      table.insert(_poe2lab_swap.temp, item)
      slot:SetSelItemId(item.id)
    else
      slot:SetSelItemId(0)
    end
  end
end
itemsTab:PopulateSlots()
build.calcsTab:BuildOutput()""")
        try:
            yield self
        finally:
            self._lua("""
local itemsTab = build.itemsTab
for slotName, id in pairs(_poe2lab_swap.saved) do itemsTab.slots[slotName]:SetSelItemId(id) end
for _, item in ipairs(_poe2lab_swap.temp) do itemsTab:DeleteItem(item, true) end
for i, g in ipairs(build.skillsTab.socketGroupList) do
  local saved = _poe2lab_swap.sets[i]
  if saved then g.set1, g.set2 = saved[1], saved[2] end
end
build.skillsTab.weaponSetValidityCache = {}
build.mainSocketGroup = _poe2lab_swap.main
_poe2lab_swap = nil
itemsTab:PopulateSlots()
wipeGlobalCache()
build.calcsTab:BuildOutput()""")

    def item_text(self, slot: str) -> str:
        """The equipped item in PoB's text format - edit it and pass it back via what_if(replace_item=...)."""
        text = self._lua(f"""
local slot = build.itemsTab.slots[ {lua_string(slot)} ]
local item = slot and build.itemsTab.items[slot.selItemId]
return item and item.raw""")
        if text is None:
            raise PobError(f"no item in slot {slot!r}")
        return text

    def requirement_sources(self) -> list[dict]:
        """Every attribute requirement PoB checks: items, gems and grouped support gems (PoB's 'Req' breakdowns)."""
        return self._json("""
local out = _poe2lab_array({})
local breakdown = build.calcsTab.calcsEnv.player.breakdown
for _, attr in ipairs({ "Str", "Dex", "Int" }) do
  for _, row in ipairs((breakdown["Req" .. attr] or {}).rowList or {}) do
    out[#out + 1] = { attr = attr, req = row.reqNum, source = row.source,
                      name = StripEscapes(tostring(row.sourceName or "")) }
  end
end
return _poe2lab_json(out)""")

    def attribute_node_counts(self) -> dict[str, int]:
        """Allocated passive attribute nodes (+5 each in PoE2) by chosen attribute."""
        return self._json("""
local counts = { Str = 0, Dex = 0, Int = 0 }
local key = { Strength = "Str", Dexterity = "Dex", Intelligence = "Int" }
for _, node in pairs(build.spec.allocNodes) do
  if node.isAttribute and key[node.dn] then counts[key[node.dn]] = counts[key[node.dn]] + 1 end
end
return _poe2lab_json(counts)""")

    def skill_conditions(self, gem_name: str) -> list[dict]:
        """Configuration checkboxes tied to a gem (e.g. Momentum's 'Moved 2m during Skill use?').
        Effects behind them count as zero in PoB until the box is ticked."""
        return self._json(f"""
local name = {lua_string(gem_name)}
local out = _poe2lab_array({{}})
for _, opt in ipairs(require("Modules.ConfigOptions")) do
  local s = opt.ifSkill
  local match = s == name
  if type(s) == "table" then
    for _, v in ipairs(s) do if v == name then match = true end end
  end
  if match and opt.type == "check" and opt.var then
    out[#out + 1] = {{ var = opt.var, label = StripEscapes(opt.label or opt.var) }}
  end
end
return _poe2lab_json(out)""")

    def config_checkboxes(self) -> list[dict]:
        """Configuration checkboxes PoB shows for this build (its own relevance rules), with their current state."""
        return self._json("""
local out = _poe2lab_array({})
local configTab = build.configTab
for _, opt in ipairs(require("Modules.ConfigOptions")) do
  local control = opt.var and opt.type == "check" and configTab.varControls[opt.var]
  if control then
    local ok, shown = pcall(function() return control:GetProperty("shown") end)
    if ok and shown then
      local skills = _poe2lab_array({})
      if type(opt.ifSkill) == "string" then skills[1] = opt.ifSkill
      elseif type(opt.ifSkill) == "table" then for i, s in ipairs(opt.ifSkill) do skills[i] = s end end
      out[#out + 1] = { var = opt.var, label = StripEscapes(opt.label or opt.var),
                        checked = configTab.input[opt.var] and true or false, skills = skills }
    end
  end
end
return _poe2lab_json(out)""")

    def config(self) -> dict:
        """Current Configuration tab values explicitly set in the build."""
        return self._json("return _poe2lab_json(build.configTab.input)")

    def can_parse_mod(self, line: str) -> bool:
        return self._lua(f"""
local mods, extra = modLib.parseMod({lua_string(line)})
return (mods and not extra) and "yes" or "no" """) == "yes"

    def logs(self, clear: bool = True) -> list[str]:
        lines = self._json("return _poe2lab_json(_poe2lab_array(_POE2LAB_LOG))")
        if clear:
            self._lua("_POE2LAB_LOG = {}")
        return lines
