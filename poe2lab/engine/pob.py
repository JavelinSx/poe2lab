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
"""


class PobError(RuntimeError):
    pass


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

    def what_if(self, add_nodes=(), remove_nodes=()) -> dict[str, float]:
        """Recalculate as if passive nodes were added/removed, without changing the build."""
        add = ", ".join(str(int(n)) for n in add_nodes)
        remove = ", ".join(str(int(n)) for n in remove_nodes)
        return self._json(f"""
local calcFunc = build.calcsTab:GetMiscCalculator()
local out = calcFunc({{ addNodes = _poe2lab_nodeset({{ {add} }}), removeNodes = _poe2lab_nodeset({{ {remove} }}) }}, false)
return _poe2lab_numbers(out)""")

    def logs(self, clear: bool = True) -> list[str]:
        lines = self._json("return _poe2lab_json(_poe2lab_array(_POE2LAB_LOG))")
        if clear:
            self._lua("_POE2LAB_LOG = {}")
        return lines
