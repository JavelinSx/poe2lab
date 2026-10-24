"""The dummy: the build's damage per second on target dummies laid out by hand - one boss or a pack - from all its
skills at once, each used the way the player sets it up (spammed for a share of the time, on its cooldown, every
N seconds, at a rate of its own when something triggers it).

Where things are is the player's: the dummies, each skill's target point, the zones of its curses, the Mirrors of
Refraction. Which dummy a skill hits comes from the skill's own numbers in PoB: an area skill hits the dummies within
its radius (metres) of its target point; a projectile skill flies from the character towards its target point,
piercing or stopping at the first dummy, coming back when it returns, and is copied by a mirror it passes (the
copies fly out from the mirror in a nova). A dummy's state - its rarity, the curses whose zone it is in, the
ailments the skills set to apply them put on it - is a PoB Configuration for that dummy: what PoB counts for each
skill on it. A skill's damage on one dummy is PoB's own (its DPS over its use rate: one use's damage on one target),
damage over time added while the skill keeps hitting it.

A rough estimate on purpose: positions, mirror copies and trigger rates are the player's guesses; PoB does every
number it can."""
import math
import re
from dataclasses import dataclass

from .. import knowledge
from .unmodeled import _times

# a dummy's kind -> PoB's Configuration (enemyIsBoss; rares by their own condition)
KINDS = {"normal": {"enemyIsBoss": "None"}, "rare": {"enemyIsBoss": "None", "conditionEnemyRareOrUnique": True},
         "boss": {"enemyIsBoss": "Boss"}, "pinnacle": {"enemyIsBoss": "Pinnacle"}, "uber": {"enemyIsBoss": "Uber"}}
# what a skill can be set to put on the dummies in its area -> PoB's Configuration box
STATES = {"shock": "conditionEnemyShocked", "freeze": "conditionEnemyFrozen", "chill": "conditionEnemyChilled",
          "ignite": "conditionEnemyIgnited", "armourBreak": "conditionEnemyArmourBroken",
          "coldExposure": "conditionEnemyColdExposure", "fireExposure": "conditionEnemyFireExposure",
          "lightningExposure": "conditionEnemyLightningExposure", "electrocute": "conditionEnemyElectrocuted"}
NOT_DAMAGE = {"Buff", "Persistent", "Aura", "Herald", "Warcry"}  # a damaging movement skill (a warp) still counts
DUMMY_RADIUS = 0.6  # metres: how wide a dummy is for a projectile to touch it
PROJECTILE_RADIUS = 0.3  # metres: how wide a flown projectile is (the game's sizes are not in PoB: the player sets it)
PROJECTILE_RANGE = 12.0  # metres a projectile flies before it is gone (or comes back)
MIRROR_TOUCH = 0.8  # metres: a projectile this close to a mirror shatters it
MIRROR_COPIES = 7  # Mirror of Refraction: "Projectiles which shatter Mirrors are copied 7 times"
FAN_STEP = math.radians(8)  # the angle between the projectiles of one use
DOT_KEYS = ("TotalDot", "IgniteDPS", "PoisonDPS", "BleedDPS", "BurningGroundDPS", "CausticGroundDPS")
# What PoB does not count, gone through for every skill: its gem's and supports' stats PoB leaves out and the gear
# lines of its weapon set PoB cannot read (poe2lab.knowledge). A line that holds at some point of a projectile's
# flight - for each pierce, after a pierce, returning - is read without its condition (PoB parses the rest) and
# applied by the flight; the rest is listed on the skill as not counted.
_WHEN = [
    ("perPierce", re.compile(r",?\s+for each (?:time (?:they|it) ha(?:ve|s) Pierced|enemy (?:they|it) ha(?:ve|s) "
                             r"Pierced|enemy Pierced)$", re.I)),
    ("afterPierce", re.compile(r",?\s+(?:after Piercing an Enemy|if (?:they|it) ha(?:ve|s) Pierced(?: an Enemy)?|"
                               r"against Pierced (?:targets|enemies)|to targets (?:they|it) Pierces?)$", re.I)),
]
_RETURN = re.compile(r"^(?:(Attack|Spell) )?Projectiles(?: from Supported Skills)? Return(?: to you)?"
                     r"(?: if they(?: have)? Pierced at least (\d+) times?)?$", re.I)
_PROJ_SUBJECT = re.compile(r"^(?:(Attack|Spell) )?Projectiles(?: from Supported Skills)? (?:deal|have|gain) ", re.I)
_QUIVER_BONUS = re.compile(r"(\d+)% increased bonuses gained from Equipped Quiver", re.I)
# skill stats the dummy uses by itself: the mirrors' limit and rate, one storm at a time
HANDLED = {"base_mirror_of_refraction_limit", "cooldown_recovery_modifiers_also_apply_to_repeat_interval",
           "lightning_storm_max_number_of_storms"}
# how a skill is aimed and moved with while used: nothing to count
_AIM = re.compile(r"performing_action|^console_|precise_cursor|contact_(?:position|direction)|show_cull_range|"
                  r"desired_amount|^base_is_projectile$|modular_projectiles|check_for_targets|hit_frequency_variance",
                  re.I)
# a gear line that may move a skill's damage (charges on kill, flask effects are the character's, not the skill's)
_DAMAGE_LINE = re.compile(r"\b(?:damage|critical|projectile|pierce|chain|fork|return|spell|attack|cast|area)\b", re.I)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _scaled(line: str, k: float) -> str:
    """The line's numbers k times, whole (PoB reads most lines in whole numbers)."""
    if k == 1:
        return line
    return _NUMBER.sub(lambda m: str(int(float(m.group()) * k + 0.5)), line)


def flight_line(text: str, can_parse) -> dict | None:
    """A line that holds at some point of a projectile's flight, as PoB reads it then: {"when": "perPierce" |
    "afterPierce", "line", "kind"} or {"when": "returns", "kind", "after": pierces needed}; "kind": the skills it is
    for (Attack, Spell) or None. None when it is no such line or PoB cannot read the rest."""
    text = " ".join(text.split())
    m = _RETURN.match(text)
    if m:
        return {"when": "returns", "kind": m.group(1) and m.group(1).capitalize(), "after": int(m.group(2) or 0)}
    for when, cond in _WHEN:
        if not cond.search(text):
            continue
        rest = cond.sub("", text)
        sm = _PROJ_SUBJECT.match(rest)
        kind = sm.group(1).capitalize() if sm and sm.group(1) else None
        tries = [rest] + ([rest[sm.end():]] if sm else [])
        for t in tries:
            t = t[:1].upper() + t[1:]
            if can_parse(t):
                return {"when": when, "line": t, "kind": kind}
    return None


def _worn(slot: str, weapon_set: int) -> bool:
    return not slot.startswith("Weapon") or ("Swap" in slot) == (weapon_set == 2)


def beyond_pob(gaps, group: dict, name: str, supports, items: dict, weapon_set: int, types, can_parse) -> dict:
    """What PoB leaves out for one skill, gone through line by line: its gem's and supports' stats (its group's) and
    the gear lines of the weapon set it is used with - a quiver's grown by the same set's "increased bonuses gained
    from Equipped Quiver". {"flight": [lines the flight applies], "returns", "returnAfter": pierces before a return,
    "notCounted": [the rest that may matter]}."""
    gems = {name, *supports}
    tag = f"(группа {group['index']})"
    quiver = 1 + sum(int(m.group(1)) for slot, it in items.items() if _worn(slot, weapon_set)
                     for line in _lines(it) if (m := _QUIVER_BONUS.search(line))) / 100
    out = {"flight": [], "returns": False, "returnAfter": 0, "notCounted": []}
    for gap in gaps:
        if gap.source == "skill":
            gem = gap.where[:-len(tag)].strip() if gap.where.endswith(tag) else None
            if gem not in gems or gap.what in HANDLED or _AIM.search(gap.what):
                continue
            src, from_item, scale = gem, False, 1.0
        else:
            m = re.match(r"^(.*) \((.+)\)$", gap.where)
            if not m or not _worn(m.group(2), weapon_set):
                continue
            it = items.get(m.group(2)) or {}
            src, from_item, scale = m.group(1), True, quiver if it.get("type") == "Quiver" else 1.0
        f = flight_line(gap.text, can_parse)
        if f:
            if "Projectile" not in types or (f["kind"] and f["kind"] not in types):
                continue  # another kind of skill's line
            if f["when"] == "returns":
                if f["after"]:
                    out["returnAfter"] = min(out["returnAfter"] or f["after"], f["after"])
                else:
                    out["returns"] = True
            else:
                out["flight"].append({"when": f["when"], "line": _scaled(f["line"], scale), "text": gap.text,
                                      "local": gap.text_local, "from": src, "item": from_item,
                                      "scale": round(scale, 2)})
            continue
        if from_item and not _DAMAGE_LINE.search(gap.text):
            continue
        if gap.likely_impact:
            out["notCounted"].append({"text": " ".join(gap.text.split()), "local": " ".join(gap.text_local.split()),
                                      "from": src, "item": from_item})
    return out


def _lines(it: dict) -> list[str]:
    return [m["line"] for k in ("implicit", "explicit", "enchant", "runes") for m in it.get(k) or []]


def _num(o: dict, key: str) -> float:
    v = o.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


class keep_main:
    """Puts the build's main skill back after the dummy has made each skill the main one in turn."""
    def __init__(self, engine):
        self.engine = engine

    def __enter__(self):
        info = self.engine.info()
        self.main = (info.get("mainSocketGroup"), info.get("mainActiveSkill") or 1)
        return self

    def __exit__(self, *exc):
        if self.main[0]:
            self.engine.set_main_skill(*self.main)
        return False


def skills(engine, statdesc_dir=None) -> list[dict]:
    """The build's skills as the dummy uses them: each active skill of an enabled group with PoB's numbers for it as
    the main skill - one use's damage on one target, uses per second, cooldown, duration, its area and projectiles -
    and what it is (damage, curse, mirrors, meta, buff). Curses socketed into Blasphemy are an aura around the
    character. What PoB leaves out of each skill is gone through (beyond_pob)."""
    out = []
    groups = engine.skill_groups()
    items = {it["slot"]: it for it in engine.equipped_item_details()}
    gaps = knowledge.collect(engine, statdesc_dir).gaps
    parsed: dict[str, bool] = {}
    can_parse = lambda line: parsed.setdefault(line, engine.can_parse_mod(line))  # noqa: E731
    shown = 2 if engine.second_weapon_set() else 1
    for g in groups:
        if not g["enabled"]:
            continue
        supports = [x["name"] for x in g["gems"] if x["support"] and x["enabled"]]
        aura = any(a["name"] == "Blasphemy" for a in g["actives"])
        for i, a in enumerate(g["actives"], 1):
            types = set(a["types"])
            engine.set_main_skill(g["index"], i)
            o = engine.what_if()
            speed = _num(o, "Speed")
            total = _num(o, "TotalDPS")
            kind = ("mirror" if a["name"] == "Mirror of Refraction" else "curse" if "AppliesCurse" in types
                    else "meta" if "Meta" in types or a["name"].startswith("Cast on") or a["name"] == "Blasphemy"
                    else "damage" if (total or _num(o, "AverageHit") or any(_num(o, k) for k in DOT_KEYS))
                    and not types & NOT_DAMAGE else "other")
            ws = g.get("weaponSet") or shown  # the set the skill is used with (both: the one the build shows)
            beyond = beyond_pob(gaps, g, a["name"], supports, items, ws, types, can_parse)
            out.append({
                "id": f"{g['index']}:{i}", "group": g["index"], "index": i, "name": a["name"], "kind": kind,
                "weaponSet": ws, "boundSet": g.get("weaponSet") or 0, "fixedSet": bool(g.get("fixedSet")),
                "flight": beyond["flight"], "notCounted": beyond["notCounted"],
                "returnAfter": beyond["returnAfter"],
                "sustained": "Sustained" in types and "Projectile" not in types,  # a storm that stands and strikes
                "travel": bool(types & {"Travel", "Movement"}),
                "types": sorted(types), "supports": supports, "inAura": aura and kind == "curse",
                "projectile": "Projectile" in types, "speed": speed,
                "perUse": total / speed if speed else _num(o, "AverageHit"), "dps": total,
                "dot": sum(_num(o, k) for k in DOT_KEYS),
                "cooldown": _num(o, "Cooldown"), "duration": _num(o, "Duration"),
                "radius": _num(o, "AreaOfEffectRadiusMetres"), "radius2": _num(o, "AreaOfEffectRadiusSecondaryMetres"),
                "projectiles": max(1, int(round(_num(o, "ProjectileCount") or 1))),
                "pierce": int(_num(o, "PierceCount")),  # how many dummies a projectile goes through (100: all)
                "returns": beyond["returns"],
                "triggered": "Triggered" in types or (kind != "meta" and any(x["name"].startswith("Cast on") for x in g["actives"])),
                "speedMod": _num(o, "ProjectileSpeedMod") or 1.0,
            })
            if kind == "mirror":  # how many copies a shattered mirror makes, how many mirrors at once
                out[-1]["copies"] = int(round(_num(o, "ProjectileCount"))) or MIRROR_COPIES
                out[-1]["limit"] = int(_gem_stat(engine, g, a["name"], "base_mirror_of_refraction_limit")) or MIRROR_LIMIT
    return out


def _gem_stat(engine, group: dict, name: str, stat: str) -> float:
    """A stat of the build's own gem (its level and quality counted): what the gem says, whether PoB uses it or not."""
    gem = next((x for x in group["gems"] if x["name"] == name and not x["support"]), None)
    if not gem:
        return 0.0
    v = engine._json(f"""
local g = build.skillsTab.socketGroupList[{int(group["index"])}]
local gem = g and g.gemList[{int(gem["index"])}]
local total = 0
if gem and gem.gemData then
  local ge = gem.gemData.grantedEffect
  for _, set in ipairs(ge.statSets or {{}}) do
    local ok, stats = pcall(calcLib.buildSkillInstanceStats, gem, ge, set, false)
    if ok and stats and stats["{stat}"] then total = math.max(total, stats["{stat}"]) end
  end
end
return _poe2lab_json({{ v = total }})""")
    return float(v.get("v") or 0)


@dataclass
class Dummy:
    id: str
    x: float
    y: float
    kind: str = "normal"


def _dist(ax, ay, bx, by) -> float:
    return math.hypot(ax - bx, ay - by)


def _along(px, py, ang, x, y) -> tuple[float, float]:
    """(how far along a ray from (px, py) at angle ang the point is, how far off the ray)."""
    dx, dy = math.cos(ang), math.sin(ang)
    t = (x - px) * dx + (y - py) * dy
    return t, abs(-(x - px) * dy + (y - py) * dx)


def _ray_hits(px, py, ang, dummies: list[Dummy], pierce: int, reach: float) -> list[str]:
    """The dummies a projectile from (px, py) at angle ang hits: the first and as many after it as it pierces."""
    on = sorted(((t, d.id) for d in dummies for t, off in [_along(px, py, ang, d.x, d.y)]
                 if 0 < t <= reach and off <= DUMMY_RADIUS), key=lambda x: x[0])
    return [i for _, i in on[:1 + max(pierce, 0)]]


def hits_per_use(skill: dict, place: dict, dummies: list[Dummy], mirrors: list[tuple[float, float]],
                 mirror_share: float = 1.0) -> dict[str, float]:
    """How many times one use of the skill hits each dummy: an area at its target point, or its projectiles flying
    from the character towards it (a fan when there are several, back again when they return), and the copies the
    mirrors it passes make. mirror_share: the part of the uses that find a mirror there (mirrors appear at a rate)."""
    tx, ty = place.get("x", 0.0), place.get("y", 0.0)
    hits = {d.id: 0.0 for d in dummies}
    if not skill["projectile"]:
        r = skill["radius"] or skill["radius2"] or 1.0
        for d in dummies:
            if _dist(d.x, d.y, tx, ty) <= r + DUMMY_RADIUS:
                hits[d.id] += 1
        return hits
    base = math.atan2(ty, tx) if (tx or ty) else 0.0
    n = skill["projectiles"]
    passes = 2 if skill["returns"] else 1
    for k in range(n):
        ang = base + (k - (n - 1) / 2) * FAN_STEP
        seen = set()
        for i in _ray_hits(0, 0, ang, dummies, skill["pierce"], PROJECTILE_RANGE):
            seen.add(i)
        for i in seen:  # only one projectile of a use hits a dummy (the game's rule), each pass
            hits[i] = max(hits[i], passes)
        # mirrors this projectile passes: each makes a nova of copies around itself
        for mx, my in mirrors:
            t, off = _along(0, 0, ang, mx, my)
            if 0 < t <= PROJECTILE_RANGE and off <= MIRROR_TOUCH:
                for c in range(MIRROR_COPIES):
                    cang = ang + 2 * math.pi * c / MIRROR_COPIES
                    for i in _ray_hits(mx, my, cang, dummies, skill["pierce"], PROJECTILE_RANGE):
                        hits[i] += passes * mirror_share / n  # the copies of one use, shared by its projectiles
    return hits


def uses_per_second(skill: dict, place: dict) -> float:
    """How often the skill hits: spammed for a share of the time, on its cooldown, every N seconds, at a rate of its
    own (a trigger), or all the time while it stands (a storm, a ground effect: PoB's rate)."""
    mode = place.get("mode", "spam")
    if mode == "sustain":  # a storm, a wall that keeps hitting while it stands: its own rate (PoB's)
        return skill["speed"]
    if mode == "cooldown":
        return 1 / skill["cooldown"] if skill["cooldown"] else skill["speed"]
    if mode == "interval":
        return 1 / max(float(place.get("interval") or 1), 0.05)
    if mode == "rate":
        return max(float(place.get("rate") or 0), 0.0)
    rate = skill["speed"] * max(min(float(place.get("share", 100)), 100), 0) / 100
    return min(rate, 1 / skill["cooldown"]) if skill["cooldown"] else rate


def calc(engine, scenario: dict, catalogue: list[dict] | None = None) -> dict:
    """The build's damage per second on the dummies of the scenario: per skill, per dummy and in all.
    scenario: {"level": enemy level, "dummies": [{"id", "x", "y", "kind"}], "skills": {skill id: {"on", "mode",
    "share", "interval", "rate", "x", "y", "split" (its hits shared by the dummies it reaches), "states": [STATES keys]}}, "curses": {skill id: {"on", "x", "y"}},
    "mirrors": [{"x", "y"}], "always": [STATES keys every dummy has]}."""
    catalogue = catalogue if catalogue is not None else skills(engine)
    by_id = {s["id"]: s for s in catalogue}
    dummies = [Dummy(str(d["id"]), float(d["x"]), float(d["y"]), d.get("kind", "normal") if d.get("kind") in KINDS else "normal")
               for d in scenario.get("dummies") or []]
    mirrors = [(float(m["x"]), float(m["y"])) for m in scenario.get("mirrors") or []]
    level = int(scenario.get("level") or 83)
    places = {k: v for k, v in (scenario.get("skills") or {}).items() if k in by_id and v.get("on", True)}
    curse_places = {k: v for k, v in (scenario.get("curses") or {}).items() if k in by_id}
    # mirrors: they appear at the Mirror of Refraction's rate; the uses that pass one share them
    mirror_skill = next((s for s in catalogue if s["kind"] == "mirror"), None)
    mirror_rate = 1 / mirror_skill["cooldown"] if mirror_skill and mirror_skill["cooldown"] else 0.0

    # each dummy's state: the ailments the skills put on it, the curses whose zone it is in
    states: dict[str, set] = {d.id: set(scenario.get("always") or []) for d in dummies}
    for sid, p in places.items():
        s = by_id[sid]
        if not p.get("states"):
            continue
        for i, n in hits_per_use(s, p, dummies, mirrors).items():
            if n:
                states[i] |= {x for x in p["states"] if x in STATES}
    curses: dict[str, set] = {d.id: set() for d in dummies}
    curse_gems = []
    for s in catalogue:
        if s["kind"] != "curse":
            continue
        curse_gems.append(s)
        p = curse_places.get(s["id"], {})
        if not p.get("on", True):
            continue
        cx, cy = (0.0, 0.0) if s["inAura"] else (float(p.get("x", 6)), float(p.get("y", 0)))
        r = s["radius"] or 2.0
        for d in dummies:
            if _dist(d.x, d.y, cx, cy) <= r + DUMMY_RADIUS:
                curses[d.id].add(s["id"])

    # PoB once per skill and dummy state (dummies alike share it)
    cache: dict[tuple, dict] = {}

    def damage(s: dict, d: Dummy, mods: tuple = ()) -> tuple[float, float]:
        key = (s["id"], d.kind, tuple(sorted(states[d.id])), tuple(sorted(curses[d.id])), mods)
        if key not in cache:
            cfg = {"enemyLevel": level, **KINDS[d.kind], **{STATES[x]: True for x in states[d.id]}}
            off = [(c["group"], c["index"]) for c in curse_gems if c["id"] not in curses[d.id]]
            engine.set_main_skill(s["group"], s["index"])
            o = engine.what_if(config=cfg, disable_gems=_gem_pairs(engine, off), mods=list(mods))
            speed = _num(o, "Speed")
            cache[key] = (_num(o, "TotalDPS") / speed if speed else _num(o, "AverageHit"),
                          sum(_num(o, k) for k in DOT_KEYS))
        return cache[key]

    rows, per_dummy = [], {d.id: 0.0 for d in dummies}
    # the projectile skills flown tick by tick (mirrors, piercing, returning); the rest by the layout alone
    flown = [(by_id[i], p) for i, p in places.items() if by_id[i]["kind"] == "damage" and by_id[i]["projectile"]
             and not by_id[i]["sustained"] and p.get("sim", True)]
    if flown:
        def at(s, d, n):
            # the lines PoB leaves out that hold at this point of the flight (beyond_pob), and the player's own crit
            mods = [f["line"] if f["when"] == "afterPierce" else _times(f["line"], n)
                    for f in s.get("flight") or [] if n]
            extra = float(places[s["id"]].get("critPerPierce") or 0)
            if extra and n:
                mods.append(f"{extra * n:g}% increased Critical Hit Chance")
            return damage(s, d, tuple(mods))[0]

        def hit_damage(s, d, pierced):
            n = min(pierced, MAX_PIERCE_STEPS)
            if n in PIERCE_POINTS:
                return at(s, d, n)
            lo = max(p for p in PIERCE_POINTS if p < n)
            hi = min(p for p in PIERCE_POINTS if p > n)
            a, b = at(s, d, lo), at(s, d, hi)
            return a + (b - a) * (n - lo) / (hi - lo)
        run = simulate(flown, dummies, mirrors, mirror_skill, hit_damage)
        for s, p in flown:
            st, on, total = run["stats"][s["id"]], {}, 0.0
            for d in dummies:
                got = run["damage"][s["id"]][d.id]
                if not got:
                    continue
                v = got / run["time"] + damage(s, d)[1]
                on[d.id] = round(v)
                total += v
                per_dummy[d.id] += v
            casts = st["casts"] or 1
            rows.append({"id": s["id"], "name": s["name"], "uses": round(st["casts"] / run["time"], 3), "dps": round(total),
                         "dummies": on, "hit": len(on), "sim": {"shattered": round(st["shattered"] / run["time"], 2),
                                                                "copiesPerCast": round(st["copies"] / casts, 1),
                                                                "hitsPerCast": round(st["hits"] / casts, 1),
                                                                # how far the pierces grow: what the per-pierce lines scale with
                                                                "avgPierced": round(st["pierced"] / st["hits"], 1) if st["hits"] else 0,
                                                                "maxPierced": st["maxPierced"],
                                                                "inAir": st.get("inAir", [])}})
    flown_ids = {s["id"] for s, _ in flown}
    uses_through_mirrors = sum(uses_per_second(by_id[i], p) for i, p in places.items()
                               if by_id[i]["projectile"] and by_id[i]["kind"] == "damage" and i not in flown_ids)
    share = min(1.0, mirror_rate / uses_through_mirrors) if uses_through_mirrors and mirror_rate else (1.0 if not mirror_rate else 0.0)
    for sid, p in places.items():
        s = by_id[sid]
        if s["kind"] != "damage" or sid in flown_ids:
            continue
        ups = uses_per_second(s, p)
        hits = hits_per_use(s, p, dummies, mirrors, share if mirror_rate else 1.0)
        if p.get("split"):  # one target a hit (a storm's strikes): its hits shared by the dummies in its area
            inside = sum(1 for n in hits.values() if n)
            hits = {i: n / inside for i, n in hits.items()} if inside else hits
        total, on = 0.0, {}
        for d in dummies:
            n = hits[d.id]
            if not n or not ups:
                continue
            per_use, dot = damage(s, d)
            v = per_use * n * ups + dot
            on[d.id] = round(v)
            total += v
            per_dummy[d.id] += v
        rows.append({"id": sid, "name": s["name"], "uses": round(ups, 3), "dps": round(total), "dummies": on,
                     "hit": sum(1 for n in hits.values() if n)})
    rows.sort(key=lambda r: -r["dps"])
    return {"total": round(sum(per_dummy.values())), "skills": rows,
            "dummies": [{"id": d.id, "kind": d.kind, "dps": round(per_dummy[d.id]), "states": sorted(states[d.id]),
                         "curses": sorted(curses[d.id])} for d in dummies],
            "best": round(max(per_dummy.values(), default=0)),
            # the layout's estimate of mirrors only for projectiles not flown (the flown ones count theirs)
            "mirrorShare": round(share, 2) if mirror_rate and uses_through_mirrors and mirrors else None}


def _gem_pairs(engine, groups: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """(socket group, active skill index) of a curse -> (socket group, gem index) to disable it."""
    out = []
    by_index = {g["index"]: g for g in engine.skill_groups()}
    for gi, ai in groups:
        g = by_index.get(gi)
        if not g:
            continue
        name = g["actives"][ai - 1]["name"] if ai - 1 < len(g["actives"]) else None
        gem = next((x for x in g["gems"] if x["name"] == name and not x["support"]), None)
        if gem:
            out.append((gi, gem["index"]))
    return out


# ---------- the projectiles flown tick by tick: mirrors, piercing, returning ----------
SIM_TIME = 20.0  # seconds of fight
SIM_WARMUP = 10.0  # the first seconds the mirrors' swarm grows in: the damage is counted after them
SIM_TICK = 1 / 30  # the game's server tick
BASE_SPEED = 4.0  # metres a second of a projectile before its speed modifiers (PoB does not know the skill's base)
MIRROR_LIMIT = 4  # "Limit 4 Mirrors of Refraction"
MAX_PROJECTILES = 4000  # a safety bound for a chain gone wild
MAX_PIERCE_STEPS = 100  # PoB's "pierces all"; a copy flying through a pack and back pierces 40-50 times
# the pierce counts PoB counts a hit at; between two of them the damage is drawn on a straight line (each pierce adds
# the same increased damage and crit chance: the line bends only where crit chance caps)
PIERCE_POINTS = (*range(0, 11), 12, 14, 16, 18, 20, 25, 30, 40, 50, 65, 80, 100)


def simulate(sim: list[tuple[dict, dict]], dummies: list[Dummy], spots: list[tuple[float, float]], mirror: dict | None,
             hit_damage) -> dict:
    """The projectile skills flown for SIM_TIME seconds, counted after SIM_WARMUP (the swarm grown). sim: (skill, its placement) pairs; spots: where mirrors
    appear (in turn, at the Mirror of Refraction's rate, up to its limit, each lasting its duration; the spots are
    all filled at the start - the fight is in its steady state); hit_damage(skill, dummy, pierced) -> one hit's
    damage. Each use fires its projectiles at its target point; a projectile pierces the dummies on its way as far as
    its pierce count lets it, shatters every live mirror it passes - the mirror copies it MIRROR_COPIES times all
    around, the copies keep its pierce count, live their own full time and can shatter other mirrors - and, when it
    returns, flies back to the character at the end of its flight, hitting again. A skill with a duration (Frostbolt:
    4 s) flies for its duration, PoB's; one without it for its range. {"damage": {skill id: {dummy id: total}}, "stats": {skill id:
    {"casts", "shattered", "copies", "hits"}}, "time"}."""
    interval = mirror["cooldown"] if mirror and mirror["cooldown"] else 0.0
    limit = (mirror or {}).get("limit") or MIRROR_LIMIT
    copies = (mirror or {}).get("copies") or MIRROR_COPIES
    lifetime = mirror["duration"] if mirror and mirror["duration"] else 8.0
    live: dict[int, float] = {}  # spot index -> when the mirror there disappears
    if interval:
        for i in range(min(limit, len(spots))):
            live[i] = lifetime
    next_spot, next_mirror = (min(limit, len(spots)) % len(spots)) if spots else 0, interval
    damage = {s["id"]: {d.id: 0.0 for d in dummies} for s, _ in sim}
    stats = {s["id"]: {"casts": 0, "shattered": 0, "copies": 0, "hits": 0, "pierced": 0, "maxPierced": 0}
             for s, _ in sim}
    shots = []  # live projectiles
    next_cast = {s["id"]: 0.0 for s, _ in sim}
    by_id = {s["id"]: (s, p) for s, p in sim}
    t = 0.0
    while t < SIM_TIME:
        # mirrors: the old ones go, a new one appears at the next free spot at the mirrors' rate
        for i in [i for i, end in live.items() if end <= t]:
            del live[i]
        if interval and spots and t >= next_mirror:
            next_mirror += interval
            if len(live) < limit:
                for k in range(len(spots)):
                    i = (next_spot + k) % len(spots)
                    if i not in live:
                        live[i] = t + lifetime
                        next_spot = (i + 1) % len(spots)
                        break
        # casts
        for sid, (s, p) in by_id.items():
            ups = uses_per_second(s, p)
            if ups <= 0 or t < next_cast[sid]:
                continue
            next_cast[sid] = t + 1 / ups
            stats[sid]["casts"] += 1
            tx, ty = float(p.get("x", 0)), float(p.get("y", 0))
            base = math.atan2(ty, tx) if (tx or ty) else 0.0
            speed = float(p.get("speed") or BASE_SPEED) * s.get("speedMod", 1.0)
            life = float(s.get("duration") or 0)
            reach = speed * life if life > 0 else float(p.get("range") or PROJECTILE_RANGE)
            for k in range(s["projectiles"]):
                ang = base + (k - (s["projectiles"] - 1) / 2) * FAN_STEP
                shots.append({"sid": sid, "x": 0.0, "y": 0.0, "a": ang, "v": speed, "left": reach, "reach": reach,
                              "pierced": 0, "back": False, "hit": set()})
        # flight
        alive = []
        for sh in shots:
            s, p = by_id[sh["sid"]]
            touch = DUMMY_RADIUS + float(p.get("width", PROJECTILE_RADIUS))
            step = min(sh["v"] * SIM_TICK, sh["left"])
            x0, y0 = sh["x"], sh["y"]
            if sh["back"]:  # flying back to the character
                sh["a"] = math.atan2(-y0, -x0)
            dx, dy = math.cos(sh["a"]), math.sin(sh["a"])
            # what lies on this tick's way, nearest first: dummies and live mirrors
            ahead = []
            for d in dummies:
                if d.id in sh["hit"]:
                    continue
                along, off = _along(x0, y0, sh["a"], d.x, d.y)
                if 0 <= along <= step and off <= touch:
                    ahead.append((along, "d", d))
            for i in list(live):
                mx, my = spots[i]
                along, off = _along(x0, y0, sh["a"], mx, my)
                if 0 <= along <= step and off <= MIRROR_TOUCH:
                    ahead.append((along, "m", i))
            ahead.sort(key=lambda x: x[0])
            stopped = False
            for along, what, obj in ahead:
                if what == "d":
                    damage[sh["sid"]][obj.id] += hit_damage(s, obj, sh["pierced"])
                    st = stats[sh["sid"]]
                    st["hits"] += 1
                    st["pierced"] += sh["pierced"]
                    st["maxPierced"] = max(st["maxPierced"], sh["pierced"])
                    sh["hit"].add(obj.id)
                    if sh["pierced"] >= s["pierce"] and not sh["back"]:
                        stopped = True  # no pierce left: the projectile ends here
                        break
                    sh["pierced"] = min(sh["pierced"] + 1, MAX_PIERCE_STEPS)
                elif obj in live and len(shots) + len(alive) < MAX_PROJECTILES:
                    del live[obj]
                    mx, my = spots[obj]
                    stats[sh["sid"]]["shattered"] += 1
                    for c in range(copies):
                        alive.append({**sh, "x": mx, "y": my, "a": sh["a"] + 2 * math.pi * (c + 1) / copies,
                                      "left": sh["reach"], "back": False, "hit": set()})
                    stats[sh["sid"]]["copies"] += copies
            if stopped:
                continue
            sh["x"], sh["y"], sh["left"] = x0 + dx * step, y0 + dy * step, sh["left"] - step
            if sh["back"] and math.hypot(sh["x"], sh["y"]) <= 0.5:
                continue  # back with the character
            if sh["left"] <= 1e-6:
                if (s["returns"] or s.get("returnAfter") and sh["pierced"] >= s["returnAfter"]) and not sh["back"]:
                    sh["back"], sh["hit"] = True, set()
                    sh["left"] = math.hypot(sh["x"], sh["y"]) + 1
                else:
                    continue
            alive.append(sh)
        shots = alive
        t += SIM_TICK
        if t - SIM_TICK < SIM_WARMUP <= t:  # the swarm has grown: count from here
            damage = {sid: {d.id: 0.0 for d in dummies} for sid in damage}
            for st in stats.values():
                st.update(casts=0, shattered=0, copies=0, hits=0, pierced=0, maxPierced=0)
        # how many are in the air: the swarm the mirrors grow, second by second
        second = min(int(t), int(SIM_TIME) - 1)
        for sid in stats:
            n = sum(1 for sh in shots if sh["sid"] == sid)
            peaks = stats[sid].setdefault("inAir", [0] * int(SIM_TIME))
            peaks[second] = max(peaks[second], n)
    return {"damage": damage, "stats": stats, "time": SIM_TIME - SIM_WARMUP}
