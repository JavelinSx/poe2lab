"""What changed in a build between two loads - after the player re-imported the character with new gear or tree:
characteristics before and after, which slots got another item, which passives and gems came and went."""
from collections import Counter

from .threats import DAMAGE_TYPES, MapProfile
from .versus import STATS, snapshot


def capture(engine, profile: MapProfile) -> dict:
    info = engine.info()
    return {
        "stats": snapshot(engine, profile),
        "class": info["ascendancy"] or info["class"], "level": info["level"],
        "items": {i["slot"]: {"name": i["name"], "base": i["baseName"], "lines": [m["line"] for m in i["explicit"]]}
                  for i in engine.equipped_item_details()},
        "nodes": {n["id"]: n["name"] for n in engine.allocated_nodes()
                  if n["type"] not in ("ClassStart", "AscendClassStart")},
        "gems": Counter(g["name"] for g in engine.gems() if g["enabled"]),
    }


def diff(before: dict, after: dict) -> dict:
    a, b = before["stats"], after["stats"]
    rows = [{"group": g, "key": key, "before": a[key], "after": b[key], "higherBetter": hb} for g, _, key, hb in STATS]
    rows += [{"group": "hits", "key": f"hit_{t}", "before": a[f"hit_{t}"], "after": b[f"hit_{t}"],
              "higherBetter": True} for t in DAMAGE_TYPES]
    items = []
    for slot in sorted(set(before["items"]) | set(after["items"])):
        old, new = before["items"].get(slot), after["items"].get(slot)
        if old != new:
            items.append({"slot": slot, "before": old and old["name"], "after": new and new["name"],
                          "sameItem": bool(old and new and old["name"] == new["name"])})  # same item, other mods
    gone, came = before["gems"] - after["gems"], after["gems"] - before["gems"]
    return {
        "rows": rows,
        "items": items,
        "nodesAdded": sorted(after["nodes"][i] for i in set(after["nodes"]) - set(before["nodes"])),
        "nodesRemoved": sorted(before["nodes"][i] for i in set(before["nodes"]) - set(after["nodes"])),
        "gemsAdded": sorted(came.elements()), "gemsRemoved": sorted(gone.elements()),
        "level": [before["level"], after["level"]],
        "class": [before["class"], after["class"]],
    }
