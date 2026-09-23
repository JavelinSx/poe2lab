"""Passive tree: where the next points pay most, which allocated branches pay least, and a search that trades the
second for the first.

For a player who does not copy a guide node for node: every notable or keystone within reach is priced by the
whole path PoB would take to it (travel nodes included) and ranked by value per point, with the same weighing as
the stat ranking (goal mode, weaker damage types count more). Allocated branches are priced by what removing them
(and everything only reachable through them) would cost - cheap ones are respec candidates."""
import random
import re

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


def growth_options(engine, cfg: dict, mode: str, weights: dict, max_points: int) -> list[dict]:
    """Reachable notables and keystones priced by their whole path, best value per point first."""
    base = engine.what_if(config=cfg)
    out = []
    for t in engine.tree_reach(max_points):
        changes = metric_changes(engine.what_if(config=cfg, add_nodes=t["path"]), base)
        value = _value(changes, mode, weights)
        out.append({"id": t["id"], "name": t["name"], "type": t["type"], "points": len(t["path"]),
                    "via": [n for nid, n in zip(t["path"], t["pathNames"]) if nid != t["id"] and n],
                    "stats": t["stats"], "changes": changes, "value": value, "perPoint": value / len(t["path"])})
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
    growth = growth_options(engine, cfg, mode, weights, max_points)
    branches = branch_options(engine, cfg, mode, weights)
    # A branch whose points are worth less than the best growth option per point is a respec candidate - unless
    # PoB sees no effect at all (utility PoB does not model: warcry speed, Rage on hit...) or it holds attributes
    # (their worth is gem requirements, which PoB does not turn into numbers). Those are listed apart, to check.
    best_growth = growth[0]["perPoint"] if growth else 0.0
    low = [b for b in branches if b["kind"] == "value" and b["lossPerPoint"] < best_growth]
    return {"mode": mode, "maxPoints": max_points, "growth": growth[:top], "respec": low[:top],
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
            options = [g for g in growth_options(engine, cfg, mode, weights, min(max_points, free))
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
