"""Passive tree: where the next points pay most, and which allocated branches pay least.

For a player who does not copy a guide node for node: every notable or keystone within reach is priced by the
whole path PoB would take to it (travel nodes included) and ranked by value per point, with the same weighing as
the stat ranking (goal mode, weaker damage types count more). Allocated branches are priced by what removing them
(and everything only reachable through them) would cost - cheap ones are respec candidates."""
import re

from .gradients import metric_changes
from .report import MODES, defence_weights, score
from .threats import MapProfile, survivable_hits


_ATTRIBUTE = re.compile(r"to (Strength|Dexterity|Intelligence|all Attributes)\b")


class _Change:
    """Adapter so report.score() can weigh a node change like a stat gradient."""

    def __init__(self, one: dict):
        self.one = one


def _value(changes: dict, mode: str, weights: dict) -> float:
    return score(_Change(changes), mode, weights)


def analyse(engine, profile: MapProfile, mode: str = "balanced", max_points: int = 6, top: int = 15) -> dict:
    cfg = profile.config()
    weights = defence_weights(survivable_hits(engine, profile))
    base = engine.what_if(config=cfg)

    growth = []
    for t in engine.tree_reach(max_points):
        changes = metric_changes(engine.what_if(config=cfg, add_nodes=t["path"]), base)
        value = _value(changes, mode, weights)
        growth.append({"id": t["id"], "name": t["name"], "type": t["type"], "points": len(t["path"]),
                       "via": [n for nid, n in zip(t["path"], t["pathNames"]) if nid != t["id"] and n], "stats": t["stats"], "changes": changes,
                       "value": value, "perPoint": value / len(t["path"])})
    growth.sort(key=lambda g: -g["perPoint"])

    branches = []
    for b in engine.tree_branches():
        changes = metric_changes(engine.what_if(config=cfg, remove_nodes=b["depends"]), base)
        loss = -_value(changes, mode, weights)  # what the build gives up
        branches.append({"id": b["id"], "name": b["name"], "type": b["type"], "points": len(b["depends"]),
                         "with": b.get("dependNames", []),
                         "stats": b["stats"], "changes": changes, "loss": loss, "lossPerPoint": loss / len(b["depends"])})
    # A branch whose points are worth less than the best growth option per point is a respec candidate - unless
    # PoB sees no effect at all (utility PoB does not model: warcry speed, Rage on hit...) or it holds attributes
    # (their worth is gem requirements, which PoB does not turn into numbers). Those are listed apart, to check.
    best_growth = growth[0]["perPoint"] if growth else 0.0
    low, unseen, attributes = [], [], []
    for b in sorted(branches, key=lambda b: b["lossPerPoint"]):
        if any(_ATTRIBUTE.search(line) for line in b["stats"]):
            attributes.append(b)
        elif all(abs(v) < 0.05 for v in b["changes"].values()):
            unseen.append(b)
        elif b["lossPerPoint"] < best_growth:
            low.append(b)
    return {"mode": mode, "maxPoints": max_points, "growth": growth[:top], "respec": low[:top],
            "unseen": unseen, "attributes": attributes, "allocated": len(branches), "bestGrowthPerPoint": best_growth}
