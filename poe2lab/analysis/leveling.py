"""Levelling up to a build. Guides are made for level 75 and above; up to it the player levels on their own. This
gives the ways the build's class can level - its weapons and elements, from PoB's gem data by the class's
attributes - and a roadmap from level 1 by the campaign's acts. Above all it says when to switch to the build and
why: the level by which every piece that carries the build's power can be had - its main skill, the supports and
uniques PoB measures the build losing most without, and what the main skill stands on (the chain): its buffs, the
skills that make what it spends (charges, rage), and the Spirit all of them reserve."""
import re

from .. import newbuild
from .combat import made_by_lines
from .gradients import metric_changes
from .skills import UNCUT_SUPPORT_AREA, available_level, mechanics_of
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
# what a skill spends that PoB is told about in its Configuration instead of following where it comes from: the box
# and the value that takes it away
CHAIN_CONFIG = {"power": ("usePowerCharges", False), "frenzy": ("useFrenzyCharges", False),
                "endurance": ("useEnduranceCharges", False), "rage": ("multiplierRage", 0)}
_SPIRIT = re.compile(r"\+(\d+) to Spirit", re.I)
# Invoker's "Lead me through Grace...": "+1 to Spirit for every 8 Item Energy Shield on Equipped Body Armour"
_ARMOUR_SPIRIT = re.compile(r"\+1 to Spirit for every (\d+) (?:Item )?(Energy Shield|Evasion Rating|Armour)\b[^.]*Body Armour",
                            re.I)
_NO_GEAR_SPIRIT = re.compile(r"cannot gain spirit from equipment", re.I)


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


def _gem_source(engine, gem: dict, levels: dict, asc: list[dict]) -> dict:
    """When an active gem can be had: its uncut gem's drop, or the ascendancy notable or item that grants it."""
    part = {"name": gem["name"], "level": available_level(gem)}
    if part["level"] is None:
        part |= _skill_source(engine, gem["name"], levels, asc)
    return part


def _spirit(engine, config: dict, base: dict, need: float, levels: dict, asc: list[dict]) -> dict:
    """Whether the Spirit the build's core reserves can be had, and from which level: the campaign's quests (each at
    its area's level), the items that give it (each at its level; Invoker's Spirit from body armour counts as the
    armour's), and the rest (the tree) from the start. With an ascendancy notable that turns body armour defences
    into Spirit and forbids Spirit from equipment: what the armour must give."""
    sources = []
    for q in engine.quest_rewards():
        m = _SPIRIT.search(q.get("stat") or "")
        if m:
            sources.append({"kind": "quest", "name": q["info"], "area": q["area"], "part": q["part"],
                            "spirit": int(m.group(1)), "level": q["level"], "on": bool(q["value"])})
    names = {it["slot"]: it["name"] for it in engine.equipped_item_details()}
    for slot, level in levels.items():
        if slot.startswith(NO_ITEM_SLOTS) or slot not in names:
            continue
        gives = base.get("Spirit", 0) - engine.what_if(config=config, remove_slot=slot).get("Spirit", 0)
        if gives >= 1:
            sources.append({"kind": "item", "name": names[slot], "slot": slot, "spirit": round(gives), "level": level or None})
    counted = sum(x["spirit"] for x in sources if x["kind"] == "item" or x["on"])
    rest = round(base.get("Spirit", 0) - counted)
    if rest >= 1:
        sources.append({"kind": "other", "name": "", "spirit": rest, "level": None})
    total, level = 0, None
    for x in sorted(sources, key=lambda x: x["level"] or 0):
        total += x["spirit"]
        if level is None and total >= need:
            level = x["level"] or 1
    if level is None:  # even the build as its file has it reserves more than it has
        level = max((x["level"] or 0 for x in sources), default=0) or None
    armour = None
    for n in asc:
        rates = [{"per": int(m.group(1)), "what": m.group(2)} for line in n["stats"] if (m := _ARMOUR_SPIRIT.search(line))]
        if rates:
            quests = sum(x["spirit"] for x in sources if x["kind"] == "quest")
            armour = {"node": n["name"], "rates": rates, "need": max(0, round(need - quests)),
                      "noGear": any(_NO_GEAR_SPIRIT.search(line) for line in n["stats"])}
    return {"kind": "spirit", "name": "Spirit", "need": round(need), "have": round(total), "level": level,
            "short": total < need, "sources": sources, "armour": armour, "core": True}


def chain(engine, config: dict, groups: list[dict], main: dict | None, skill: dict | None, base: dict,
          levels: dict, asc: list[dict]) -> list[dict]:
    """What the main skill stands on besides its own gems - the build does not start before all of it can be had:
    - buffs: other skills whose loss costs the main skill CORE_SUPPORT% of its damage (Eternal Rage...);
    - sources: what it spends that PoB takes from its Configuration (charges, rage) and which of the build's skills
      make it - by the way the build keeps it up: a meta gem triggering it (Profane Ritual by Cast on Critical)
      before casting it by hand;
    - Spirit: what the main skill, the buffs and the sources reserve, against when that much Spirit can be had."""
    if not main or not skill:
        return []
    out, reserving = [], {}
    loss = {}
    for g in groups:
        if not g["enabled"] or not g["gems"]:
            continue
        o = engine.what_if(config=config, disable_gems=[(g["index"], x["index"]) for x in g["gems"]])
        loss[g["index"]] = {"dps": -metric_changes(o, base)["dps"],
                            "spirit": max(0, round(o.get("SpiritUnreserved", 0) - base.get("SpiritUnreserved", 0)))}
    reserving[main["index"]] = loss.get(main["index"], {}).get("spirit", 0)
    for g in groups:
        active = next((x for x in g["gems"] if not x["support"] and x["enabled"]), None)
        if g["index"] == main["index"] or g["index"] not in loss or not active:
            continue
        if loss[g["index"]]["dps"] >= CORE_SUPPORT:
            out.append({"kind": "buff", "dps": loss[g["index"]]["dps"], "spirit": loss[g["index"]]["spirit"],
                        "group": g["index"], "core": True} | _gem_source(engine, active, levels, asc))
            reserving[g["index"]] = loss[g["index"]]["spirit"]
    uses = set(mechanics_of(skill)["uses"])
    uses |= {k for x in main["gems"] if x["support"] and x["enabled"] for k in mechanics_of(x)["uses"]}
    # made without another skill: by the main skill's own gems, a passive or an item
    own = {k for x in main["gems"] if x["enabled"] for k in mechanics_of(x)["creates"]}
    lines = [line for n in engine.tree_graph()["nodes"] if n["alloc"] for line in n["stats"]]
    lines += [l["line"] for it in engine.equipped_item_details() for k in ("implicit", "explicit", "runes", "enchant")
              for l in it.get(k, [])]
    own |= made_by_lines(lines)
    for key, (var, off) in CHAIN_CONFIG.items():
        if key not in uses or key in own:
            continue
        lost = -metric_changes(engine.what_if(config=config | {var: off}), base)["dps"]
        if lost < CORE_SUPPORT:
            continue
        paths = []
        for g in groups:
            if not g["enabled"] or g["index"] == main["index"]:
                continue
            maker = next((x for x in g["gems"] if not x["support"] and x["enabled"] and key in mechanics_of(x)["creates"]
                          and "Meta" not in x.get("types", [])), None)
            if maker:
                meta = next((x for x in g["gems"] if not x["support"] and "Meta" in x.get("types", [])), None)
                paths.append((g, maker, meta))
        if not paths:
            continue  # made by the tree or an item: nothing to wait for
        g, maker, meta = next((p for p in paths if p[2]), paths[0])
        buff = next((b for b in out if b["kind"] == "buff" and b["group"] == g["index"]), None)
        if buff:  # a buff that makes it (Eternal Rage): one piece
            buff["mechanic"] = key
            continue
        part = {"kind": "source", "mechanic": key, "dps": lost, "spirit": loss.get(g["index"], {}).get("spirit", 0),
                "core": True} | _gem_source(engine, maker, levels, asc)
        if meta:
            via = _gem_source(engine, meta, levels, asc)
            part |= {"via": meta["name"], "viaLevel": via["level"]}
            if via["level"] and part["level"]:
                part["level"] = max(part["level"], via["level"])
            hand = next((p for p in paths if not p[2]), None)
            if hand:  # cast by hand meanwhile: no Spirit, but not steady
                part["byHand"] = _gem_source(engine, hand[1], levels, asc)["level"]
        out.append(part)
        reserving[g["index"]] = part["spirit"]
    need = sum(reserving.values())
    if need >= 1:
        out.append(_spirit(engine, config, base, need, levels, asc))
    return out


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
    gems_level = max((p["level"] for p in counted), default=None)
    links = chain(engine, config, groups, main, skill if main else None, base, levels, asc)
    parts += links
    counted += [p for p in links if p["core"] and p["level"]]
    level = max((p["level"] for p in counted), default=None)
    for p in parts:
        p["decisive"] = p in counted and p["level"] == level
    order = {"skill": 0, "source": 1, "spirit": 2, "buff": 3, "support": 4, "unique": 5}
    parts.sort(key=lambda p: (not p["core"], order[p["kind"]], -(p.get("dps") or 0)))
    return {"level": level, "stage": stage_of(level), "parts": parts, "trade": trade,
            "mainDps": base.get("CombinedDPS", 0), "early": _early(engine, config, base, links, gems_level, level)}


def _early(engine, config: dict, base: dict, links: list[dict], at: int | None, level: int | None) -> dict | None:
    """Starting with the build's own gems before what they stand on is there: from `at`, the level its gems can be
    had, the share of the build's damage it deals without the sources, and the buffs that cannot be up yet (their
    gem not there, or the Spirit for them not)."""
    if not at or not level or at >= level or not base.get("CombinedDPS"):
        return None
    spirit = next((p for p in links if p["kind"] == "spirit"), None)
    short = spirit is not None and (spirit["level"] or 0) > at
    cfg = dict(config)
    without = []
    for p in links:
        late = not p["level"] or p["level"] > at or (short and p.get("spirit"))
        if p["kind"] == "source" and late:
            var, off = CHAIN_CONFIG[p["mechanic"]]
            cfg[var] = off
            without.append(p["name"])
        elif p["kind"] == "buff" and late:
            without.append(p["name"])
    late_buffs = {p["group"] for p in links if p["kind"] == "buff" and p["name"] in without}
    off = [(g["index"], x["index"]) for g in engine.skill_groups() if g["index"] in late_buffs for x in g["gems"]]
    out = engine.what_if(config=cfg, disable_gems=off)
    return {"level": at, "dps": out.get("CombinedDPS", 0) / base["CombinedDPS"] * 100, "without": without}


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
