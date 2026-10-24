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
from dataclasses import dataclass

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
PROJECTILE_RANGE = 12.0  # metres a projectile flies before it is gone (or comes back)
MIRROR_TOUCH = 0.8  # metres: a projectile this close to a mirror shatters it
MIRROR_COPIES = 7  # Mirror of Refraction: "Projectiles which shatter Mirrors are copied 7 times"
FAN_STEP = math.radians(8)  # the angle between the projectiles of one use
DOT_KEYS = ("TotalDot", "IgniteDPS", "PoisonDPS", "BleedDPS", "BurningGroundDPS", "CausticGroundDPS")


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


def skills(engine) -> list[dict]:
    """The build's skills as the dummy uses them: each active skill of an enabled group with PoB's numbers for it as
    the main skill - one use's damage on one target, uses per second, cooldown, duration, its area and projectiles -
    and what it is (damage, curse, mirrors, meta, buff). Curses socketed into Blasphemy are an aura around the
    character."""
    out = []
    groups = engine.skill_groups()
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
            out.append({
                "id": f"{g['index']}:{i}", "group": g["index"], "index": i, "name": a["name"], "kind": kind,
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
                "returns": "Breachlord's Amalgam" in supports,
                "triggered": "Triggered" in types or (kind != "meta" and any(x["name"].startswith("Cast on") for x in g["actives"])),
            })
    return out


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

    def damage(s: dict, d: Dummy) -> tuple[float, float]:
        key = (s["id"], d.kind, tuple(sorted(states[d.id])), tuple(sorted(curses[d.id])))
        if key not in cache:
            cfg = {"enemyLevel": level, **KINDS[d.kind], **{STATES[x]: True for x in states[d.id]}}
            off = [(c["group"], c["index"]) for c in curse_gems if c["id"] not in curses[d.id]]
            engine.set_main_skill(s["group"], s["index"])
            o = engine.what_if(config=cfg, disable_gems=_gem_pairs(engine, off))
            speed = _num(o, "Speed")
            cache[key] = (_num(o, "TotalDPS") / speed if speed else _num(o, "AverageHit"),
                          sum(_num(o, k) for k in DOT_KEYS))
        return cache[key]

    rows, per_dummy = [], {d.id: 0.0 for d in dummies}
    uses_through_mirrors = sum(uses_per_second(by_id[i], p) for i, p in places.items()
                               if by_id[i]["projectile"] and by_id[i]["kind"] == "damage")
    share = min(1.0, mirror_rate / uses_through_mirrors) if uses_through_mirrors and mirror_rate else (1.0 if not mirror_rate else 0.0)
    for sid, p in places.items():
        s = by_id[sid]
        if s["kind"] != "damage":
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
            "best": round(max(per_dummy.values(), default=0)), "mirrorShare": round(share, 2) if mirror_rate else None}


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
