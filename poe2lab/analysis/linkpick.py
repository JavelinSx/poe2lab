"""Links for levelling, picked by PoB: every skill gem a character of a level can have, with every weapon type that
can use it, its damage worked out on a character made from nothing (poe2lab.newbuild) - then for the best ones the
supports that add the most (up to SUPPORTS, those the level gives), and the skills grouped by what their damage is:
one element (physical, fire, cold, lightning, chaos), one ailment (bleeding, poison, ignite) or minions. Each theme
gets the 2-3 skills that deal the most with one weapon (spells go with any), and a passive tree for its first points:
most on their damage, about DEFENCE_SHARE on defence.

The character is plain: no gear but the weapon (a normal base of the type, the highest the level wears), no tree but
the one made here. A rough comparison of skills on equal terms - what a levelling character would get from them."""
import math
import threading
from concurrent.futures import ThreadPoolExecutor

from .. import newbuild
from .leveling import _gem_level
from .report import defence_weights
from .threats import MapProfile, survivable_hits
from .tree import Pricing, growth_options

SUPPORTS = 5  # supports in a link at most (the game's: a skill gem with five support sockets)
TREE_POINTS = 40  # the tree for the first points
DEFENCE_SHARE = 15 / 40  # of them on defence (the player: about 15 of 40)
SHORTLIST = 6  # skills of a theme given supports (the best by their bare damage)
PACKAGE = 3  # skills in a theme's links at most
THIRD_SHARE = 0.25  # a third skill only if it deals this share of the first's damage
NOT_LINKS = {"Travel", "Movement"}  # a dash or a leap: not what a levelling character's links are built on
AILMENTS = {"bleed": "BleedDPS", "poison": "PoisonDPS", "ignite": "IgniteDPS"}
ELEMENTS = ("Physical", "Fire", "Cold", "Lightning", "Chaos")
WEAPON_SLOT = "Weapon 1"
# a skill's weapon type (PoB's weaponTypes) -> the bases that are it: (base type, subtype)
WEAPON_BASES = {"Staff": ("Staff", "Warstaff"), "Bow": ("Bow", ""), "Crossbow": ("Crossbow", ""), "Spear": ("Spear", ""),
                "Talisman": ("Talisman", ""), "Two Hand Mace": ("Two Hand Mace", ""), "One Hand Mace": ("One Hand Mace", ""),
                "Claw": ("Claw", ""), "Dagger": ("Dagger", ""), "Flail": ("Flail", ""), "One Hand Axe": ("One Hand Axe", ""),
                "One Hand Sword": ("One Hand Sword", ""), "Two Hand Axe": ("Two Hand Axe", ""),
                "Two Hand Sword": ("Two Hand Sword", "")}
SPELL_WEAPON = ("Staff", "")  # a spell's character holds a caster's staff (its plain base adds nothing to spells)
WORKERS = 4


def _base_for(bases: list[dict], kind: tuple[str, str], level: int) -> str | None:
    """The best plain base of a weapon type a character of `level` can wear: the highest level one."""
    fit = [b for b in bases if not b.get("hidden") and b["type"] == kind[0] and (b.get("subType") or "") == kind[1]
           and (b.get("level") or 0) <= level]
    return max(fit, key=lambda b: (b.get("level") or 0, b["name"]))["name"] if fit else None


def theme_of(out: dict) -> str | None:
    """What a skill's damage is: an ailment that deals most of it, else the element of its biggest hit; minions'.
    None: it deals none."""
    total = out.get("CombinedDPS") or 0
    if total <= 0:
        return None
    if out.get("DpsFromMinions"):
        return "minion"
    ail = max(AILMENTS, key=lambda k: out.get(AILMENTS[k]) or 0)
    if (out.get(AILMENTS[ail]) or 0) >= 0.5 * total:
        return ail
    hits = {el: max(out.get(f"{el}HitAverage") or 0, out.get(f"MainHand.{el}HitAverage") or 0) for el in ELEMENTS}
    best = max(hits, key=hits.get)
    return best.lower() if hits[best] > 0 else None


class _Worker:
    """A character of the level made from nothing in its own engine (one per thread): the weapon of the skills it
    tries, and the skills' groups added and taken out again."""

    def __init__(self, xml: str):
        from ..engine import PobEngine
        self.xml = xml
        self.engine = PobEngine()
        self.engine.load_xml(xml, "linkpick")
        self.weapon = None

    def wear(self, base: str | None):
        if base == self.weapon:
            return
        if base:
            self.engine.equip_item(WEAPON_SLOT, f"Rarity: Normal\n{base}")
        else:
            self.engine.clear_slot(WEAPON_SLOT)
        self.weapon = base


def pick(base_engine, level: int, ascendancy_id: str | None = None, workers: int = WORKERS) -> dict:
    """The themes of links for a character of `level` (see the module). `base_engine`: an engine with the build open
    (its class and ascendancy, PoB's data); `ascendancy_id`: another ascendancy (newbuild's id)."""
    return run(inputs(base_engine, level, ascendancy_id), workers)


def inputs(base_engine, level: int, ascendancy_id: str | None = None) -> dict:
    """What the pick needs from the open build's engine (quick: the rest runs in engines of its own, see run)."""
    info = base_engine.info()
    asc = ascendancy_id or next((a["id"] for c in newbuild.classes(base_engine) for a in c["ascendancies"]
                                 if a["name"] == info.get("ascendancy")), None) or next(
        (a["id"] for c in newbuild.classes(base_engine) if c["name"] == info["class"] for a in c["ascendancies"]), None)
    return {"level": level, "xml": newbuild.empty_build(base_engine, asc, level), "catalog": base_engine.gem_catalog(),
            "bases": base_engine.item_bases()}


def run(ctx: dict, workers: int = WORKERS) -> dict:
    """The pick on `inputs`, in `workers` engines side by side."""
    level, xml, catalog, bases = ctx["level"], ctx["xml"], ctx["catalog"], ctx["bases"]
    config = MapProfile.for_level(level).config()
    points = min(TREE_POINTS, max(0, level - 1))
    defence = round(points * DEFENCE_SHARE)

    # every skill the level gives with every weapon type that can use it (a spell once, with a caster's staff)
    weapons = {w: _base_for(bases, kind, level) for w, kind in WEAPON_BASES.items()}
    spell_base = _base_for(bases, SPELL_WEAPON, level)
    tries = []
    for g in catalog:
        if g["support"] or (_gem_level(g) or 99) > level or set(g["types"]) & NOT_LINKS:
            continue
        kinds = [w for w in g["weapons"] if weapons.get(w)]
        if not g["weapons"]:
            tries.append((None, spell_base, g))
        tries += [(w, weapons[w], g) for w in kinds]
    supports = [g for g in catalog if g["support"] and (_gem_level(g) or 99) <= level]
    support_ids = {g["id"] for g in supports}
    tries.sort(key=lambda x: (x[1] or "", x[2]["name"]))  # by weapon: a worker swaps it seldom

    local = threading.local()
    made: list[_Worker] = []
    made_lock = threading.Lock()

    def worker() -> _Worker:
        if getattr(local, "w", None) is None:
            local.w = _Worker(xml)
            with made_lock:
                made.append(local.w)
        return local.w

    def bare(t):
        weapon, base, g = t
        w = worker()
        e = w.engine
        try:
            w.wear(base)
            lv = e.gem_level_at([g["id"]], level).get(g["id"], 1)
            group = e.set_gem(0, None, g["id"], level=lv)
        except Exception:  # noqa: BLE001 - a gem PoB cannot socket here: not a candidate
            return {"theme": None, "dps": 0}
        try:
            e.set_main_skill(group, 1)
            out = e.what_if(config=config)
            return {"weapon": weapon, "base": base, "gem": g, "level": lv, "theme": theme_of(out),
                    "dps": out.get("CombinedDPS") or 0.0}
        finally:
            _drop(e, group)

    def linked(row):
        """The supports that add the most to the skill, one at a time (one per family), up to SUPPORTS."""
        w = worker()
        w.wear(row["base"])
        e = w.engine
        group = e.set_gem(0, None, row["gem"]["id"], level=row["level"])
        chosen = []
        try:
            e.set_main_skill(group, 1)
            for _ in range(SUPPORTS):
                cands = [c["id"] for c in e.support_candidates(group) if c["id"] in support_ids]
                if not cands:
                    break
                gains = e.support_gains(group, cands, config, measure_group=group)
                base_dps = gains["base"]["dps"] or 0
                best = max(cands, key=lambda i: (gains.get(i) or {}).get("dps", 0))
                if (gains.get(best) or {}).get("dps", 0) <= base_dps * 1.005:
                    break
                lv = e.gem_level_at([best], level).get(best, 1)
                e.set_gem(group, None, best, level=lv)
                chosen.append(best)
            e.set_main_skill(group, 1)
            out = e.what_if(config=config)
            names = {g["id"]: g["name"] for g in supports}
            return row | {"supports": [names[i] for i in chosen], "supportIds": chosen,
                          "dps": out.get("CombinedDPS") or 0.0, "bare": row["dps"]}
        finally:
            _drop(e, group)

    with ThreadPoolExecutor(max(1, workers)) as ex:
        rows = [r for r in ex.map(bare, tries) if r["theme"] and r["dps"] > 0]
        # the best of each theme by their bare damage, given supports
        short = []
        for theme in sorted({r["theme"] for r in rows}):
            short += sorted((r for r in rows if r["theme"] == theme), key=lambda r: -r["dps"])[:SHORTLIST]
        linked_rows = list(ex.map(linked, short))
        themes = [_package(theme, [r for r in linked_rows if r["theme"] == theme])
                  for theme in sorted({r["theme"] for r in linked_rows})]
        themes = [t for t in themes if t]
        trees = list(ex.map(lambda t: _tree(worker(), t, level, config, points, defence), themes))
    for w in made:
        w.engine = None  # the engines go (a few hundred MB each)
    for t, tree in zip(themes, trees):
        t["tree"] = tree
        for s in t["skills"]:
            s["dpsTree"] = tree["dps"].get(s["name"], s["dps"])
        t["score"] = sum(s["dpsTree"] for s in t["skills"])
    themes.sort(key=lambda t: -t["score"])
    return {"level": level, "points": points, "defence": defence, "tried": len(tries), "themes": themes}


def _drop(e, group: int):
    """The tried skill's group out again, every gem of it (the last one takes the group)."""
    n = len(next((g["gems"] for g in e.skill_groups() if g["index"] == group), []))
    for i in range(n, 0, -1):
        e.remove_gem(group, i)


def _package(theme: str, rows: list[dict]) -> dict | None:
    """The theme's links: for each weapon type the skills it can use (spells with any), the best few; the weapon
    whose skills deal the most."""
    best = None
    for weapon in {r["weapon"] for r in rows if r["weapon"]} | {None}:
        fit = sorted((r for r in rows if r["weapon"] in (weapon, None)), key=lambda r: -r["dps"])
        seen, take = set(), []
        for r in fit:
            if r["gem"]["name"] in seen:
                continue
            if take and len(take) >= 2 and r["dps"] < THIRD_SHARE * take[0]["dps"]:
                break
            seen.add(r["gem"]["name"])
            take.append(r)
            if len(take) >= PACKAGE:
                break
        score = sum(r["dps"] * w for r, w in zip(take, (1.0, 0.5, 0.25)))
        if take and (best is None or score > best[0]):
            best = (score, weapon, take)
    if best is None:
        return None
    _, weapon, take = best
    base = next((r["base"] for r in take if r["weapon"] == weapon and weapon), None) or take[0]["base"]
    return {"theme": theme, "weapon": {"type": weapon, "base": base},
            "skills": [{"name": r["gem"]["name"], "id": r["gem"]["id"], "level": r["level"], "supports": r["supports"],
                        "supportIds": r["supportIds"], "dps": round(r["dps"]), "bare": round(r["bare"])} for r in take]}


def _tree(w: _Worker, theme: dict, level: int, config: dict, points: int, defence: int) -> dict:
    """The theme's character (its weapon, its links) with its first passive points spent: on its skills' damage
    (the skills weighed as they deal it), then `defence` of them on defence. Its passives, and each skill's damage."""
    e = w.engine
    e.load_xml(w.xml, "linkpick-tree")
    w.weapon = None
    w.wear(theme["weapon"]["base"])
    groups = []
    for s in theme["skills"]:
        group = e.set_gem(0, None, s["id"], level=s["level"])
        for sid in s["supportIds"]:
            e.set_gem(group, None, sid, level=e.gem_level_at([sid], level).get(sid, 1))
        groups.append((s["name"], group))
    e.set_damage_mix([{"group": g, "index": 1, "coef": 1.0} for _, g in groups])
    profile = MapProfile.for_level(level)
    weights = defence_weights(survivable_hits(e, profile))
    start = e.tree_points()
    damage = _spend_to(e, profile, "only-damage", weights, lambda: start + points - defence - e.tree_points())
    guard = _spend_to(e, profile, "only-defence", weights, lambda: start + points - e.tree_points())
    e.set_damage_mix(None)
    dps = {}
    for name, g in groups:
        dps[name] = round(e.what_if(config=config, main_socket_group=g).get("CombinedDPS") or 0)
    return {"damage": damage, "defence": guard, "points": e.tree_points() - start, "dps": dps}



def _spend_to(e, profile, mode: str, weights: dict, free, rounds: int = 40) -> list[dict]:
    """Free points (`free()`: how many now) spent one notable at a time on the best growth per point for `mode`
    (poe2lab.analysis.tree's way): each notable taken, with its path, in the order taken."""
    taken = []
    for _ in range(rounds):
        points = free()
        if points <= 0:
            break
        options = [g for g in growth_options(e, Pricing(e, profile), mode, weights, min(5, points), own=False)
                   if g["points"] <= points and g["perPoint"] > 0]
        if not options:
            break
        best = options[0]
        e.tree_add(best["id"])
        taken.append({"id": best["id"], "name": best["name"], "type": best["type"], "points": best["points"]})
    return taken
