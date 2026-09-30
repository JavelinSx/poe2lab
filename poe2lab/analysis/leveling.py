"""Levelling up to a build. Guides are made for level 75 and above; up to it the player levels on their own. This
gives the ways the build's class can level - its weapons and elements, from PoB's gem data by the class's
attributes - and a roadmap from level 1 by the campaign's acts. Above all it says when to switch to the build and
why: the level by which every piece that carries the build's power can be had - its main skill, and the supports
and uniques PoB measures the build losing most without."""
from .. import newbuild
from .gradients import metric_changes
from .skills import UNCUT_SUPPORT_AREA, available_level
from .threats import CAMPAIGN, MAPS_LEVEL, MapProfile

# PoB's weapon types -> the weapon a way of levelling is played with
WEAPONS = {"Staff": "quarterstaff", "One Hand Mace": "mace", "Two Hand Mace": "mace", "Bow": "bow",
           "Crossbow": "crossbow", "Spear": "spear", "Talisman": "talisman"}
ELEMENTS = ("Fire", "Cold", "Lightning", "Chaos", "Physical")
ATTRIBUTES = {"str": "strength", "dex": "dexterity", "int": "intelligence"}
# what a character does not level with: buffs, auras, heralds, warcries, movement skills
NOT_LEVELLING = {"Buff", "Persistent", "Herald", "Warcry", "Travel", "Movement", "Meta", "Aura"}
EARLY_LEVEL = 7  # a way of levelling has a skill from this level at the latest
SECOND_LEVEL = 23  # ... and a second one by this level
MAX_WAYS = 6
CORE_SUPPORT = 10.0  # % of the main skill's damage a support carries to be part of the switch
CORE_ITEM = 15.0  # % of the build's damage (or, for defence uniques, EHP) a unique carries to count
NO_ITEM_SLOTS = ("Jewel", "Flask", "Charm")  # not what the switch waits for
# the ascendancy's trials: which part of the game each pair of points comes in (the order, not an exact place)
TRIALS = ["act2", "interlude", "maps", "maps"]


def stages() -> list[dict]:
    """The campaign's acts by character level (area level ~ character level) with each one's resistance penalty,
    then maps."""
    out, low = [], 1
    for top, key, penalty in CAMPAIGN:
        out.append({"key": key, "from": low, "to": top, "penalty": penalty})
        low = top + 1
    out.append({"key": "maps", "from": MAPS_LEVEL, "to": None, "penalty": MapProfile().resist_penalty})
    return out


def stage_of(level: int | None) -> str | None:
    if not level:
        return None
    return next(s["key"] for s in stages() if s["to"] is None or level <= s["to"])


def way_of(gem: dict) -> tuple[str, str | None] | None:
    """How a skill gem levels: (weapon, element), ("spell", element), ("minion", None); None for what one does not
    level with (buffs, movement, skills of any weapon or of none)."""
    types = set(gem["types"])
    if "CreatesMinion" in types:
        return "minion", None
    if not types & {"Attack", "Spell"} or types & NOT_LEVELLING:
        return None
    element = next((e.lower() for e in ELEMENTS if e in types), "physical")
    if "Attack" not in types:
        return "spell", element
    weapons = {WEAPONS.get(w) for w in gem.get("weapons", [])}
    if len(weapons) != 1 or None in weapons:  # bare hands, a shield, or every weapon (totems)
        return None
    return weapons.pop(), element


def _gem_level(g: dict) -> int | None:
    return available_level({"tier": g["tier"], "support": g["support"], "reqLevel": (g.get("reqs") or [0])[0]})


def ways(engine, catalog: list[dict] | None = None) -> dict:
    """The ways the build's class can level: the skill gems of its attributes grouped by weapon and element, each
    with its first skills and when they drop; the build's own skills first, ways like the build's next."""
    info = engine.info()
    cls = next((c for c in newbuild.classes(engine) if c["name"] == info["class"]), None)
    primary = {name for key, name in ATTRIBUTES.items() if cls and cls[key] > 7}
    catalog = catalog if catalog is not None else engine.gem_catalog()
    by_name = {g["name"]: g for g in catalog if not g["support"]}
    groups: dict[tuple, list[dict]] = {}
    for g in by_name.values():
        way = way_of(g) if g["tier"] > 0 else None
        attrs = {t for t in g["tags"] if t in ATTRIBUTES.values()}
        level = _gem_level(g)
        if way is None or level is None or not attrs or not attrs <= primary:
            continue
        groups.setdefault(way, []).append({"name": g["name"], "tier": g["tier"], "level": level})
    main = engine.main_skill()
    main_way = way_of(by_name[main]) if main in by_name else None
    def enough(skills):
        early = [s["level"] for s in skills if s["level"] <= SECOND_LEVEL]
        return len(early) >= 2 and min(early) <= EARLY_LEVEL

    # a weapon's elements with too few skills each make one way of that weapon ("Talisman": a slam of each element)
    for weapon in {w for w, e in groups if w not in ("spell", "minion")}:
        thin = [k for k in groups if k[0] == weapon and not enough(groups[k])]
        if len(thin) > 1:
            groups[(weapon, None)] = [s for k in thin for s in groups.pop(k)]
    out = []
    for (weapon, element), skills in groups.items():
        skills.sort(key=lambda s: (s["level"], s["name"]))
        if not enough(skills):
            continue
        like = (weapon, element) == main_way or (element is None and bool(main_way) and weapon == main_way[0])
        out.append({"id": f"{weapon}:{element or ''}", "weapon": weapon, "element": element, "skills": skills[:6],
                    "from": skills[0]["level"], "likeBuild": like,
                    "sameWeapon": bool(main_way) and weapon == main_way[0]})
    out.sort(key=lambda w: (not w["likeBuild"], not w["sameWeapon"], w["from"], -len(w["skills"])))
    own = _build_way(engine, by_name, main, main_way)
    return {"class": info["class"], "ascendancy": info["ascendancy"], "level": info["level"],
            "attributes": sorted(primary), "mainSkill": main, "ways": ([own] if own else []) + out[:MAX_WAYS]}


def _build_way(engine, by_name: dict, main: str | None, main_way) -> dict | None:
    """Levelling with the build's own damage skills from the start, each as soon as it drops."""
    skills, seen = [], set()
    for g in engine.skill_groups():
        for gem in g["gems"]:
            cat = by_name.get(gem["name"])
            if gem["support"] or gem["name"] in seen or not cat or way_of(cat) is None:
                continue
            seen.add(gem["name"])
            level = available_level(gem)
            if level is not None:
                skills.append({"name": gem["name"], "tier": gem.get("tier") or 0, "level": level,
                               "main": gem["name"] == main})
    if not skills:
        return None
    skills.sort(key=lambda s: (not s["main"], s["level"]))
    return {"id": "build", "weapon": main_way[0] if main_way else None, "element": main_way[1] if main_way else None,
            "skills": skills[:6], "from": min(s["level"] for s in skills), "likeBuild": True, "sameWeapon": True}


def _until_build(own: dict, all_ways: list[dict]) -> dict:
    """The build's own skills, and before the first of them drops the skills of the way most like the build."""
    first = min(s["level"] for s in own["skills"])
    if first <= EARLY_LEVEL:
        return own
    others = [w for w in all_ways if w["id"] != "build"]
    near = next((w for w in others if w["likeBuild"]), None) or next((w for w in others if w["sameWeapon"]), None) \
        or (others[0] if others else None)
    if near is None:
        return own
    names = {x["name"] for x in own["skills"]}
    before = [s | {"until": True} for s in near["skills"] if s["level"] < first and s["name"] not in names]
    return own | {"skills": sorted(before + own["skills"], key=lambda s: s["level"]), "until": near["id"]}


def ascendancy_order(engine, config: dict, mode: str) -> list[dict]:
    """The build's ascendancy notables, most worth first (PoB: what the build loses without each), with the trial
    their points come from."""
    g = engine.tree_graph()
    base = engine.what_if(config=config)
    key, other = ("ehp", "dps") if mode == "defence" else ("dps", "ehp")
    out = []
    for n in g["nodes"]:
        if n["asc"] and n["alloc"] and n["type"] == "Notable":
            change = metric_changes(engine.what_if(config=config, remove_nodes=[n["id"]]), base)
            out.append({"id": n["id"], "name": n["name"], "stats": n["stats"], "dps": -change["dps"], "ehp": -change["ehp"]})
    out.sort(key=lambda n: (-n[key], -n[other]))
    for i, n in enumerate(out):
        n["trial"] = i + 1
        n["stage"] = TRIALS[min(i, len(TRIALS) - 1)]
    return out


def _skill_source(engine, name: str, levels: dict, asc: list[dict]) -> dict:
    """Where a skill not cut from an uncut gem comes from: an ascendancy notable (the trial its points come in) or
    an item (the level it needs); {} when PoB does not say."""
    wanted = f"grants skill: {name}".lower()
    for n in asc:
        if any(wanted in line.lower() for line in n["stats"]):
            first = next(st for st in stages() if st["key"] == n["stage"])
            return {"source": "ascendancy", "sourceName": n["name"], "trial": n["trial"], "level": first["from"],
                    "approx": True}
    for item in engine.equipped_item_details():
        if any(name.lower() in line["line"].lower() for line in item["explicit"] + item["implicit"]):
            return {"source": "item", "sourceName": item["name"], "level": levels.get(item["slot"]) or None}
    return {}


def _first_of_family(gem: dict, catalog: list[dict]) -> dict | None:
    """The lowest tier of a support's family when it drops earlier ("Close Combat I" for "Close Combat II")."""
    fam = next((g["family"] for g in catalog if g["name"] == gem["name"] and g["support"]), None)
    if fam is None:
        return None
    own = available_level(gem)
    first = None
    for g in catalog:
        if g["support"] and g["family"] == fam and g["name"] != gem["name"]:
            lv = _gem_level(g)
            if lv is not None and (own is None or lv < own) and (first is None or lv < first["level"]):
                first = {"name": g["name"], "level": lv}
    return first


def switch(engine, config: dict, trade: bool = True, catalog: list[dict] | None = None,
           asc: list[dict] | None = None) -> dict:
    """When to switch to the build and why: every piece that carries its power with the level it can be had from and
    what the build loses without it (PoB). The switch is the level by which the main skill and every core piece -
    a support worth CORE_SUPPORT% of the main skill's damage (its family's first tier counts: "Close Combat I" is
    there long before "II"), a unique worth CORE_ITEM% of the damage (only when trading: a unique may never drop) -
    can all be had; `decisive` are the ones that set it. A unique that gives defence only does not hold the switch
    back: it is put on when it can be."""
    catalog = catalog if catalog is not None else engine.gem_catalog()
    asc = asc if asc is not None else ascendancy_order(engine, config, "damage")
    groups = engine.skill_groups()
    main = next((g for g in groups if g["main"]), None)
    base = engine.what_if(config=config)
    levels = engine.item_levels()
    parts = []
    if main:
        name = engine.main_skill()
        skill = next((x for x in main["gems"] if not x["support"] and x["name"] == name), None) \
            or next((x for x in main["gems"] if not x["support"]), None)
        if skill:
            part = {"kind": "skill", "name": skill["name"], "level": available_level(skill), "core": True}
            if part["level"] is None:
                part |= _skill_source(engine, skill["name"], levels, asc)
            parts.append(part)
        for gem in main["gems"]:
            if not gem["support"] or not gem["enabled"]:
                continue
            without = engine.what_if(config=config, disable_gems=[(main["index"], gem["index"])])
            worth = -metric_changes(without, base)["dps"]
            part = {"kind": "support", "name": gem["name"], "level": available_level(gem), "dps": worth,
                    "core": worth >= CORE_SUPPORT}
            first = _first_of_family(gem, catalog)
            if first:
                part |= {"full": part["level"], "firstName": first["name"], "level": first["level"]}
            parts.append(part)
    for item in engine.equipped_item_details():
        if item["rarity"] != "UNIQUE" or item["slot"].startswith(NO_ITEM_SLOTS):
            continue
        change = metric_changes(engine.what_if(config=config, remove_slot=item["slot"]), base)
        dps, ehp = -change["dps"], -change["ehp"]
        parts.append({"kind": "unique", "name": item["name"], "slot": item["slot"],
                      "level": levels.get(item["slot"]) or None, "dps": dps, "ehp": ehp,
                      "core": dps >= CORE_ITEM, "defence": dps < CORE_ITEM <= ehp, "counted": trade})
    counted = [p for p in parts if p["core"] and p["level"] and p.get("counted", True)]
    level = max((p["level"] for p in counted), default=None)
    for p in parts:
        p["decisive"] = p in counted and p["level"] == level
    order = {"skill": 0, "support": 1, "unique": 2}
    parts.sort(key=lambda p: (not p["core"], order[p["kind"]], -(p.get("dps") or 0)))
    return {"level": level, "stage": stage_of(level), "parts": parts, "trade": trade,
            "mainDps": base.get("CombinedDPS", 0)}


def tree_order(engine) -> list[dict]:
    """The build's notables and keystones in the order a character reaches them from its class's start, each with
    about how many points the tree has spent by then (the build's own nodes nearer the start)."""
    g = engine.tree_graph()
    nodes = {n["id"]: n for n in g["nodes"] if not n["asc"]}
    start = next((n for n in nodes.values() if n["type"] == "ClassStart" and n["alloc"]), None)
    if start is None:
        return []
    dist, queue = {start["id"]: 0}, [start["id"]]
    while queue:  # breadth first through the allocated nodes
        nid = queue.pop(0)
        for m in nodes[nid]["links"]:
            n = nodes.get(m)
            if n and n["alloc"] and m not in dist:
                dist[m] = dist[nid] + 1
                queue.append(m)
    main_tree = sorted(d for nid, d in dist.items() if nid != start["id"] and not nodes[nid].get("mode"))
    out = []
    for nid, d in sorted(dist.items(), key=lambda x: x[1]):
        n = nodes[nid]
        if n["type"] in ("Notable", "Keystone") and not n.get("mode"):
            out.append({"id": nid, "name": n["name"], "type": n["type"], "stats": n["stats"],
                        "points": sum(1 for x in main_tree if x <= d)})
    return out


def roadmap(engine, rage: int | None, mana_sustained: bool, answers: dict, character_level: int | None = None) -> dict:
    """From level 1 to the build, act by act: the skills of the chosen way as they drop, new support tiers, the
    build's notables in the order they are reached, its ascendancy by trials, the resistance penalty - and the
    switch to the build with its reasons. `answers`: way, trade (bool), pace ("fast"/"safe"), novice (bool)."""
    mode = "defence" if answers.get("pace") == "safe" else "damage"
    trade = bool(answers.get("trade", True))
    catalog = engine.gem_catalog()
    all_ways = ways(engine, catalog)
    way = next((w for w in all_ways["ways"] if w["id"] == answers.get("way")), None) or all_ways["ways"][0]
    config = MapProfile(rage=rage, mana_sustained=mana_sustained).config()
    asc = ascendancy_order(engine, config, mode)
    sw = switch(engine, config, trade, catalog, asc)
    notables = tree_order(engine)
    if way["id"] == "build":  # until the build's skills drop: the way closest to it
        way = _until_build(way, all_ways["ways"])
    build_gems = {}
    for g in engine.skill_groups():
        for gem in g["gems"]:
            lv = available_level(gem)
            if lv is not None and g["enabled"] and gem["enabled"]:
                build_gems.setdefault(gem["name"], {"name": gem["name"], "support": gem["support"], "level": lv})
    core = {p["name"] for p in sw["parts"] if p["core"]}
    out, taken = [], 0
    for st in stages():
        low, high = st["from"], st["to"] or 100
        points = high - 1  # passive points by the stage's end from levels alone
        tree = [n for n in notables if taken < n["points"] <= points] if st["to"] else \
            [n for n in notables if n["points"] > taken]
        taken = max([taken] + [n["points"] for n in tree])
        before_switch = sw["level"] is None or low <= sw["level"]
        out.append(st | {
            "skills": [s for s in way["skills"] if low <= s["level"] <= high]
            if before_switch or way["id"] == "build" else [],
            "gems": [x for x in build_gems.values() if low <= x["level"] <= high and x["name"] in core],
            "later": [x for x in build_gems.values() if low <= x["level"] <= high and x["name"] not in core],
            "supportTier": [t for t, lv in UNCUT_SUPPORT_AREA.items() if low <= lv <= high and t > 1],
            "tree": tree, "ascendancy": [a for a in asc if a["stage"] == st["key"]],
            "switch": sw["level"] is not None and low <= sw["level"] <= high,
            "here": character_level is not None and low <= character_level <= high,
            "uniques": [p for p in sw["parts"] if p["kind"] == "unique" and (p["core"] or p["defence"])
                        and p["level"] and low <= p["level"] <= high],
        })
    return {"class": all_ways["class"], "ascendancy": all_ways["ascendancy"], "guideLevel": all_ways["level"],
            "mainSkill": all_ways["mainSkill"], "way": way, "answers": answers | {"way": way["id"]}, "mode": mode,
            "switch": sw, "stages": out, "characterLevel": character_level}
