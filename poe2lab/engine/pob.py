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
                remove_slot: str | None = None) -> dict[str, float]:
        """Recalculate without changing the build, as if:
        - passive nodes were added/removed,
        - extra player mod lines were present (e.g. "10% increased Attack Speed"),
        - extra enemy mod lines were present (e.g. "50% increased Damage"),
        - Configuration tab values were set (e.g. {"enemyLevel": 79, "enemyCritChance": 100}),
        - the item in remove_slot (e.g. "Ring 1") was taken off."""
        add = ", ".join(str(int(n)) for n in add_nodes)
        remove = ", ".join(str(int(n)) for n in remove_nodes)
        lines = ", ".join(lua_string(m) for m in mods)
        enemy_lines = ", ".join(lua_string(m) for m in enemy_mods)
        cfg = ", ".join(f"[ {lua_string(k)} ] = {_lua_value(v)}" for k, v in (config or {}).items())
        slot = f", repSlotName = {lua_string(remove_slot)}" if remove_slot else ""
        return self._json(f"""
local calcFunc = build.calcsTab:GetMiscCalculator()
local override = {{ addNodes = _poe2lab_nodeset({{ {add} }}), removeNodes = _poe2lab_nodeset({{ {remove} }}){slot} }}
local out = _poe2lab_with_setup({{ {cfg} }}, {{ {lines} }}, {{ {enemy_lines} }},
  function() return calcFunc(override, false) end)
return _poe2lab_numbers(out)""")

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
