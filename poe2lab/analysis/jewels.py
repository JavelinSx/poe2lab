"""What a jewel in the tree does there, beyond its own lines. The lines are on the item; what they mean on this tree
is not: a timeless jewel's conqueror swaps the keystones in its radius (PoB knows for which) and the notables (PoB
does not: it has no seed data for PoE2 yet), From Nothing lets the nodes around its keystone be taken without a path
to them, a Time-Lost jewel adds to every small or notable passive in its radius. Each answer comes from PoB's tree
(poe2lab.engine.PobEngine.jewel_effects) - the nodes the build has taken there - so it holds for any build."""
import re

# the conqueror is named in the jewel's line: "Remembrancing 3876 songworthy deeds by the line of Vorana"
CONQUEROR = re.compile(r"(?:by the line of|in tribute to) (\w+)", re.I)
# Time-Lost and other radius jewels: what each passive of a kind in the radius gets
GRANT = re.compile(r"^(Small|Notable|Attribute) Passive Skills in Radius also grant (.+)$", re.I)
EFFECT = re.compile(r"^(\d+)% increased Effect of (Small|Notable) Passive Skills in Radius$", re.I)
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _kind_of(node: dict) -> str:
    if node["type"] == "Normal":
        return "attribute" if node.get("attribute") else "small"
    return node["type"].lower()


def _label(node: dict) -> str:
    """A node by its name; an attribute node by the attribute chosen in it ("Strength")."""
    return node["now"] if node.get("attribute") else node["name"]


def _times(stat: str, count: int) -> str:
    """A stat given `count` times: its numbers multiplied ("1% increased X" x 5 -> "5% increased X")."""
    def mul(m):
        v = float(m.group(0)) * count
        return str(int(v)) if v == int(v) else f"{v:.1f}"
    return NUMBER.sub(mul, stat)


def describe(item: dict, effect: dict | None) -> dict | None:
    """What the jewel does on this tree, or None when its lines say everything (a jewel without a radius)."""
    if not effect:
        return None
    lines = [m["line"] for m in (item.get("implicit") or []) + (item.get("explicit") or [])]
    nodes = effect.get("nodes") or []
    out = {"radius": effect.get("radius") or None}
    if effect.get("conqueror"):
        name = next((m.group(1) for m in map(CONQUEROR.search, lines) if m), "")
        out |= {"kind": "timeless", "conqueror": effect["conqueror"] | {"name": name},
                # what PoB swaps (keystones): the name on the tree, the conqueror's passive and its lines
                "replaced": [{"name": n["name"], "now": n["now"], "type": n["type"], "lines": n["lines"]}
                             for n in nodes if n["conquered"] and n["type"] in ("Keystone", "Notable") and n["now"] != n["name"]],
                # the notables the conqueror changes into its own, which PoB cannot tell
                "unknown": [n["name"] for n in nodes if n["conquered"] and n["type"] == "Notable" and n["now"] == n["name"]],
                "small": sum(1 for n in nodes if n["type"] == "Normal")}
        return out
    if effect.get("keystone"):  # From Nothing: the nodes around its keystone, taken without a path
        return out | {"kind": "fromNothing", "keystone": effect["keystone"],
                      "reached": [{"name": _label(n), "type": _kind_of(n)} for n in nodes]}
    counts = {}
    for n in nodes:
        counts[_kind_of(n)] = counts.get(_kind_of(n), 0) + 1
    grants = []
    for line in lines:
        m = GRANT.match(line)
        if m:
            kind, stat = m.group(1).lower(), m.group(2)
            grants.append({"line": line, "kind": kind, "count": counts.get(kind, 0), "total": _times(stat, counts.get(kind, 0))})
            continue
        m = EFFECT.match(line)
        if m:
            kind = m.group(2).lower()
            grants.append({"line": line, "kind": kind, "count": counts.get(kind, 0), "total": None})
    if grants:
        return out | {"kind": "radiusMods", "grants": grants,
                      "reached": [{"name": _label(n), "type": _kind_of(n)} for n in nodes if n["type"] in ("Notable", "Keystone")]}
    if effect.get("leap"):  # nodes in the radius taken without a path
        return out | {"kind": "leap", "reached": [{"name": _label(n), "type": _kind_of(n)} for n in nodes]}
    if effect.get("radius") and nodes:
        return out | {"kind": "radius", "reached": [{"name": _label(n), "type": _kind_of(n)} for n in nodes
                                                    if n["type"] in ("Notable", "Keystone")], "counts": counts}
    return None
