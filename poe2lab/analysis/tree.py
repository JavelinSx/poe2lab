"""Passive tree: where the next points pay most, which allocated branches pay least, and a search that trades the
second for the first.

For a player who does not copy a guide node for node: every notable or keystone within reach is priced by the
whole path PoB would take to it (travel nodes included) and ranked by value per point, with the same weighing as
the stat ranking (goal mode, weaker damage types count more). Allocated branches are priced by what removing them
(and everything only reachable through them) would cost - cheap ones are respec candidates."""
import random
import re

from .fit import build_topics, fit
from .gradients import metric_changes
from .report import defence_weights, score
from .threats import MapProfile, survivable_hits

_ATTRIBUTE = re.compile(r"to (Strength|Dexterity|Intelligence|all Attributes)\b")


class _Change:
    """Adapter so report.score() can weigh a node change like a stat gradient."""

    def __init__(self, one: dict):
        self.one = one


def _value(changes: dict, mode: str, weights: dict) -> float:
    return score(_Change(changes), mode, weights)


# a notable whose own share of its path's value is below this is not for the build: only the road to it pays
# (PoB sees its conditions unmet - no ignite, no shock, another weapon...)
ROAD_ONLY_SHARE = 0.1


def growth_options(engine, cfg: dict, mode: str, weights: dict, max_points: int, own: bool = True) -> list[dict]:
    """Reachable notables and keystones priced by their whole path, best value per point first. With `own`, also
    what the notable itself adds (the path without it priced too): `roadOnly` when the travel nodes do all the
    work - the notable's name would then recommend something the build gets nothing from."""
    base = engine.what_if(config=cfg)
    out = []
    for t in engine.tree_reach(max_points):
        changes = metric_changes(engine.what_if(config=cfg, add_nodes=t["path"]), base)
        value = _value(changes, mode, weights)
        own_value = value
        if own and len(t["path"]) > 1:
            road = [n for n in t["path"] if n != t["id"]]
            own_value = value - _value(metric_changes(engine.what_if(config=cfg, add_nodes=road), base), mode, weights)
        out.append({"id": t["id"], "name": t["name"], "type": t["type"], "points": len(t["path"]), "path": t["path"],
                    "via": [n for nid, n in zip(t["path"], t["pathNames"]) if nid != t["id"] and n],
                    "stats": t["stats"], "changes": changes, "value": value, "perPoint": value / len(t["path"]),
                    "own": own_value, "ownShare": own_value / value if value > 0 else 0.0,
                    "roadOnly": own and value > 0 and own_value < ROAD_ONLY_SHARE * value})
    return sorted(out, key=lambda g: -g["perPoint"])


def branch_options(engine, cfg: dict, mode: str, weights: dict) -> list[dict]:
    """Allocated branches priced by what removing them would cost, cheapest per point first."""
    base = engine.what_if(config=cfg)
    out = []
    for b in engine.tree_branches():
        changes = metric_changes(engine.what_if(config=cfg, remove_nodes=b["depends"]), base)
        loss = -_value(changes, mode, weights)  # what the build gives up
        kind = ("attributes" if any(_ATTRIBUTE.search(line) for line in b["stats"])
                else "unseen" if all(abs(v) < 0.05 for v in changes.values()) else "value")
        out.append({"id": b["id"], "name": b["name"], "type": b["type"], "points": len(b["depends"]),
                    "with": b.get("dependNames", []), "stats": b["stats"], "changes": changes, "loss": loss,
                    "lossPerPoint": loss / len(b["depends"]), "kind": kind})
    return sorted(out, key=lambda b: b["lossPerPoint"])


def analyse(engine, profile: MapProfile, mode: str = "balanced", max_points: int = 6, top: int = 15) -> dict:
    cfg = profile.config()
    weights = defence_weights(survivable_hits(engine, profile))
    options = growth_options(engine, cfg, mode, weights, max_points)
    # how each node's topics meet the build's (damage, mechanics, defences, skills, weapons): the reason a node
    # worth nothing is either off-build or on-build but outside what PoB models
    have = build_topics(engine, engine.what_if(config=cfg))
    for g in options:
        g["fit"] = fit(g["stats"], have)
    growth = [g for g in options if not g["roadOnly"]]
    road_only = [g for g in options if g["roadOnly"]]
    for g in road_only:
        f = g["fit"]
        g["verdict"] = "offBuild" if f["misses"] else "onBuild" if f["fits"] else "unknown"
    road_only.sort(key=lambda g: ({"onBuild": 0, "unknown": 1, "offBuild": 2}[g["verdict"]], -g["perPoint"]))
    branches = branch_options(engine, cfg, mode, weights)
    # A branch whose points are worth less than the best growth option per point is a respec candidate - unless
    # PoB sees no effect at all (utility PoB does not model: warcry speed, Rage on hit...) or it holds attributes
    # (their worth is gem requirements, which PoB does not turn into numbers). Those are listed apart, to check.
    best_growth = growth[0]["perPoint"] if growth else 0.0
    low = [b for b in branches if b["kind"] == "value" and b["lossPerPoint"] < best_growth]
    return {"mode": mode, "maxPoints": max_points, "growth": growth[:top], "roadOnly": road_only[:top * 2],
            "buildTopics": sorted(have), "respec": low[:top],
            "unseen": [b for b in branches if b["kind"] == "unseen"],
            "attributes": [b for b in branches if b["kind"] == "attributes"],
            "allocated": len(branches), "bestGrowthPerPoint": best_growth}


def optimize(engine, profile: MapProfile, mode: str, budget: int, seed: int | None = None, rounds: int = 8,
             max_points: int = 5, pick_from: int = 3) -> dict:
    """Trade weak branches for strong notables while the goal's total improves, within `budget` points.

    Each round removes one of the `pick_from` cheapest branches (picked at random - so every run can find a
    different tree), spends the freed points on the best value per point, and keeps the trade only if the build's
    total for the goal went up. Branches PoB sees no effect of and attribute nodes are never removed: their worth
    is not in PoB's numbers. Free points (budget above what is allocated) are spent first."""
    rng = random.Random(seed)
    cfg = profile.config()
    weights = defence_weights(survivable_hits(engine, profile))
    start = engine.what_if(config=cfg)

    def total() -> float:
        return _value(metric_changes(engine.what_if(config=cfg), start), mode, weights)

    def spend() -> list[str]:
        added = []
        while (free := budget - engine.tree_points()) > 0:
            options = [g for g in growth_options(engine, cfg, mode, weights, min(max_points, free), own=False)
                       if g["points"] <= free and g["perPoint"] > 0]
            if not options:
                break
            added += engine.tree_add(options[0]["id"])
        return added

    steps, tried = [], set()
    added = spend()
    current = total()
    if added:
        steps.append({"removed": [], "added": added, "total": current})
    for _ in range(rounds):
        weak = [b for b in branch_options(engine, cfg, mode, weights) if b["kind"] == "value" and b["id"] not in tried]
        if not weak:
            break
        branch = rng.choice(weak[:pick_from])
        engine.tree_snapshot("optimize-try")
        removed = engine.tree_remove(branch["id"])
        added = spend()
        new = total()
        if new > current + 0.05:
            current = new
            steps.append({"removed": removed, "added": added, "total": new})
        else:
            engine.tree_restore("optimize-try")
            tried.add(branch["id"])
    return {"steps": steps, "total": current, "changes": metric_changes(engine.what_if(config=cfg), start)}


ASCENDANCY_POINTS = 8  # four trials of ascension, two points each


def ascendancy(engine, profile: MapProfile, mode: str = "balanced") -> dict:
    """The build's ascendancy: its allocated notables, and each notable not yet taken priced by PoB on the build
    (with the path to it inside the ascendancy), best first. With every point spent, taking one means giving
    another up - the value says whether a swap is worth it."""
    cfg = profile.config()
    weights = defence_weights(survivable_hits(engine, profile))
    graph = engine.tree_graph()
    base = engine.what_if(config=cfg)
    options = []
    for t in engine.ascendancy_reach():
        changes = metric_changes(engine.what_if(config=cfg, add_nodes=t["path"]), base)
        value = _value(changes, mode, weights)
        options.append({"id": t["id"], "name": t["name"], "points": len(t["path"]), "stats": t["stats"], "path": t["path"],
                        "via": [n for nid, n in zip(t["path"], t["pathNames"]) if nid != t["id"] and n],
                        "changes": changes, "value": value, "perPoint": value / len(t["path"])})
    have = build_topics(engine, base)
    for o in options:
        o["fit"] = fit(o["stats"], have)  # PoB may not see a node's effect: its topics still tell if it is the build's
    options.sort(key=lambda o: -o["value"])
    taken = [{"id": n["id"], "name": n["name"], "stats": n["stats"]} for n in graph["nodes"]
             if n["asc"] and n["alloc"] and n["type"] == "Notable"]
    return {"ascendancy": graph["ascendancy"], "class": graph["class"], "points": graph["ascendancyPoints"],
            "maxPoints": ASCENDANCY_POINTS, "taken": taken, "options": options}
