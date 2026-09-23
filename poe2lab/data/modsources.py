"""Does a mod exist in the game, and where does it come from: item affixes (tiers, item level, item types), runes
and soul cores, uniques, passive tree nodes and ascendancies, base implicits - searched in PoB's game data by text.

An answer to "is there such a mod" that does not depend on what a language model remembers."""
import re

from .moddb import ModDB

_NUM = re.compile(r"\(\s*-?\d+(?:\.\d+)?\s*-\s*-?\d+(?:\.\d+)?\s*\)|[+-]?\d+(?:\.\d+)?%?")
_TAG = re.compile(r"\{[^}]*\}")
_VARIANT = re.compile(r"\{variant:([\d,]+)\}")
_UNIQUE_META = ("Variant:", "Implicits:", "Requires", "League:", "Source:", "LevelReq:", "Sockets:", "Has Alt Variant",
                "Selected Variant", "Radius:", "Limited to:", "Item Level", "Quality:", "Rune:")
LIMIT = 10


def search_text(query: str) -> str:
    """The longest wording between the numbers: '+30% of Armour also applies to Chaos Damage' -> 'of armour also
    applies to chaos damage', which matches every tier and roll."""
    parts = [p.strip(" ,.%+") for p in _NUM.split(query.lower())]
    return max(parts, key=len) if parts else ""


def _unique(raw: str, query: str) -> dict | None:
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return None
    variants = [l.split(":", 1)[1].strip() for l in lines if l.startswith("Variant:")]
    current = len(variants)  # PoB opens a unique on its last variant, which is the current one
    hits = []
    for line in lines[2:]:
        if line.startswith(_UNIQUE_META):
            continue
        m = _VARIANT.search(line)
        if m and current and str(current) not in m.group(1).split(","):
            continue  # a line of an older version of the item
        text = _TAG.sub("", line).strip()
        if query in text.lower():
            hits.append(text)
    return {"name": lines[0], "base": lines[1], "lines": hits} if hits else None


def _item_types(db: ModDB, kinds: list[str]) -> list[str]:
    if "default" in kinds:
        return ["any"]
    tags = set(kinds)
    return sorted({b["type"] for b in db.bases.values() if tags & set(b["tags"])})


def find(engine, db: ModDB, query: str, names: dict | None = None) -> dict:
    q = search_text(query)
    if len(q) < 6:
        raise ValueError("give a distinctive part of the mod text in English, e.g. 'armour also applies to chaos'")
    raw = engine.find_mod_text(q)
    ru = (lambda n: (names or {}).get(n))

    families = {}
    for a in raw["affixes"]:
        families.setdefault((a["set"], a["group"]), []).append(a)
    affixes = []
    for (mod_set, _), tiers in families.items():
        tiers.sort(key=lambda a: a["level"])
        best = tiers[-1]
        affixes.append({"source": {"Item": "affix", "Desecrated": "desecrated affix", "Corruption": "corruption",
                                   "Jewel": "jewel affix", "Charm": "charm affix", "Flask": "flask affix"}[mod_set],
                        "type": best["type"], "tiers": len(tiers), "fromItemLevel": tiers[0]["level"],
                        "bestTier": " / ".join(best["lines"]), "bestTierItemLevel": best["level"],
                        "itemTypes": _item_types(db, best["kinds"])})
    uniques = [u | {"nameRu": ru(u["name"])} for u in (_unique(x["raw"], q) for x in raw["uniques"]) if u]
    passives = {}
    for n in raw["nodes"]:  # the same node in the build's tree and the game's current one: listed once
        key = (n["name"], tuple(n["lines"]))
        if key in passives:
            passives[key]["trees"].append(n["tree"])
            passives[key]["allocated"] |= n["allocated"]
            continue
        asc = n["ascendancy"]
        passives[key] = {"name": n["name"], "nameRu": ru(n["name"]), "lines": n["lines"], "trees": [n["tree"]],
                         "kind": f"ascendancy {asc} ({ru(asc) or asc})" if asc else n["type"].lower(),
                         "allocated": n["allocated"]}
    passives = sorted(passives.values(),
                      key=lambda p: (raw["gameTree"] not in p["trees"], p["kind"] == "normal", p["name"]))
    runes = [{"name": r["name"], "nameRu": ru(r["name"]), "slot": r["slot"], "lines": r["lines"]} for r in raw["runes"]]
    bases = [{"name": b["name"], "nameRu": ru(b["name"]), "type": b["type"], "implicit": b["implicit"]}
             for b in raw["bases"]]
    found = bool(affixes or uniques or passives or runes or bases)
    return {
        "searched": q, "found": found, "buildTree": raw["buildTree"], "gameTree": raw["gameTree"],
        "affixes": affixes[:LIMIT], "runes": runes[:LIMIT], "uniques": uniques[:LIMIT], "passives": passives[:LIMIT],
        "baseImplicits": bases[:LIMIT],
        "counts": {"affixes": len(affixes), "runes": len(runes), "uniques": len(uniques), "passives": len(passives),
                   "baseImplicits": len(bases)},
        "note": None if found else ("not in PoB's game data (affixes, runes, uniques, passive tree, base implicits); "
                                    "this does not prove it is absent from the game - try a shorter wording"),
    }
