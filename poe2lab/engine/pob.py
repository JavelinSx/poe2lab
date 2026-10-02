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
  -- an attack's hit lives in its weapon's table (the top-level AverageHit is 0)
  for _, hand in ipairs({ "MainHand", "OffHand" }) do
    if type(t[hand]) == "table" then
      for k, v in pairs(t[hand]) do
        if (k == "AverageHit" or k:match("HitAverage$")) and _poe2lab_finite(v) then res[hand .. "." .. k] = v end
      end
    end
  end
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

-- exact: the quality as the text has it; otherwise PoB's rule for a pasted item (below 20% counts as 20%: the
-- player would quality it) - right for a candidate, wrong for the build's own item or one edited on purpose
function _poe2lab_item(text, exact)
  local item = new("Item"):Item(text)
  if not item.base then error("PoB could not read the item (unknown base?)", 0) end
  if not exact then item:NormaliseQuality() end
  return item
end

-- an item with its quality, sockets, runes and catalyst (its number, 0: none; and its quality) set (nil: as it is);
-- runes past the sockets go
function _poe2lab_item_edit(text, quality, sockets, runes, catalyst, catalystQuality)
  local item = _poe2lab_item(text, true)
  if quality then item.quality = quality end
  if catalyst then item.catalyst = catalyst > 0 and catalyst or nil end
  if catalystQuality then item.catalystQuality = catalystQuality end
  if sockets then
    wipeTable(item.sockets)
    for i = 1, sockets do item.sockets[i] = { group = i - 1 } end
    item.itemSocketCount = sockets
  end
  if runes then for i = 1, item.itemSocketCount do item.runes[i] = runes[i] or "None" end end
  for i = #item.runes, item.itemSocketCount + 1, -1 do item.runes[i] = nil end
  item:UpdateRunes()
  item:BuildAndParseRaw()
  return item
end

-- an item as the page shows it: name, base, rarity and its lines (the unique's chosen variant only)
function _poe2lab_item_view(item, slotName)
  local function lines(list)
    local out = _poe2lab_array({})
    for _, ml in ipairs(list or {}) do
      if item:CheckModLineVariant(ml) then
        out[#out + 1] = { line = ml.line, crafted = ml.crafted and true or false,
          fractured = ml.fractured and true or false, desecrated = ml.desecrated and true or false }
      end
    end
    return out
  end
  local tags = _poe2lab_array({})
  for t, on in pairs(item.base and item.base.tags or {}) do if on then tags[#tags + 1] = t end end
  return { slot = slotName, name = item.name or "", baseName = item.baseName or "", type = item.type or "",
    rarity = item.rarity or "", itemLevel = item.itemLevel or 0, corrupted = item.corrupted and true or false,
    quality = item.quality or 0, reqLevel = item.requirements and item.requirements.level or 0, tags = tags,
    implicit = lines(item.implicitModLines), explicit = lines(item.explicitModLines),
    runes = lines(item.runeModLines), enchant = lines(item.enchantModLines) }
end

-- the equipped item's own text with other runes: its quality stays what it is
function _poe2lab_item_runes(text, names)
  return _poe2lab_item_edit(text, nil, nil, names)
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


# PoB outputs a skill's triggers are made of (skill_damage): our key -> PoB's output
TRIGGER_OUTPUTS = {"hit": "AverageHit", "hitSpeed": "HitSpeed", "cooldown": "Cooldown", "manaCost": "ManaCost",
                   "igniteOnHit": "IgniteChanceOnHit", "igniteOnCrit": "IgniteChanceOnCrit",
                   "shockOnHit": "ShockChanceOnHit", "shockOnCrit": "ShockChanceOnCrit",
                   "freezeBuildup": "FreezeBuildupAvg", "igniteDps": "IgniteDPS", "igniteDuration": "IgniteDuration",
                   "threshold": "EnemyAilmentThreshold", "duration": "Duration"}


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
  ascendancy = (build.spec.curAscendClassId or 0) > 0 and build.spec.curAscendClassName or "",
  level = build.characterLevel,
  mainSocketGroup = build.mainSocketGroup,
  mainActiveSkill = (build.skillsTab.socketGroupList[build.mainSocketGroup] or {}).mainActiveSkill or 1,
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
        is restored). For a main skill PoB cannot compute (0 DPS) this shows where the damage actually is. With each
        skill's own crit chance and multiplier, speed and hit chance: in the game crit is each skill's own (its base,
        its supports, its modifiers), not the character's."""
        group = int(self._lua("return build.mainSocketGroup"))
        g = f"build.skillsTab.socketGroupList[{group}]"
        if not self._json(f"return _poe2lab_json({g} ~= nil)"):
            return []  # no skills yet: a build just made (poe2lab.newbuild)
        active = int(self._lua(f"return {g}.mainActiveSkill or 1"))
        out = []
        try:
            for g in self.socket_groups():
                if not g["enabled"]:
                    continue
                for i, name in enumerate(g["skills"], 1):
                    self.set_main_skill(g["index"], i)
                    o = self.what_if(config=config)
                    # what a triggered skill's own numbers are made of (poe2lab.analysis.triggers): the hit it
                    # deals, how often the skill hits, its ailments, and the enemy's ailment threshold
                    extra = {k: o.get(src) or 0.0 for k, src in TRIGGER_OUTPUTS.items()}
                    extra["hit"] = extra["hit"] or o.get("MainHand.AverageHit") or o.get("OffHand.AverageHit") or 0.0
                    out.append({"group": g["index"], "skill": i, "name": name, "dps": o["CombinedDPS"],
                                "crit": o.get("CritChance") or 0.0, "critMulti": o.get("CritMultiplier") or 0.0,
                                "speed": o.get("Speed") or 0.0, "hitChance": o.get("HitChance") or 0.0} | extra)
        finally:
            # back to the build's own choice as it was, even a group with no active skill left (a skill its item
            # grants, missing from a planner file): no range check here
            self._lua(f"build.mainSocketGroup = {group}\n"
                      f"local g = build.skillsTab.socketGroupList[{group}]\n"
                      f"if g then g.mainActiveSkill = {active} end")
            self.recalc()
        return sorted(out, key=lambda x: -x["dps"])

    @contextmanager
    def main_skill_of(self, group: int):
        """Calculations inside take the group's first active skill as the main one; the build's choice is back on
        exit."""
        before = int(self._lua("return build.mainSocketGroup"))
        g = f"build.skillsTab.socketGroupList[{before}]"
        active = int(self._lua(f"return {g} and {g}.mainActiveSkill or 1"))
        if group != before:
            self.set_main_skill(group, 1)
        try:
            yield
        finally:
            if group != before:
                self._lua(f"build.mainSocketGroup = {before}\n"
                          f"local g = build.skillsTab.socketGroupList[{before}]\n"
                          f"if g then g.mainActiveSkill = {active} end")
                self.recalc()

    def stat_sources(self, names: list[str], player: bool = False, flags: tuple[str, ...] = ()) -> dict:
        """PoB's modifiers to each stat as the main skill sees them (`player`: the character's own, for defences), by
        type (BASE, INC, MORE): each with its value, where it comes from by name (a passive and its kind, an item, a
        gem, a jewel in its socket) and the conditions it waits for - with the Configuration box that is each one's.
        Also the main skill's base critical chance (its weapon's for an attack), whether it is an attack, its weapon's
        damage by type and the `flags` it has."""
        stats = ", ".join(lua_string(n) for n in names)
        flag_list = ", ".join(lua_string(f) for f in flags)
        return self._json(f"""
local env = build.calcsTab.mainEnv
local skill = env and env.player.mainSkill
local db = {'env and env.player.modDB' if player else 'skill and skill.skillModList'}
local cfg = {'nil' if player else 'skill and skill.skillCfg'}
local boxes = {{}}
for _, opt in ipairs(require("Modules.ConfigOptions")) do
  if opt.type == "check" and opt.var then
    local box = {{ var = opt.var, label = StripEscapes(opt.label or opt.var) }}
    for _, key in ipairs({{ "ifCond", "ifEnemyCond" }}) do
      local c = opt[key]
      for _, v in ipairs(type(c) == "table" and c or {{ c }}) do
        local k = (key == "ifEnemyCond" and "enemy:" or "") .. v
        if not boxes[k] then boxes[k] = box end
      end
    end
    -- a box that names no condition is named after it: conditionEnemyBlinded is the enemy's Blinded
    local enemy, own = opt.var:match("^conditionEnemy(.+)$"), opt.var:match("^condition(.+)$")
    if enemy and not boxes["enemy:" .. enemy] then boxes["enemy:" .. enemy] = box
    elseif own and not enemy and not boxes[own] then boxes[own] = box end
  end
end
local function sourceOf(src)
  local kind, rest = src:match("^([^:]+):?(.*)$")
  local o = {{ kind = kind or src, name = rest ~= "" and rest or (kind or src) }}
  if kind == "Tree" then
    local id = tonumber(rest:match("^(%d+)"))
    local node = id and build.spec.nodes[id]
    if node then
      o.name, o.nodeType, o.asc = node.dn or node.name, node.type, node.ascendancyName ~= nil
      local socket = build.itemsTab.sockets[id]
      local jewel = socket and build.itemsTab.items[socket.selItemId]
      if jewel then o.name, o.jewel = jewel.name, true end
    end
  elseif kind == "Item" then
    o.name = rest:match("^%d+:(.+)$") or rest
  elseif kind == "Skill" then
    local ge = data.skills[rest]
    o.name = ge and ge.name or rest
  end
  return o
end
local function condsOf(mod)
  local c = _poe2lab_array({{}})
  for _, tag in ipairs(mod) do
    if type(tag) == "table" and (tag.type == "Condition" or tag.type == "ActorCondition") then
      local enemy = tag.type == "ActorCondition" and tag.actor == "enemy"
      for _, v in ipairs(tag.varList or {{ tag.var }}) do
        local box = boxes[(enemy and "enemy:" or "") .. v]
        c[#c + 1] = {{ var = v, enemy = enemy, neg = tag.neg and true or false, box = box and box.var or nil,
                       label = box and box.label or nil }}
      end
    end
  end
  return c
end
local out = {{ stats = {{}}, flags = {{}} }}
if db then
  for _, name in ipairs({{ {stats} }}) do
    local per = {{}}
    for _, t in ipairs({{ "BASE", "INC", "MORE" }}) do
      local rows = _poe2lab_array({{}})
      for _, r in ipairs(db:Tabulate(t, cfg, name)) do
        rows[#rows + 1] = {{ value = r.value, source = sourceOf(r.mod.source or "?"), conds = condsOf(r.mod) }}
      end
      per[t] = rows
    end
    out.stats[name] = per
  end
  for _, f in ipairs({{ {flag_list} }}) do out.flags[f] = db:Flag(cfg, f) and true or false end
end
if skill then
  local w = env.player.weaponData1
  out.skill = skill.activeEffect.grantedEffect.name
  out.attack = (skill.skillTypes and skill.skillTypes[SkillType.Attack]) and true or false
  out.weaponCrit = w and w.CritChance or nil
  out.weapon = w and w.name or nil
  -- the weapon's own damage by type (its local mods counted): what an attack starts from
  for _, t in ipairs({{ "Physical", "Fire", "Cold", "Lightning", "Chaos" }}) do
    if w and (w[t .. "Max"] or 0) > 0 then
      out.weaponDamage = out.weaponDamage or {{}}
      out.weaponDamage[t] = {{ min = w[t .. "Min"] or 0, max = w[t .. "Max"] }}
    end
  end
  out.skillCrit = skill.skillData and skill.skillData.CritChance or nil
  out.attackRate = w and w.AttackRate or nil
  out.castTime = skill.activeEffect.grantedEffect.castTime or nil
end
return _poe2lab_json(out)""")

    def stat_names(self, parts: tuple[str, ...]) -> list[str]:
        """The names of the modifiers the main skill sees (its own and the character's) that contain one of `parts`:
        PoB's links between stats, "DamageGainAsCold", "EvasionGainAsDeflection" - for stat_sources."""
        wanted = ", ".join(lua_string(p) for p in parts)
        return self._json(f"""
local env = build.calcsTab.mainEnv
local seen, out = {{}}, _poe2lab_array({{}})
local function add(name)
  if seen[name] then return end
  for _, p in ipairs({{ {wanted} }}) do
    if name:find(p, 1, true) then seen[name] = true out[#out + 1] = name return end
  end
end
if env then
  for name in pairs(env.player.modDB.mods) do add(name) end
  local skill = env.player.mainSkill
  if skill then for _, m in ipairs(skill.skillModList) do add(m.name) end end
end
table.sort(out)
return _poe2lab_json(out)""")

    def _stat_set(self, group: int, name: str, index: int | None) -> list[dict]:
        """Show stat set `index` of a skill (its other parts: Elemental Expression's explosion, bolt and wave) in
        every later calculation; None puts back what the build had. Returns the skill's stat sets."""
        return self._json(f"""
_poe2lab_saved_sets = _poe2lab_saved_sets or {{}}
local g = build.skillsTab.socketGroupList[{int(group)}]
local key, out = "{int(group)}:" .. {lua_string(name)}, _poe2lab_array({{}})
for _, gem in ipairs(g and g.gemList or {{}}) do
  local ge = gem.gemData and gem.gemData.grantedEffect
  if ge and ge.name == {lua_string(name)} then
    for i, set in ipairs(ge.statSets or {{}}) do out[#out + 1] = {{ index = i, label = set.label or "" }} end
    local index = {'nil' if index is None else int(index)}
    if index == nil then
      local saved = _poe2lab_saved_sets[key]
      if saved then gem.statSet, gem.statSetCalcs = saved[1], saved[2] end
      _poe2lab_saved_sets[key] = nil
    else
      if not _poe2lab_saved_sets[key] then _poe2lab_saved_sets[key] = {{ gem.statSet, gem.statSetCalcs }} end
      gem.statSet = {{ [ge.id] = index, index = index }}
      gem.statSetCalcs = {{ [ge.id] = index, index = index }}
    end
    break
  end
end
return _poe2lab_json(out)""")

    @contextmanager
    def shown_stat_set(self, group: int, name: str, index: int):
        """Calculations inside show stat set `index` of the skill; the build's own choice is back on exit."""
        self._stat_set(group, name, index)
        try:
            yield
        finally:
            self._stat_set(group, name, None)

    def stat_set_hits(self, group: int, name: str, config: dict | None = None, disable_gems=()) -> list[dict]:
        """A skill made of several stat sets priced set by set - each one's hit and DPS as PoB computes them when
        that set is shown. Empty for a skill of one set. PoB shows the first set unless told otherwise, and the
        first set of Elemental Expression deals no damage: its explosion, bolt and wave are the others."""
        sets = self._stat_set(group, name, None)
        if len(sets) < 2:
            return []
        out = []
        for s in sets:
            with self.shown_stat_set(group, name, s["index"]):
                o = self.what_if(config=config, main_socket_group=group, disable_gems=disable_gems)
            out.append(s | {"hit": o.get("AverageHit") or 0.0, "dps": o.get("CombinedDPS") or 0.0})
        return out

    def gem_conditions(self, group: int, gem_index: int) -> list[dict]:
        """The Configuration boxes a gem's own modifiers wait for and this build leaves unticked: Retreat's "if
        you've dealt a melee hit in the past two seconds" is "Have you Melee Hit Recently?" - until it is ticked,
        PoB gives the gem nothing. Conditions on the enemy too ("Is the enemy Blinded?")."""
        return self._json(f"""
local g = build.skillsTab.socketGroupList[{int(group)}]
local gem = g and g.gemList[{int(gem_index)}]
local ge = gem and gem.gemData and gem.gemData.grantedEffect
local own, enemy = {{}}, {{}}
local function tag(t)
  if t.neg then return end
  for _, v in ipairs(t.varList or {{ t.var }}) do
    if t.type == "Condition" and not t.actor then own[v] = true
    elseif t.type == "ActorCondition" and t.actor == "enemy" then enemy[v] = true end
  end
end
local function scan(statMap)
  for _, mods in pairs(statMap or {{}}) do
    for _, m in ipairs(type(mods) == "table" and mods or {{}}) do
      for _, t in ipairs(type(m) == "table" and m or {{}}) do if type(t) == "table" then tag(t) end end
    end
  end
end
if ge then
  scan(ge.statMap)
  for _, set in ipairs(ge.statSets or {{}}) do scan(set.statMap) end
end
local function wanted(cond, set)
  if type(cond) == "table" then
    for _, c in ipairs(cond) do if set[c] then return true end end
    return false
  end
  return cond ~= nil and set[cond] == true
end
local out, seen = _poe2lab_array({{}}), {{}}
for _, opt in ipairs(require("Modules.ConfigOptions")) do
  -- a box that names no condition is named after it: conditionEnemyBlinded is the enemy's Blinded
  local byEnemy = opt.var and opt.var:match("^conditionEnemy(.+)$")
  local byOwn = opt.var and not byEnemy and opt.var:match("^condition(.+)$")
  if opt.type == "check" and opt.var and not seen[opt.var] and not build.configTab.input[opt.var]
     and (wanted(opt.ifCond, own) or wanted(opt.ifEnemyCond, enemy)
          or (opt.ifEnemyCond == nil and byEnemy and enemy[byEnemy])
          or (opt.ifCond == nil and byOwn and own[byOwn])) then
    seen[opt.var] = true
    out[#out + 1] = {{ var = opt.var, label = StripEscapes(opt.label or opt.var) }}
  end
end
return _poe2lab_json(out)""")

    def trigger_inputs(self) -> list[dict]:
        """For each enabled socket group: its active skills with their base cast time, and the numbers of
        triggers PoB has no calculation for - the energy and trigger stats of its active gems (at their level and
        quality) and the energy gained the group's supports add (poe2lab.analysis.triggers)."""
        return self._json(self._GEM_HELPERS + """
local out = arr({})
local function instanceStats(gem, ge)
  local all = {}
  for _, set in ipairs(ge.statSets or {}) do
    local ok, stats = pcall(calcLib.buildSkillInstanceStats, gem, ge, set, false)
    for k, v in pairs(ok and stats or {}) do all[k] = (all[k] or 0) + v end
  end
  return all
end
for gi, g in ipairs(build.skillsTab.socketGroupList) do
  if g.enabled ~= false then
    local actives, supportGain = arr({}), 0
    for _, gem in ipairs(g.gemList) do
      local ge = gem.gemData and gem.gemData.grantedEffect
      if ge and gem.enabled ~= false then
        local stats = instanceStats(gem, ge)
        if ge.support then
          supportGain = supportGain + (stats["energy_generated_+%"] or 0)
        else
          local energy = {}
          for k, v in pairs(stats) do
            if k:find("energy") or k:find("trigger") then energy[k] = v end
          end
          actives[#actives + 1] = { name = ge.name, castTime = ge.castTime or 0, stats = energy,
                                    description = ge.description or "" }
        end
      end
    end
    out[#out + 1] = { group = gi, actives = actives, supportEnergy = supportGain }
  end
end
return _poe2lab_json(out)""")

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

    def node_lines(self, ids=None) -> dict[int, list[str]]:
        """Stat lines of passive nodes by id: the given ones, or every allocated node (the ascendancy's too)."""
        pick = ("{" + ", ".join(f"[{int(i)}] = true" for i in ids) + "}") if ids is not None else "nil"
        rows = self._json(f"""
local pick, out = {pick}, _poe2lab_array({{}})
local nodes = pick and build.spec.nodes or build.spec.allocNodes
for id, node in pairs(nodes) do
  if not pick or pick[id] then
    out[#out + 1] = {{ id = id, lines = _poe2lab_array(node.sd or {{}}) }}
  end
end
return _poe2lab_json(out)""")
        return {r["id"]: r["lines"] for r in rows}

    def gem_stat_values(self) -> list[dict]:
        """The enabled gems of the enabled socket groups with their stats' values at the gem's level (PoB's gem data:
        constant stats and the level's own) - `main`: in the main skill's group."""
        return self._json("""
local out = _poe2lab_array({})
for gi, g in ipairs(build.skillsTab.socketGroupList) do
  if g.enabled ~= false then
    for _, gem in ipairs(g.gemList) do
      local d = gem.gemData
      if d and gem.enabled ~= false then
        local values = {}
        for _, set in ipairs(d.grantedEffect.statSets or {}) do
          for _, c in ipairs(set.constantStats or {}) do values[c[1]] = values[c[1]] or c[2] end
          local lv = set.levels and (set.levels[gem.level or 1] or set.levels[1])
          for i, stat in ipairs(set.stats or {}) do
            if lv and type(lv[i]) == "number" then values[stat] = values[stat] or lv[i] end
          end
        end
        out[#out + 1] = { name = d.grantedEffect.name, support = d.grantedEffect.support and true or false,
                          main = gi == build.mainSocketGroup, stats = values }
      end
    end
  end
end
return _poe2lab_json(out)""")

    def allocated_nodes(self) -> list[dict]:
        return self._json("""
local out = _poe2lab_array({})
for id, node in pairs(build.spec.allocNodes) do
  out[#out + 1] = { id = id, name = node.dn or node.name or "", type = node.type or "",
                    ascendancy = node.ascendancyName or "" }
end
return _poe2lab_json(out)""")

    def tree_graph(self) -> dict:
        """The passive tree to draw: every node of the main tree and of the build's own ascendancy with its position
        (PoB's own layout), type, name, stat lines, links, group centre and orbit radius (links along one orbit are
        arcs), whether it is allocated, its size and frame as PoB draws them (sz, fs: the icon's and the frame's width;
        fr: the frame, in `frames` by the allocated state's name) and a taken socket's jewel; plus the class,
        ascendancy and points used, and where the game's art for all this is in PoB's tree textures.
        Weapon sets: `mode` is the set a node is taken in (0: the main tree, 1, 2: weapon set I, II); `wc` - what a
        node costs taken in set I and II, when that differs from `cost`; `glob` - a keystone or a jewel socket (taken
        on the main tree only), `wnear` - one that cannot be taken now, being next to a weapon set's branch."""
        return self._json("""
local spec, tree = build.spec, build.spec.tree
-- no ascendancy chosen yet (PoB calls it "None"): every ascendancy of the class is shown, to choose from
local asc = spec.curAscendClassId and spec.curAscendClassId > 0 and spec.curAscendClassName or nil
local shown = {}
if asc then shown[asc] = true
else for i, a in pairs(spec.curClass.classes or {}) do if i > 0 and a.name then shown[a.name] = true end end end
-- the game's pictures in PoB's tree textures (a file and its layer): the nodes' frames, the jewels in sockets
local function atlas(name)
  if not name then return nil end
  for file, names in pairs(tree.ddsCoords or {}) do
    if names[name] then return { file = file, layer = names[name] } end
  end
end
local frames = {}
local function frameOf(ov)  -- a frame's three states by the allocated one's name, each kept once
  if not ov or not ov.alloc then return "" end
  if not frames[ov.alloc] then
    frames[ov.alloc] = { alloc = atlas(ov.alloc) or false, path = atlas(ov.path) or false, unalloc = atlas(ov.unalloc) or false }
  end
  return ov.alloc
end
-- a weapon set's cost of each node: PoB's GetAllocationPath for all nodes at once - from the nodes taken in the
-- main tree or in that set, through nodes not taken (the other set's branch is a wall)
local function open(n)
  for _, nid in ipairs(n.unlockConstraint and n.unlockConstraint.nodes or {}) do
    if not spec.nodes[nid].alloc then return false end
  end
  return true
end
local function setCosts(m)
  local dist, queue, o = {}, {}, 1
  for _, n in pairs(spec.allocNodes) do
    if spec:CanPathThroughAllocMode(m, n) then dist[n] = 0; queue[#queue + 1] = n end
  end
  while queue[o] do
    local n = queue[o]
    o = o + 1
    if open(n) then
      for _, other in ipairs(n.linked or {}) do
        if dist[other] == nil and open(other) and (not other.alloc or spec:CanPathThroughAllocMode(m, other))
           and n.type ~= "Mastery" and other.type ~= "ClassStart" and other.type ~= "AscendClassStart"
           and (n.ascendancyName == other.ascendancyName or (dist[n] == 0 and not other.ascendancyName)) then
          dist[other] = dist[n] + 1
          queue[#queue + 1] = other
        end
      end
    end
  end
  return dist
end
local setCost = { setCosts(1), setCosts(2) }
-- PoB's rule for keystones and jewel sockets: the main tree only, and not while a weapon set's branch touches them
local function global(node) return node.type == "Keystone" or node.type == "Socket" or node.containJewelSocket end
local function nearSet(node)
  for i = 2, #(node.path or {}) do
    if node.path[i].alloc and (node.path[i].allocMode or 0) > 0 then return true end
  end
  for _, other in ipairs(node.linked or {}) do
    if other.alloc and (other.allocMode or 0) > 0 then return true end
  end
  return false
end
local nodes = _poe2lab_array({})
for id, node in pairs(spec.nodes) do
  if node.x and node.type ~= "OnlyImage" and (not node.ascendancyName or shown[node.ascendancyName]) then
    local links = _poe2lab_array({})
    for _, other in ipairs(node.linked or {}) do links[#links + 1] = other.id end
    -- the connections as the tree data defines them (each once, on one of its two nodes): an orbit other than 0
    -- makes the line an arc of that orbit's radius through both nodes (PoB's BuildConnector)
    local arcs = _poe2lab_array({})
    for _, c in pairs(node.connections or {}) do arcs[#arcs + 1] = { id = c.id, orbit = c.orbit or 0 } end
    local g = node.group  -- PoB's group tables carry no id: the group's number is node.g
    -- what a click would do: allocate the path to it (cost: points) or take it off with what hangs on it (drop)
    local cost = (not node.alloc and node.path) and #node.path or 0
    local drop = node.alloc and #(node.depends or {}) or 0
    local wc = false
    if not node.alloc and not node.ascendancyName then
      local c1, c2 = setCost[1][node] or 0, setCost[2][node] or 0
      if c1 ~= cost or c2 ~= cost then wc = { c1, c2 } end
    end
    -- a taken socket's jewel: its picture from the tree textures (a unique's own, else its base's)
    local jewel = false
    if node.type == "Socket" or node.containJewelSocket then
      local slot = build.itemsTab.sockets[id]
      local item = slot and node.alloc and build.itemsTab.items[slot.selItemId]
      if item then
        jewel = { name = item.name or "", base = item.baseName or "", rarity = item.rarity or "",
                  art = (item.rarity == "UNIQUE" and atlas(item.title)) or atlas(item.baseName) or false }
      end
    end
    local ts = node.targetSize or {}
    nodes[#nodes + 1] = { id = id, x = node.x, y = node.y, type = node.type, name = node.dn or "", icon = node.icon or "",
      sz = ts.width or 0, fs = ts.overlay and ts.overlay.width or 0, fr = frameOf(node.overlay), jewel = jewel,
      stats = _poe2lab_array(node.sd or {}), asc = node.ascendancyName or "", alloc = node.alloc and true or false,
      cost = cost, drop = drop, mode = node.allocMode or 0, wc = wc, glob = global(node) and true or false,
      wnear = (global(node) and not node.alloc and nearSet(node)) and true or false,
      links = links, arcs = arcs, group = node.g or 0, o = node.o or 0,
      gx = g and g.x * tree.scaleImage or 0, gy = g and g.y * tree.scaleImage or 0,
      r = node.o and tree.orbitRadii[node.o + 1] and tree.orbitRadii[node.o + 1] * tree.scaleImage or 0 }
  end
end
local used, ascUsed = spec:CountAllocNodes()
-- the game's own background art as PoB draws it: where each picture sits in PoB's texture files (file, layer)
local function where(name)
  for file, names in pairs(tree.ddsCoords or {}) do
    if names[name] then return { file = file, layer = names[name] } end
  end
end
local art = { version = tree.treeVersion, tile = where("Background2"), asc = _poe2lab_array({}) }
local cls = tree.classes[spec.curClassId]
if cls and cls.background and cls.background.image then
  local b, start = cls.background, spec.nodes[cls.startNodeId]
  local x, y = b.x * tree.scaleImage, b.y * tree.scaleImage
  art.center = { x = x, y = y, w = b.width, image = where(b.image), ring = where("BGTree"),
    ringW = b.bg and b.bg.width or 0, active = where("BGTreeActive"), activeW = b.active and b.active.width or 0,
    angle = start and (math.pi / 2 + math.atan2(start.y - y, start.x - x)) or 0 }
end
for i, a in pairs(spec.curClass.classes or {}) do
  if i > 0 and a.name and shown[a.name] and a.background and a.background.image then
    art.asc[#art.asc + 1] = { name = a.name, x = a.background.x * tree.scaleImage, y = a.background.y * tree.scaleImage,
      w = a.background.width, image = where(a.background.image) }
  end
end
local radii = _poe2lab_array({})
for i, r in ipairs(tree.orbitRadii or {}) do radii[i] = r * tree.scaleImage end
return _poe2lab_json({ nodes = nodes, class = spec.curClassName, ascendancy = asc or "", points = used,
  ascendancyPoints = ascUsed, art = art, orbitRadii = radii, frames = frames })""") | {"budget": self.points_budget()}

    def points_budget(self) -> dict:
        """Passive points: used on the main tree (a node taken in both weapon sets counts once) and how many the
        character's level gives (level - 1, the quest points of the acts done by that level, extra points from the
        build - PoB's own count, EstimatePlayerProgress); ascendancy points used of 8; the weapon sets' nodes
        (ws1, ws2) of how many each set can have (wsTotal: the quest points, plus what the build's items add)."""
        return self._json("""
local used, asc, _, _, ws1, ws2 = build.spec:CountAllocNodes()
local extra = build.calcsTab.mainOutput and build.calcsTab.mainOutput.ExtraPoints or 0
local level = build.characterLevel or 1
local quest = 0
for _, a in ipairs(build.acts or {}) do if (a.level or 0) <= level then quest = a.questPoints or quest end end
local total = math.min(level - 1 + quest + extra, 99 + (build.maxWeaponSets or 0) + extra)
local wsExtra = build.calcsTab.mainOutput and build.calcsTab.mainOutput.PassivePointsToWeaponSetPoints or 0
return _poe2lab_json({ used = used - math.min(ws1 or 0, ws2 or 0), total = total, asc = asc or 0, ascTotal = 8,
  ws1 = ws1 or 0, ws2 = ws2 or 0, wsTotal = (build.maxWeaponSets or 0) + wsExtra })""")

    def class_ascendancies(self) -> list[dict]:
        """The ascendancies of the build's class with their notables - to choose from while none is taken."""
        return self._json("""
local spec, out = build.spec, _poe2lab_array({})
for i, a in pairs(spec.curClass.classes or {}) do
  if i > 0 and a.name then
    local notables = _poe2lab_array({})
    for id, node in pairs(spec.nodes) do
      if node.ascendancyName == a.name and node.type == "Notable" then
        notables[#notables + 1] = { id = id, name = node.dn or "", stats = _poe2lab_array(node.sd or {}) }
      end
    end
    out[#out + 1] = { name = a.name, notables = notables }
  end
end
return _poe2lab_json(out)""")

    def ascendancy_reach(self) -> list[dict]:
        """Unallocated notables of the build's own ascendancy with the path PoB would allocate to them."""
        return self._json("""
local out, asc = _poe2lab_array({}), build.spec.curAscendClassName
for id, node in pairs(build.spec.nodes) do
  if not node.alloc and node.type == "Notable" and asc and node.ascendancyName == asc and node.path and #node.path > 0 then
    local path, names = _poe2lab_array({}), _poe2lab_array({})
    for i, n in ipairs(node.path) do path[i] = n.id; names[i] = n.dn or "" end
    out[#out + 1] = { id = id, name = node.dn or "", type = node.type, path = path, pathNames = names,
                      stats = _poe2lab_array(node.sd or {}) }
  end
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

    def tree_add(self, node_id: int, weapon_set: int = 0) -> list[str]:
        """Allocate a node along PoB's shortest path from the tree - on the main tree (weapon_set 0) or for weapon
        set 1 or 2, as PoB does in that mode (keystones, jewel sockets and the ascendancy stay on the main tree);
        returns the names of the nodes allocated."""
        if weapon_set not in (0, 1, 2):
            raise PobError(f"no weapon set {weapon_set}")
        return self._json(f"""
local spec = build.spec
local node = spec.nodes[{int(node_id)}]
if not node then error("no passive node {int(node_id)}", 0) end
if node.alloc then return _poe2lab_json(_poe2lab_array({{}})) end
if not node.path or #node.path == 0 then error("node cannot be reached from the tree", 0) end
local global = node.type == "Keystone" or node.type == "Socket" or node.containJewelSocket
if global and {weapon_set} > 0 then error("keystones and jewel sockets are taken on the main tree only", 0) end
if global then
  local near = false
  for i = 2, #node.path do if node.path[i].alloc and (node.path[i].allocMode or 0) > 0 then near = true end end
  for _, other in ipairs(node.linked or {{}}) do if other.alloc and (other.allocMode or 0) > 0 then near = true end end
  if near then error("a keystone or a jewel socket next to a weapon set's branch cannot be taken", 0) end
end
local before = {{}}
for id in pairs(spec.allocNodes) do before[id] = true end
spec.allocMode = {weapon_set}
local ok, err = pcall(spec.AllocNode, spec, node)
spec.allocMode = 0
if not ok then error(err, 0) end
if not node.alloc then error("node cannot be reached in this weapon set", 0) end
spec:BuildAllDependsAndPaths()
build.buildFlag = true
build.calcsTab:BuildOutput()
local added = _poe2lab_array({{}})
for id, n in pairs(spec.allocNodes) do if not before[id] then added[#added + 1] = n.dn or "" end end
return _poe2lab_json(added)""")

    def tree_remove(self, node_id: int, weapon_set: int = 0) -> list[str]:
        """Deallocate a node and everything only reachable through it; returns the names removed. Viewed from a
        weapon set (1, 2), a keystone or jewel socket of the main tree is not taken off - PoB's rule."""
        return self._json(f"""
local spec = build.spec
local node = spec.nodes[{int(node_id)}]
if not node or not node.alloc then return _poe2lab_json(_poe2lab_array({{}})) end
if node.type == "ClassStart" or node.type == "AscendClassStart" then error("the class start cannot be removed", 0) end
if {int(weapon_set)} > 0 and (node.allocMode or 0) == 0 and (node.type == "Keystone" or node.type == "Socket" or node.containJewelSocket) then
  error("a keystone or a jewel socket of the main tree is taken off on the main tree only", 0)
end
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
                replace_runes: tuple[str, list[str]] | None = None, keep_quality: bool = False) -> dict[str, float]:
        """Recalculate without changing the build, as if:
        - passive nodes were added/removed,
        - extra player mod lines were present (e.g. "10% increased Attack Speed"),
        - extra enemy mod lines were present (e.g. "50% increased Damage"),
        - Configuration tab values were set (e.g. {"enemyLevel": 79, "enemyCritChance": 100}),
        - the item in remove_slot (e.g. "Ring 1") was taken off,
        - gems given as (socket group, gem index) pairs were disabled,
        - offence was reported for main_socket_group instead of the build's main skill,
        - replace_item = (slot, item text) was equipped instead (PoB format or text copied from the game; its
          quality below 20% counts as 20%, as PoB takes a pasted item, unless keep_quality),
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
            extra += (f", repSlotName = {lua_string(slot_name)}, "
                      f"repItem = _poe2lab_item({lua_string(text)}, {'true' if keep_quality else 'false'})")
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

    def at_level(self, level: int, disable_gems=(), remove_nodes=(), items: dict | None = None,
                 config: dict | None = None) -> dict[str, float]:
        """The build as a character of `level` would have it, calculated without changing the build: that character
        level; each active gem at the highest level its requirement allows (not above the build's own); the gems
        given as (group, index) left out (not dropped yet); passive nodes removed; items by slot replaced by an item
        text or taken off (None); Configuration values set (the quests not done yet). PoB's output for the main
        skill, with the attributes the gems and items require (ReqStr...)."""
        remove = ", ".join(str(int(n)) for n in remove_nodes)
        gems = ", ".join(f"{{ {int(g)}, {int(i)} }}" for g, i in disable_gems)
        slots = ", ".join(f"[ {lua_string(k)} ] = {lua_string(v) if v else 'false'}" for k, v in (items or {}).items())
        cfg = ", ".join(f"[ {lua_string(k)} ] = {_lua_value(v)}" for k, v in (config or {}).items())
        return self._json(f"""
local level = {int(level)}
local saved = {{ level = build.characterLevel, gems = {{}}, slots = {{}}, added = {{}} }}
local groups = build.skillsTab.socketGroupList
local ok, res = pcall(function()
  build.characterLevel = level
  for _, g in ipairs(groups) do
    for _, gem in ipairs(g.gemList) do
      local ge = gem.gemData and gem.gemData.grantedEffect
      saved.gems[#saved.gems + 1] = {{ gem = gem, level = gem.level, enabled = gem.enabled }}
      if ge and not ge.support and gem.level then
        local top = 1
        for l = 1, gem.level do
          local lv = ge.levels[l]
          if lv and (lv.levelRequirement or 0) <= level then top = l end
        end
        gem.level = top
      end
    end
  end
  for _, p in ipairs({{ {gems} }}) do
    local gem = groups[p[1]] and groups[p[1]].gemList[p[2]]
    if gem then gem.enabled = false end
  end
  for _, g in ipairs(groups) do build.skillsTab:ProcessSocketGroup(g) end
  for slotName, text in pairs({{ {slots} }}) do
    local slot = build.itemsTab.slots[slotName]
    if slot then
      saved.slots[slotName] = slot.selItemId
      if text then
        local item = _poe2lab_item(text, true)
        build.itemsTab:AddItem(item, true)
        saved.added[#saved.added + 1] = item
        slot:SetSelItemId(item.id)
      else
        slot:SetSelItemId(0)
      end
    end
  end
  return _poe2lab_with_setup({{ {cfg} }}, {{}}, {{}}, function()
    local calcFunc = build.calcsTab:GetMiscCalculator()
    return calcFunc({{ removeNodes = _poe2lab_nodeset({{ {remove} }}) }}, false)
  end)
end)
build.characterLevel = saved.level
for _, s in ipairs(saved.gems) do s.gem.level, s.gem.enabled = s.level, s.enabled end
for slotName, id in pairs(saved.slots) do build.itemsTab.slots[slotName]:SetSelItemId(id) end
for _, item in ipairs(saved.added) do build.itemsTab:DeleteItem(item, true) end
for _, g in ipairs(groups) do build.skillsTab:ProcessSocketGroup(g) end
build.buildFlag = true
build.calcsTab:BuildOutput()
if not ok then error(res, 0) end
return _poe2lab_numbers(res)""")

    def item_bases(self) -> list[dict]:
        """Every item base PoB knows: name, type, subtype, level requirement."""
        return self._json("""
local out = _poe2lab_array({})
for name, b in pairs(data.itemBases) do
  out[#out + 1] = { name = name, type = b.type or "", subType = b.subType or "", level = (b.req and b.req.level) or 0,
                    hidden = b.hidden and true or false }
end
return _poe2lab_json(out)""")

    def equipped_bases(self) -> dict[str, dict]:
        """Each gear slot's item base: {slot: {base, type, subType}}."""
        return self._json("""
local out = {}
for _, slot in ipairs(build.itemsTab.orderedSlots) do
  local item = not slot.nodeId and build.itemsTab.items[slot.selItemId]
  if item and item.base then
    out[slot.slotName] = { base = item.baseName or "", type = item.base.type or "", subType = item.base.subType or "",
                           rarity = item.rarity or "" }
  end
end
return _poe2lab_json(out)""")

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
    implicit = b.implicit or "", level = (b.req and b.req.level) or 0, quality = b.quality or 0,
    socketLimit = b.socketLimit or 0 }}
end
return _poe2lab_json({{ mods = mods, bases = bases }})""")

    def equipped_item_details(self) -> list[dict]:
        """Equipped gear with base tags, item level, corruption and its lines - implicit, explicit (for affix
        analysis), runes, enchantments - as the page shows it."""
        return self._json("""
local out = _poe2lab_array({})
for _, slot in ipairs(build.itemsTab.orderedSlots) do
  local item = not slot.nodeId and build.itemsTab.items[slot.selItemId]
  if item and item.base then out[#out + 1] = _poe2lab_item_view(item, slot.slotName) end
end
return _poe2lab_json(out)""")

    def jewel_sockets(self) -> list[dict]:
        """The jewel sockets allocated in the tree: each with its slot ("Jewel <node id>"), the nearest allocated
        notable (where it is, in words) and the jewel in it as the page shows items (none when empty)."""
        return self._json("""
local out = _poe2lab_array({})
for nodeId, slot in pairs(build.itemsTab.sockets) do
  local node = build.spec.nodes[nodeId]
  if node and build.spec.allocNodes[nodeId] then
    local near, best = "", math.huge
    for _, n in pairs(build.spec.allocNodes) do
      if n.type == "Notable" and not n.ascendancyName and n.x and node.x then
        local d = (n.x - node.x) ^ 2 + (n.y - node.y) ^ 2
        if d < best then best, near = d, n.dn or "" end
      end
    end
    local item = build.itemsTab.items[slot.selItemId]
    out[#out + 1] = { node = nodeId, slot = slot.slotName, near = near,
                      item = item and _poe2lab_item_view(item, slot.slotName) or false }
  end
end
return _poe2lab_json(out)""")

    def resolve_ranges(self, pairs: list[tuple[str, float]]) -> list[str]:
        """Item lines with each range - "(4-8)%" - resolved where its roll puts it (0: the low end, 1: the high
        end), by PoB's own itemLib.applyRange as it reads an affix's roll; leading {tags} and lines with no range
        stay as they are."""
        rows = ", ".join(f"{{ {lua_string(line)}, {float(r)} }}" for line, r in pairs)
        return self._json(f"""
local out = _poe2lab_array({{}})
for i, p in ipairs({{ {rows} }}) do
  local line, prefix = p[1], ""
  while true do
    local tok, rest = line:match("^({{[^}}]*}})(.*)$")
    if not tok then break end
    prefix, line = prefix .. tok, rest
  end
  if line:match("%(%-?[%d%.]+%-%-?[%d%.]+%)") then line = itemLib.applyRange(line, p[2]) end
  out[i] = prefix .. line
end
return _poe2lab_json(out)""")

    def edit_item(self, slot: str, quality: int | None = None, sockets: int | None = None,
                  runes: list[str] | None = None, catalyst: int | None = None,
                  catalyst_quality: int | None = None) -> str:
        """The equipped item's text with its quality, rune sockets and runes (a name or "None" per socket), its
        catalyst (PoB's number, 0: none) and the catalyst's quality set - None: as it is. PoB scales by a catalyst
        only the lines with mod tags (poe2lab.quality.recatalyse does the rest). Nothing is equipped:
        equip_item(slot, text, exact=True) or what_if(replace_item=(slot, text), keep_quality=True)."""
        num = lambda v: "nil" if v is None else str(int(v))  # noqa: E731
        q, n, c, cq = num(quality), num(sockets), num(catalyst), num(catalyst_quality)
        r = "nil" if runes is None else "{ " + ", ".join(lua_string(x) for x in runes) + " }"
        return self._lua(f"""
local slot = build.itemsTab.slots[ {lua_string(slot)} ]
local item = slot and build.itemsTab.items[slot.selItemId]
if not item then error("no item in slot " .. {lua_string(slot)}, 0) end
return _poe2lab_item_edit(item.raw, {q}, {n}, {r}, {c}, {cq}):BuildRaw()""")

    def item_fits(self, slot: str, text: str) -> bool:
        """Whether PoB lets the item into the slot: the slot's item type, one hand or two beside the other weapon,
        a jewel socket's kind (a Lich's takes plain jewels only, a sinister one no uniques, a charm socket charms)."""
        return self._json(f"""
local item = _poe2lab_item({lua_string(text)}, true)
return _poe2lab_json(build.itemsTab:IsItemValidForSlot(item, {lua_string(slot)}) and true or false)""")

    def slot_bases(self, slot: str) -> list[str]:
        """The item bases PoB lets into the slot."""
        return self._json(f"""
local out = _poe2lab_array({{}})
for name in pairs(data.itemBases) do
  local ok, item = pcall(function() return new("Item"):Item("Rarity: NORMAL\\n" .. name) end)
  if ok and item and item.base and build.itemsTab:IsItemValidForSlot(item, {lua_string(slot)}) then out[#out + 1] = name end
end
return _poe2lab_json(out)""")

    def clear_slot(self, slot: str):
        """Take off whatever is in a slot (gear or a jewel socket), recalculated."""
        self._lua(f"""
local slot = build.itemsTab.slots[ {lua_string(slot)} ]
if not slot then error("no slot " .. {lua_string(slot)}, 0) end
slot:SetSelItemId(0)
build.itemsTab:PopulateSlots()
build.buildFlag = true
build.calcsTab:BuildOutput()""")

    def parse_item(self, text: str) -> dict:
        """An item's text (PoB's or the game's, in English) read the way equipped_item_details shows gear."""
        return self._json(f"return _poe2lab_json(_poe2lab_item_view(_poe2lab_item({lua_string(text)}), ''))")

    def find_mod_text(self, query: str) -> dict:
        """Everything in PoB's game data whose text contains `query` (any case): item affixes, runes and soul
        cores, uniques (their raw text, variants included), passive tree nodes of this build's tree, base
        implicits. For "does this mod exist, and where from"."""
        return self._json(f"""
local q = {lua_string(query.lower())}
local function hit(s) return type(s) == "string" and s:lower():find(q, 1, true) ~= nil end
local function arr(t) local o = _poe2lab_array({{}}) for i, v in ipairs(t or {{}}) do o[i] = v end return o end
local out = {{ affixes = _poe2lab_array({{}}), runes = _poe2lab_array({{}}), uniques = _poe2lab_array({{}}),
  nodes = _poe2lab_array({{}}), bases = _poe2lab_array({{}}) }}
for _, setName in ipairs({{ "Item", "Desecrated", "Corruption", "Jewel", "Charm", "Flask" }}) do
  for id, m in pairs(data.itemMods[setName] or {{}}) do
    for _, line in ipairs(m) do
      if hit(line) then
        local kinds = _poe2lab_array({{}})
        for i, key in ipairs(m.weightKey or {{}}) do
          if (m.weightVal or {{}})[i] and m.weightVal[i] > 0 then kinds[#kinds + 1] = key end
        end
        out.affixes[#out.affixes + 1] = {{ set = setName, id = id, type = m.type or "", affix = m.affix or "",
          lines = arr(m), level = m.level or 0, group = m.group or id, kinds = kinds }}
        break
      end
    end
  end
end
for name, rune in pairs(data.itemMods.Runes or {{}}) do
  for slotType, m in pairs(rune) do
    if type(m) == "table" then
      for _, line in ipairs(m) do
        if hit(line) then out.runes[#out.runes + 1] = {{ name = name, slot = slotType, lines = arr(m) }} break end
      end
    end
  end
end
for kind, list in pairs(data.uniques or {{}}) do
  for _, raw in ipairs(list) do
    if hit(raw) then out.uniques[#out.uniques + 1] = {{ kind = kind, raw = raw }} end
  end
end
-- the build's own tree, and the game's current one when the build was made on an older tree
local trees = {{ {{ build.spec.treeVersion, build.spec.tree }} }}
if latestTreeVersion ~= build.spec.treeVersion then
  trees[2] = {{ latestTreeVersion, main:LoadTree(latestTreeVersion) }}
  data.setJewelRadiiGlobally(build.spec.treeVersion)  -- LoadTree switched them to the other version
end
for _, pair in ipairs(trees) do
  for id, node in pairs(pair[2].nodes) do
    for _, line in ipairs(node.sd or {{}}) do
      if hit(line) then
        out.nodes[#out.nodes + 1] = {{ name = node.dn or node.name or "", lines = arr(node.sd), tree = pair[1],
          type = node.type or "", ascendancy = node.ascendancyName or "",
          allocated = pair[1] == build.spec.treeVersion and build.spec.allocNodes[id] ~= nil }}
        break
      end
    end
  end
end
out.buildTree = build.spec.treeVersion
out.gameTree = latestTreeVersion
for name, b in pairs(data.itemBases) do
  if hit(b.implicit) then out.bases[#out.bases + 1] = {{ name = name, type = b.type or "", implicit = b.implicit }} end
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
        """Sockets of the equipped item, the runes / soul cores in them and which augments fit it; its quality,
        whether its base takes quality, how many rune sockets the base can have; its type and catalyst."""
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
  rarity = item.rarity or "", baseType = baseType or "", specificType = specificType or "", options = options,
  quality = item.quality or 0, hasQuality = item.base.quality and true or false,
  socketLimit = item.base.socketLimit or 0, itemType = item.base.type or "", catalyst = item.catalyst or 0,
  catalystQuality = item.catalystQuality or 0 }})""")

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

    def equip_item(self, slot: str, item_text: str, exact: bool = False):
        """Really equip an item (in memory) and recalculate. Unlike what_if(replace_item=...) this persists,
        so several slots can be changed together; equip the old text again (exact: its quality as written) to
        undo."""
        self._lua(f"""
local itemsTab = build.itemsTab
local item = _poe2lab_item({lua_string(item_text)}, {'true' if exact else 'false'})
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

    _GEM_HELPERS = """
local typeName = {}
for k, v in pairs(SkillType) do typeName[v] = k end
local function arr(t) return _poe2lab_array(t or {}) end
local function tags(d) local o = arr({}) for t, on in pairs(d.tags or {}) do if on then o[#o + 1] = t end end return o end
local function types(set) local o = arr({}) for id, on in pairs(set or {}) do if on and typeName[id] then o[#o + 1] = typeName[id] end end return o end
-- the required skill types of a support that this active skill has: why the support applies to it
local function statIds(ge)
  local o, seen = arr({}), {}
  for _, set in ipairs(ge.statSets or {}) do
    for _, st in ipairs(set.stats or {}) do if not seen[st] then seen[st] = true o[#o + 1] = st end end
    for _, c in ipairs(set.constantStats or {}) do if not seen[c[1]] then seen[c[1]] = true o[#o + 1] = c[1] end end
  end
  return o
end
local function because(ge, active)
  local o = arr({})
  for _, id in ipairs(ge.requireSkillTypes or {}) do
    local n = typeName[id]
    if n and n ~= "AND" and n ~= "OR" and n ~= "NOT" and active.skillTypes[id] then o[#o + 1] = n end
  end
  return o
end
"""

    def skill_groups(self) -> list[dict]:
        """Socket groups with their gems as the player sees them: active skills with their skill types, support gems
        with the active skills they apply to and the required skill types that make them apply; gem tiers."""
        return self._json(self._GEM_HELPERS + """
local out = arr({})
for gi, g in ipairs(build.skillsTab.socketGroupList) do
  local actives = arr({})
  for _, a in ipairs(g.displaySkillList or {}) do
    actives[#actives + 1] = { name = a.activeEffect.grantedEffect.name, types = types(a.skillTypes) }
  end
  local gems = arr({})
  for i, gem in ipairs(g.gemList) do
    local d = gem.gemData
    if d then
      local ge = d.grantedEffect
      local fits = arr({})
      if ge.support then
        for _, a in ipairs(g.displaySkillList or {}) do
          if calcLib.canGrantedEffectSupportActiveSkill(ge, a) then
            fits[#fits + 1] = { skill = a.activeEffect.grantedEffect.name, because = because(ge, a) }
          end
        end
      end
      gems[#gems + 1] = { index = i, id = gem.gemId or "", name = ge.name, support = ge.support and true or false,
        enabled = gem.enabled ~= false, level = gem.level or 1, quality = gem.quality or 0, tier = d.Tier or 0,
        maxLevel = d.naturalMaxLevel or 1, tags = tags(d), lineage = ge.isLineage and true or false,
        family = d.gemFamily or "", reqLevel = (ge.levels[d.Tier or 1] or ge.levels[1] or {}).levelRequirement or 0,
        description = ge.description or "", fits = fits, stats = statIds(ge),
        types = ge.support and arr({}) or types(ge.skillTypes) }
    end
  end
  out[#out + 1] = { index = gi, label = g.label or "", slot = g.slot or "", enabled = g.enabled and true or false,
    main = gi == build.mainSocketGroup, mainActive = g.mainActiveSkill or 1, actives = actives, gems = gems }
end
return _poe2lab_json(out)""")

    def unique_catalog(self) -> list[dict]:
        """Every unique item of PoB's data as PoB reads it (the current variant): name, base, type, level
        requirement, lines (with the ones PoB cannot parse marked), and its raw text to equip it in a what-if."""
        return self._json("""
local out = _poe2lab_array({})
for kind, list in pairs(data.uniques or {}) do
  for _, raw in pairs(list) do
    local ok, item = pcall(function() return new("Item"):Item(raw, "UNIQUE", true) end)
    if ok and item and item.base and item.rarity == "UNIQUE" then
      local lines, unread = _poe2lab_array({}), _poe2lab_array({})
      for _, list in ipairs({ item.implicitModLines or {}, item.explicitModLines or {} }) do
        for _, ml in ipairs(list) do
          if item:CheckModLineVariant(ml) then
            lines[#lines + 1] = ml.line
            if ml.extra then unread[#unread + 1] = ml.line end
          end
        end
      end
      local source = raw:match("\\nSource: ([^\\n]+)") or ""
      out[#out + 1] = { name = item.title or item.name, base = item.baseName or "", type = item.type or "",
        kind = kind, level = (item.requirements and item.requirements.level) or 0, lines = lines, unread = unread,
        source = source, raw = raw }
    end
  end
end
return _poe2lab_json(out)""")

    def support_candidates(self, group: int) -> list[dict]:
        """Support gems (cuttable from uncut gems: tier > 0) that can support the group's first active skill and whose
        family is not in the group yet."""
        return self._json(self._GEM_HELPERS + f"""
local g = build.skillsTab.socketGroupList[{int(group)}]
local active = g and g.displaySkillList and g.displaySkillList[1]
local out = arr({{}})
if not active then return _poe2lab_json(out) end
local have = {{}}
for _, gem in ipairs(g.gemList) do
  if gem.gemData then have[gem.gemData.gemFamily or gem.gemData.name] = true end
end
for id, d in pairs(data.gems) do
  local ge = d.grantedEffect
  if ge and ge.support and (d.Tier or 0) > 0 and not ge.hidden and not have[d.gemFamily or d.name]
     and calcLib.canGrantedEffectSupportActiveSkill(ge, active) then
    out[#out + 1] = {{ id = id, name = ge.name, tier = d.Tier, family = d.gemFamily or "",
      color = tostring(d.color or ""), description = ge.description or "", because = because(ge, active) }}
  end
end
return _poe2lab_json(out)""")

    def support_gains(self, group: int, gem_ids: list[str], config=None, measure_group: int | None = None) -> dict:
        """DPS, one hit, EHP and the mana balance (regenerated and leeched less spent per second) with each support gem
        added to the group on its own, in one pass: {"base": {...},
        id: {...}}. Offence is read for `measure_group` (default: the build's main skill)."""
        ids = ", ".join(lua_string(i) for i in gem_ids)
        cfg = ", ".join(f"[ {lua_string(k)} ] = {_lua_value(v)}" for k, v in (config or {}).items())
        override = f"mainSocketGroup = {int(measure_group)}" if measure_group else ""
        return self._json(f"""
local g = build.skillsTab.socketGroupList[{int(group)}]
local res = {{}}
_poe2lab_with_setup({{ {cfg} }}, {{}}, {{}}, function()
  local function measure()
    wipeGlobalCache()
    local out = build.calcsTab:GetMiscCalculator()({{ {override} }}, false)
    return {{ dps = out.CombinedDPS or 0, ehp = out.TotalEHP or 0, hit = out.AverageHit or 0,
             mana = (out.ManaRegenRecovery or 0) + (out.ManaLeechRate or 0) - (out.ManaPerSecondCost or 0) }}
  end
  res.base = measure()
  for _, id in ipairs({{ {ids} }}) do
    local d = data.gems[id]
    if d then
      local inst = {{ nameSpec = d.name, gemId = id, level = build.skillsTab:ProcessGemLevel(d), quality = 0,
        enabled = true, enableGlobal1 = true, enableGlobal2 = true, count = 1, corruptLevel = 0, corrupted = false }}
      table.insert(g.gemList, inst)
      build.skillsTab:ProcessSocketGroup(g)
      local ok, m = pcall(measure)
      table.remove(g.gemList)
      if ok then res[id] = m end
    end
  end
  build.skillsTab:ProcessSocketGroup(g)
end)
wipeGlobalCache()
build.calcsTab:BuildOutput()
return _poe2lab_json(res)""")

    @contextmanager
    def added_gem(self, group: int, gem_id: str):
        """Temporarily socket one more gem (a data.gems id) into a socket group, recalculated; removed on exit."""
        self._lua(f"""
local g = build.skillsTab.socketGroupList[{int(group)}]
local d = data.gems[ {lua_string(gem_id)} ]
if not g or not d then error("no such group or gem", 0) end
local inst = {{ nameSpec = d.name, gemId = {lua_string(gem_id)}, level = build.skillsTab:ProcessGemLevel(d), quality = 0,
  enabled = true, enableGlobal1 = true, enableGlobal2 = true, count = 1, corruptLevel = 0, corrupted = false }}
table.insert(g.gemList, inst)
_poe2lab_added = {{ group = g, inst = inst }}
build.skillsTab:ProcessSocketGroup(g)
wipeGlobalCache()
build.calcsTab:BuildOutput()""")
        try:
            yield self
        finally:
            self._lua("""
local a = _poe2lab_added
for i, inst in ipairs(a.group.gemList) do
  if inst == a.inst then table.remove(a.group.gemList, i) break end
end
build.skillsTab:ProcessSocketGroup(a.group)
_poe2lab_added = nil
wipeGlobalCache()
build.calcsTab:BuildOutput()""")

    def skills_snapshot(self, name: str):
        """Remember every socket group (gems, levels, qualities, what is switched on, the main skill) under `name`:
        PoB's own undo state of the skills tab."""
        self._lua(f"""
_poe2lab_skill_snaps = _poe2lab_skill_snaps or {{}}
_poe2lab_skill_snaps[ {lua_string(name)} ] = build.skillsTab:CreateUndoState()""")

    def skills_restore(self, name: str):
        """Put back the socket groups remembered by skills_snapshot, recalculated. The snapshot is used up: PoB
        restores its very tables."""
        self._lua(f"""
local snap = _poe2lab_skill_snaps and _poe2lab_skill_snaps[ {lua_string(name)} ]
if not snap then error("no skills snapshot {name}", 0) end
_poe2lab_skill_snaps[ {lua_string(name)} ] = nil
build.skillsTab:RestoreUndoState(snap)
for _, g in ipairs(build.skillsTab.socketGroupList) do build.skillsTab:ProcessSocketGroup(g) end
build.buildFlag = true
wipeGlobalCache()
build.calcsTab:BuildOutput()""")

    def set_gem(self, group: int, index: int | None, gem_id: str, level: int | None = None, quality: int = 0) -> int:
        """Socket a gem (a data.gems id) into socket group `group`: in place of the gem at `index`, or after the
        group's gems when index is None. Group 0 is a new socket group - a new skill. Level None: the highest the
        character's level allows. Recalculated; returns the group's number."""
        lvl = "build.skillsTab:ProcessGemLevel(d)" if level is None else str(int(level))
        return self._json(f"""
local d = data.gems[ {lua_string(gem_id)} ]
if not d then error("no gem " .. {lua_string(gem_id)}, 0) end
local list = build.skillsTab.socketGroupList
local g = list[{int(group)}]
if {int(group)} == 0 then
  g = {{ label = "", enabled = true, gemList = {{}} }}
  table.insert(list, g)
elseif not g then
  error("no socket group {int(group)}", 0)
end
local inst = {{ nameSpec = d.name, gemId = {lua_string(gem_id)}, level = {lvl}, quality = {int(quality)}, enabled = true,
  enableGlobal1 = true, enableGlobal2 = true, count = 1, corruptLevel = 0, corrupted = false }}
local at = {int(index or 0)}
if at > 0 and g.gemList[at] then g.gemList[at] = inst else table.insert(g.gemList, inst) end
build.skillsTab:ProcessSocketGroup(g)
build.buildFlag = true
wipeGlobalCache()
build.calcsTab:BuildOutput()
for i, x in ipairs(list) do if x == g then return _poe2lab_json(i) end end""")

    def remove_gem(self, group: int, index: int):
        """Take the gem at `index` out of socket group `group`; a group left empty goes (the skill is gone), the
        main skill's number following. Recalculated."""
        self._lua(f"""
local list = build.skillsTab.socketGroupList
local gi = {int(group)}
local g = list[gi]
if not g or not g.gemList[{int(index)}] then error("no gem {int(index)} in socket group {int(group)}", 0) end
table.remove(g.gemList, {int(index)})
if #g.gemList == 0 then
  table.remove(list, gi)
  if build.mainSocketGroup > gi then build.mainSocketGroup = build.mainSocketGroup - 1
  elseif build.mainSocketGroup == gi then build.mainSocketGroup = 1 end
else
  build.skillsTab:ProcessSocketGroup(g)
end
build.buildFlag = true
wipeGlobalCache()
build.calcsTab:BuildOutput()""")

    def gem_catalog(self) -> list[dict]:
        """The gems the game gives: skill and support gems cut from uncut gems (a tier above 0) and lineage supports.
        Each with its colour code, family, level cap, the character level each gem level needs and the weapon types
        a skill needs (none for spells and minions)."""
        return self._json(self._GEM_HELPERS + """
local colours = { colorCodes.STRENGTH, colorCodes.DEXTERITY, colorCodes.INTELLIGENCE }
local out = arr({})
for id, d in pairs(data.gems) do
  local ge = d.grantedEffect
  if ge and not ge.hidden and ((d.Tier or 0) > 0 or ge.isLineage) then
    local reqs, max = arr({}), d.naturalMaxLevel or 1
    for i = 1, max do reqs[i] = (ge.levels[i] or {}).levelRequirement or 0 end
    out[#out + 1] = { id = id, name = ge.name, support = ge.support and true or false, tier = d.Tier or 0,
      lineage = ge.isLineage and true or false, family = type(d.gemFamily) == "string" and d.gemFamily or ge.name,
      color = tostring(colours[ge.color] or colorCodes.NORMAL), tags = tags(d), maxLevel = max, reqs = reqs,
      description = ge.description or "", types = ge.support and arr({}) or types(ge.skillTypes),
      weapons = arr((function() local w = {} for k in pairs(ge.weaponTypes or {}) do w[#w + 1] = k end table.sort(w) return w end)()) }
  end
end
return _poe2lab_json(out)""")

    def gem_texts(self) -> list[dict]:
        """Every gem the game gives (as gem_catalog) with what it says: its description, its stat lines in English
        at level 10 (or its highest below that) and its stat ids - what the game data tells about its mechanics."""
        return self._json(self._GEM_HELPERS + """
local out = arr({})
for id, d in pairs(data.gems) do
  local ge = d.grantedEffect
  if ge and not ge.hidden and ((d.Tier or 0) > 0 or ge.isLineage) then
    local gem = { level = math.min(d.naturalMaxLevel or 1, 10), quality = 0, gemData = d, grantedEffect = ge,
                  enabled = true }
    local lines, seen = arr({}), {}
    for _, set in ipairs(ge.statSets or {}) do
      local ok, stats = pcall(calcLib.buildSkillInstanceStats, gem, ge, set, false)
      if ok and stats then
        local ok2, ls = pcall(data.describeStats, stats, set.statDescriptionScope)
        for _, l in ipairs(ok2 and ls or {}) do
          l = StripEscapes(l)
          if not seen[l] then seen[l] = true lines[#lines + 1] = l end
        end
      end
    end
    out[#out + 1] = { id = id, name = ge.name, support = ge.support and true or false, tier = d.Tier or 0,
      description = ge.description or "", lines = lines, stats = statIds(ge), tags = tags(d),
      types = ge.support and arr({}) or types(ge.skillTypes) }
  end
end
return _poe2lab_json(out)""")

    def unmapped_stats(self) -> list[dict]:
        """Every stat of every gem the game gives that PoB has no calculation for (what "PoB does not count" lists
        for a build's skills), once each: its id and the game's text for it."""
        return self._json(self._GEM_HELPERS + """
local out, seen, ids = arr({}), {}, {}
for id in pairs(data.gems) do ids[#ids + 1] = id end
table.sort(ids)  -- a stat of several gems is described by the same one every time
for _, id in ipairs(ids) do
  local d = data.gems[id]
  local ge = d.grantedEffect
  if ge and not ge.hidden and ((d.Tier or 0) > 0 or ge.isLineage) then
    local gem = { level = math.min(d.naturalMaxLevel or 1, 10), quality = 0, gemData = d, grantedEffect = ge,
                  enabled = true }
    for _, set in ipairs(ge.statSets or {}) do
      local ok, stats = pcall(calcLib.buildSkillInstanceStats, gem, ge, set, false)
      local names = {}
      for stat in pairs(ok and stats or {}) do names[#names + 1] = stat end
      table.sort(names)
      for _, stat in ipairs(names) do
        local value = stats[stat]
        if not set.statMap[stat] and not seen[stat] then
          seen[stat] = true
          local ok2, ls = pcall(data.describeStats, { [stat] = value }, set.statDescriptionScope)
          local text = {}
          for _, l in ipairs(ok2 and ls or {}) do text[#text + 1] = StripEscapes(l) end
          out[#out + 1] = { stat = stat, value = value, text = table.concat(text, " / "), gem = ge.name }
        end
      end
    end
  end
end
return _poe2lab_json(out)""")

    def item_levels(self) -> dict[str, int]:
        """The character level each equipped item needs, by slot (0 when PoB does not know it)."""
        rows = self._json("""
local out = _poe2lab_array({})
for name, slot in pairs(build.itemsTab.slots) do
  local item = build.itemsTab.items[slot.selItemId]
  if item then out[#out + 1] = { slot = name, level = item.requirements and item.requirements.level or 0 } end
end
return _poe2lab_json(out)""")
        return {r["slot"]: r["level"] or 0 for r in rows}

    def gem_fits(self, group: int) -> list[str]:
        """The support gems (data.gems ids) that can support one of the group's active skills."""
        return self._json(f"""
local g = build.skillsTab.socketGroupList[{int(group)}]
local out = _poe2lab_array({{}})
if g then
  for id, d in pairs(data.gems) do
    local ge = d.grantedEffect
    if ge and ge.support then
      for _, a in ipairs(g.displaySkillList or {{}}) do
        if calcLib.canGrantedEffectSupportActiveSkill(ge, a) then out[#out + 1] = id break end
      end
    end
  end
end
return _poe2lab_json(out)""")

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

    def quest_rewards(self) -> list[dict]:
        """The campaign's rewards that change the character (PoB's data.questRewards, its "Quest Rewards" config):
        a fixed stat (on unless the build turned it off) or one of several options (none unless the build chose
        one); each with its config key and its value in this build."""
        rows = self._json("""
local out = _poe2lab_array({})
for _, q in ipairs(data.questRewards) do
  if q.useConfig ~= false then
    local var = "quest" .. q.Description .. q.Area .. q.Info
    out[#out + 1] = { var = var, act = q.Act, part = q.Description, area = q.Area, info = q.Info,
                      level = q.AreaLevel, stat = q.Stat, options = q.Options and _poe2lab_array(q.Options) or nil,
                      value = build.configTab.input[var] }
  end
end
return _poe2lab_json(out)""")
        for r in rows:
            if r.get("options"):
                r["value"] = r.get("value") or "None"
            else:
                r["value"] = r.get("value") is not False
        return rows

    def set_config_input(self, values: dict):
        """Set Configuration tab values for good (unlike what_if(config=...)) and recalculate."""
        if not values:
            return
        cfg = ", ".join(f"[ {lua_string(k)} ] = {_lua_value(v)}" for k, v in values.items())
        self._lua(f"""
local configTab = build.configTab
for k, v in pairs({{ {cfg} }}) do configTab.input[k] = v end
configTab:BuildModList()
build.calcsTab:BuildOutput()""")

    def can_parse_mod(self, line: str) -> bool:
        return self._lua(f"""
local mods, extra = modLib.parseMod({lua_string(line)})
return (mods and not extra) and "yes" or "no" """) == "yes"

    def logs(self, clear: bool = True) -> list[str]:
        lines = self._json("return _poe2lab_json(_poe2lab_array(_POE2LAB_LOG))")
        if clear:
            self._lua("_POE2LAB_LOG = {}")
        return lines
