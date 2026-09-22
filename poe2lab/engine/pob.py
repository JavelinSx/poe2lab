import json
from pathlib import Path

from .luahost import DEFAULT_POB_ROOT, LuaError, LuaHost, lua_string
from .pobcode import decode_pob_code

_HELPERS = r"""
local dkjson = require "dkjson"

function _poe2lab_json(value)
  return dkjson.encode(value)
end

function _poe2lab_numbers(t)
  local res = {}
  for k, v in pairs(t) do
    if type(v) == "number" and v == v and v ~= math.huge and v ~= -math.huge then
      res[k] = v
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
        self._lua(f"loadBuildFromXML({lua_string(xml)}, {lua_string(name)})")
        self._check_loaded()

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

    def what_if(self, add_nodes=(), remove_nodes=(), mods=(), enemy_mods=(), config=None,
                remove_slot: str | None = None, disable_gems=(), main_socket_group: int | None = None,
                replace_item: tuple[str, str] | None = None) -> dict[str, float]:
        """Recalculate without changing the build, as if:
        - passive nodes were added/removed,
        - extra player mod lines were present (e.g. "10% increased Attack Speed"),
        - extra enemy mod lines were present (e.g. "50% increased Damage"),
        - Configuration tab values were set (e.g. {"enemyLevel": 79, "enemyCritChance": 100}),
        - the item in remove_slot (e.g. "Ring 1") was taken off,
        - gems given as (socket group, gem index) pairs were disabled,
        - offence was reported for main_socket_group instead of the build's main skill,
        - replace_item = (slot, item text) was equipped instead (PoB format or text copied from the game)."""
        add = ", ".join(str(int(n)) for n in add_nodes)
        remove = ", ".join(str(int(n)) for n in remove_nodes)
        lines = ", ".join(lua_string(m) for m in mods)
        enemy_lines = ", ".join(lua_string(m) for m in enemy_mods)
        cfg = ", ".join(f"[ {lua_string(k)} ] = {_lua_value(v)}" for k, v in (config or {}).items())
        extra = ""
        if remove_slot and replace_item:
            raise PobError("use either remove_slot or replace_item")
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
