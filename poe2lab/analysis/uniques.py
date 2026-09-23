"""Which unique items of the whole game go with this build's skills - found the way a player would: the mechanics
the build's skills create and use (a unique that spends the Rage your skills build, one that works on the Frozen
enemies your skills freeze), the kinds of skills it has (warcries, slams, spells, minions...), its damage types and
the game terms they share; then each candidate is worn in PoB to see what it is worth, and the lines PoB cannot
read are marked, since that part of the unique is not in the number."""
import re

from .. import keywords as kw
from .gradients import metric_changes
from .skills import MECHANICS, TYPE_RU, mechanics_of

# gear slots a unique of that item type goes into (flasks, charms and jewels are left out)
SLOTS = {"Helmet": ["Helmet"], "Body Armour": ["Body Armour"], "Gloves": ["Gloves"], "Boots": ["Boots"],
         "Amulet": ["Amulet"], "Ring": ["Ring 1", "Ring 2"], "Belt": ["Belt"], "Shield": ["Weapon 2"],
         "Focus": ["Weapon 2"], "Quiver": ["Weapon 2"]}
WEAPON_SLOTS = ["Weapon 1", "Weapon 1 Swap"]
# kinds of skills a unique can be about, and how its lines name them
SKILL_KINDS = {
    "Warcry": r"warcr(?:y|ies)", "Slam": r"\bslams?\b", "Strike": r"\bstrikes?\b", "Spell": r"\bspells?\b",
    "Minion": r"\bminions?\b", "Totem": r"\btotems?\b", "Mark": r"\bmarks?\b|\bmarked\b",
    "Projectile": r"\bprojectiles?\b", "Shapeshift": r"shapeshift|\bbear form\b|\bwyvern\b|\bwolf form\b",
    "Herald": r"\bheralds?\b", "Aura": r"\bauras?\b", "Channel": r"\bchannell?ing\b", "Trap": r"\btraps?\b",
    "Nova": r"\bnova\b", "Jumping": r"\bleap|\bjump", "Cooldown": r"\bcooldown\b",
}
DAMAGE = {"cold": r"\bcold damage\b", "fire": r"\bfire damage\b", "lightning": r"\blightning damage\b",
          "chaos": r"\bchaos damage\b", "physical": r"\bphysical damage\b"}
EVALUATE = 60  # most related candidates worn in PoB
SHOW = 24
# How a change counts in the plus/minus balance: damage and effective HP fully, each damage type's survivable hit
# partly (five of them), recovery least (its percentages swing wildly on small numbers).
BALANCE_WEIGHTS = {"dps": 1.0, "ehp": 1.0, "phys_hit": 0.4, "fire_hit": 0.4, "cold_hit": 0.4, "lightning_hit": 0.4,
                   "chaos_hit": 0.4, "recovery": 0.3}
MIN_GAIN = 3.0  # weighted % points of plus a unique must bring
GAIN_OVER_LOSS = 2.0  # and at least this many times its minus


def balance(changes: dict) -> tuple[float, float]:
    """(plus, minus) of wearing it: weighted sums of the gains and of the losses."""
    plus = sum(w * max(changes.get(k, 0), 0) for k, w in BALANCE_WEIGHTS.items())
    minus = sum(w * max(-changes.get(k, 0), 0) for k, w in BALANCE_WEIGHTS.items())
    return plus, minus


def build_traits(view: dict) -> dict:
    """What the build's enabled skills create, use, are (skill types), deal (damage types) and talk about."""
    t = {"creates": {}, "uses": {}, "kinds": {}, "damage": set(), "terms": set()}
    for g in view["groups"]:
        if not g["enabled"]:
            continue
        for gem in g["gems"]:
            if not gem["enabled"]:
                continue
            for key in gem["mechanics"]["creates"]:
                t["creates"].setdefault(key, []).append(gem["name"])
            for key in gem["mechanics"]["uses"]:
                t["uses"].setdefault(key, []).append(gem["name"])
            t["terms"].update(gem.get("terms", []))
            if not gem["support"]:
                for kind in gem.get("types", []):
                    if kind in SKILL_KINDS:
                        t["kinds"].setdefault(kind, []).append(gem["name"])
                t["damage"].update(d for d in DAMAGE if d in gem.get("tags", []))
    return t


def relate(unique: dict, traits: dict) -> list[dict]:
    """Why this unique goes with the build: a list of reasons, strongest first."""
    item = {"name": unique["name"], "description": " ".join(unique["lines"]), "support": True}
    mech = mechanics_of(item)
    text = item["description"].lower()
    reasons = []
    for key in mech["uses"]:
        if key in traits["creates"]:
            reasons.append({"kind": "uses", "mechanic": key, "skills": sorted(set(traits["creates"][key])), "weight": 3})
    for key in mech["creates"]:
        if key in traits["uses"]:
            reasons.append({"kind": "creates", "mechanic": key, "skills": sorted(set(traits["uses"][key])), "weight": 3})
    for kind, skills in traits["kinds"].items():
        if re.search(SKILL_KINDS[kind], text):
            reasons.append({"kind": "skillKind", "type": kind, "typeRu": TYPE_RU.get(kind, kind),
                            "skills": sorted(set(skills)), "weight": 2})
    for dmg in traits["damage"]:
        if re.search(DAMAGE[dmg], text):
            reasons.append({"kind": "damage", "type": dmg, "weight": 1})
    shared = [t for t in kw.find(unique["lines"]) if t in traits["terms"]]
    if shared:
        reasons.append({"kind": "terms", "terms": shared[:4], "weight": min(len(shared), 3)})
    return sorted(reasons, key=lambda r: -r["weight"])


def offhand_types(equipped: list[dict]) -> set[str]:
    """What the off-hand can hold with this weapon: the kind already there, a shield or focus next to a one-handed
    weapon, a quiver with a bow. PoB would compute an off-hand next to a two-handed weapon anyway."""
    w1 = next((i for i in equipped if i["slot"] == "Weapon 1"), None)
    w2 = next((i for i in equipped if i["slot"] == "Weapon 2"), None)
    allowed = {w2["type"]} if w2 else set()
    if w1 is None or "two_hand_weapon" not in w1["tags"]:
        allowed |= {"Shield", "Focus"}
    if w1 is not None and w1["type"] == "Bow":
        allowed.add("Quiver")
    return allowed


_catalog: dict = {}


def catalog(engine) -> list[dict]:
    """Every unique of the game data, read once per process (the data does not change while it runs)."""
    if "list" not in _catalog:
        _catalog["list"] = engine.unique_catalog()
    return _catalog["list"]


def _worth(engine, config: dict, unique: dict, slots: list[str], base: dict) -> dict | None:
    """The best slot to wear it in and what it changes there (None if PoB cannot equip it in any)."""
    best = None
    for slot in slots:
        try:
            out = engine.what_if(config=config, replace_item=(slot, unique["raw"]))
        except Exception:  # an item PoB cannot place here
            continue
        changes = metric_changes(out, base)
        if changes.get("dps", 0) <= -95:
            continue  # a weapon the build's skills cannot use
        if slot in WEAPON_SLOTS and all(abs(v) < 0.05 for v in changes.values()):
            continue  # a weapon set the build's skills do not use: wearing it there changes nothing
        score = changes.get("dps", 0) + changes.get("ehp", 0) + 0.5 * max(
            changes.get(k, 0) for k in ("phys_hit", "fire_hit", "cold_hit", "lightning_hit", "chaos_hit"))
        if best is None or score > best["score"]:
            best = {"slot": slot, "changes": changes, "score": score}
    return best


def suggest(engine, config: dict, view: dict, max_level: int | None = None) -> dict:
    """Uniques related to the build's skills, each worn in PoB. `max_level`: only those a character of that level
    can wear (levelling)."""
    traits = build_traits(view)
    worn = {it["name"].split(",")[0] for it in view.get("items", [])}
    equipped = engine.equipped_item_details()
    weapon_types = {i["type"] for i in equipped if i["slot"] in WEAPON_SLOTS}
    offhand = offhand_types(equipped)
    base = engine.what_if(config=config)
    related = []
    for u in catalog(engine):
        if u["name"] in worn or (max_level is not None and u["level"] > max_level):
            continue
        slots = SLOTS.get(u["type"]) or (WEAPON_SLOTS if u["type"] in weapon_types else None)
        if not slots or (slots == ["Weapon 2"] and u["type"] not in offhand):
            continue
        reasons = relate(u, traits)
        if reasons:
            related.append((sum(r["weight"] for r in reasons), u, reasons, slots))
    related.sort(key=lambda x: -x[0])
    out, tried = [], 0
    for weight, u, reasons, slots in related[:EVALUATE]:
        worth = _worth(engine, config, u, slots, base)
        if worth is None:
            continue
        tried += 1
        strong = any(r["kind"] in ("uses", "creates", "skillKind") for r in reasons)
        plus, minus = balance(worth["changes"])
        # PoB sees nothing, but the unique is tied to the skills by a mechanic in lines PoB does not read: its worth
        # is outside the numbers, so it stays (marked); otherwise the plus has to clearly outweigh the minus
        outside_pob = strong and u["unread"] and plus < 0.5 and minus < 0.5
        if not outside_pob and (plus < MIN_GAIN or plus < GAIN_OVER_LOSS * minus):
            continue
        out.append({"name": u["name"], "base": u["base"], "type": u["type"], "level": u["level"],
                    "lines": u["lines"], "unread": u["unread"], "slot": worth["slot"],
                    # PoB's markup in sources: "Drops from unique{Trialmaster} in normal{The Trial of Chaos}"
                    "source": re.sub(r"\w+\{([^}]*)\}", r"\1", u["source"]),
                    "changes": worth["changes"], "reasons": reasons, "relevance": weight,
                    "plus": plus, "minus": minus, "outsidePob": bool(outside_pob),
                    "terms": kw.find(u["lines"])})
    # related first (a mechanic link outweighs a stat bump), then what PoB says it is worth
    out.sort(key=lambda s: (-min(s["relevance"], 6), -(s["plus"] - s["minus"])))
    terms = {t for s in out[:SHOW] for t in s["terms"]}
    return {"suggestions": out[:SHOW], "maxLevel": max_level, "considered": len(related), "tried": tried,
            "outweighed": tried - len(out),
            "mechanics": {m.key: m.name for m in MECHANICS}, "terms": kw.entries(terms)}
