"""Does a passive fit the build: the topics its lines speak of (damage types, ailments and mechanics, defences,
skill kinds, weapons) against what the build has - its skills and gems, their mechanics, the weapons it holds and
the defences it really stacks.

PoB prices every node on the build, so a node PoB values fits it by construction. This matters where PoB sees
nothing: a notable worth 0 may be off-build (it wants ignite, the build never ignites) or on-build but outside PoB's
model (slam aftershocks, warcry effects, stun build-up for a slam build) - the second is worth a look, the first
is not."""
import re

from .skills import mechanics_of

# (topic, group, pattern on the node's lines, lower-cased)
TOPICS = [
    ("fire", "damage", r"\bfire\b"), ("cold", "damage", r"\bcold\b"), ("lightning", "damage", r"\blightning\b"),
    ("chaos", "damage", r"\bchaos damage\b"), ("physical", "damage", r"\bphysical damage\b"),
    ("elemental", "damage", r"\belemental damage\b"),
    ("ignite", "mechanic", r"\bignit"), ("shock", "mechanic", r"\bshock"), ("freeze", "mechanic", r"\bfreez|\bchill"),
    ("bleed", "mechanic", r"\bbleed"), ("poison", "mechanic", r"\bpoison"), ("impale", "mechanic", r"\bimpal"),
    ("armour_break", "mechanic", r"break\w* armour|armour break|fully broken"),
    ("stun", "mechanic", r"\bstun|\bdaze"), ("rage", "mechanic", r"\brage\b"), ("glory", "mechanic", r"\bglory\b"),
    ("combo", "mechanic", r"\bcombo\b"), ("exposure", "mechanic", r"\bexposure\b"),
    ("armour", "defence", r"(?<!break )\barmour\b(?! break)"), ("evasion", "defence", r"\bevasion\b|\bevade"),
    ("energy_shield", "defence", r"\benergy shield\b"), ("block", "defence", r"\bblock"),
    ("thorns", "defence", r"\bthorns\b"),
    ("attack", "skill", r"\battacks?\b"), ("spell", "skill", r"\bspells?\b"), ("melee", "skill", r"\bmelee\b"),
    ("projectile", "skill", r"\bprojectiles?\b"), ("minion", "skill", r"\bminions?\b"),
    ("totem", "skill", r"\btotems?\b"), ("warcry", "skill", r"\bwarcr|\bcr(?:y|ies)\b"),
    ("slam", "skill", r"\bslams?\b|\baftershock"), ("shapeshift", "skill", r"shapeshift|\bbear\b|\bwyvern\b|\bwolf\b"),
    ("curse", "skill", r"\bcurses?\b"), ("mark", "skill", r"\bmarks?\b"), ("herald", "skill", r"\bheralds?\b"),
    ("mace", "weapon", r"\bmaces?\b"), ("axe", "weapon", r"\baxes?\b"), ("sword", "weapon", r"\bswords?\b"),
    ("bow", "weapon", r"\bbows?\b"), ("crossbow", "weapon", r"\bcrossbows?\b"), ("spear", "weapon", r"\bspears?\b"),
    ("quarterstaff", "weapon", r"\bquarterstaff|\bquarterstaves\b"), ("staff", "weapon", r"(?<!quarter)\bstaff\b|\bstaves\b"),
    ("wand", "weapon", r"\bwands?\b"), ("sceptre", "weapon", r"\bsceptres?\b"), ("dagger", "weapon", r"\bdaggers?\b"),
    ("claw", "weapon", r"\bclaws?\b"), ("flail", "weapon", r"\bflails?\b"), ("shield", "weapon", r"(?<!energy )\bshields?\b"),
    ("focus", "weapon", r"\bfoci\b|\bfocus\b"), ("talisman", "weapon", r"\btalismans?\b"),
]
_PATTERNS = [(t, g, re.compile(p)) for t, g, p in TOPICS]

# skill types (PoB) and gem tags that make a topic the build's
_SKILL_TYPES = {"Attack": "attack", "Spell": "spell", "Melee": "melee", "Projectile": "projectile",
                "Minion": "minion", "Totem": "totem", "Warcry": "warcry", "Slam": "slam", "Shapeshift": "shapeshift",
                "Curse": "curse", "Mark": "mark", "Herald": "herald"}
_GEM_TAGS = {"fire": "fire", "cold": "cold", "lightning": "lightning", "chaos": "chaos", "physical": "physical",
             "attack": "attack", "spell": "spell", "melee": "melee", "projectile": "projectile", "minion": "minion",
             "totem": "totem", "warcry": "warcry", "slam": "slam", "curse": "curse", "mark": "mark", "herald": "herald"}
_MECHANICS = {"ignite": "ignite", "shock": "shock", "freeze": "freeze", "bleed": "bleed", "poison": "poison",
              "impale": "impale", "armour_break": "armour_break", "rage": "rage", "glory": "glory", "combo": "combo",
              "heavy_stun": "stun"}
_WEAPONS = {"One Hand Mace": ["mace"], "Two Hand Mace": ["mace"], "One Hand Axe": ["axe"], "Two Hand Axe": ["axe"],
            "One Hand Sword": ["sword"], "Two Hand Sword": ["sword"], "Bow": ["bow"], "Crossbow": ["crossbow"],
            "Spear": ["spear"], "Warstaff": ["quarterstaff"], "Staff": ["staff"], "Wand": ["wand"],
            "Sceptre": ["sceptre"], "Dagger": ["dagger"], "Claw": ["claw"], "Flail": ["flail"],
            "Shield": ["shield", "block"], "Buckler": ["shield", "block"], "Focus": ["focus"],
            "Talisman": ["talisman", "shapeshift"], "Quiver": ["bow"]}


def node_topics(lines: list[str]) -> list[tuple[str, str]]:
    """(topic, group) the node's lines speak of."""
    text = " ".join(lines).lower()
    return [(t, g) for t, g, p in _PATTERNS if p.search(text)]


def build_topics(engine, output: dict) -> set[str]:
    """What the build has: its enabled skills' types and gem tags, the mechanics its gems create or use, the weapons
    it holds and the defences it really stacks (armour / evasion / energy shield near the largest of the three -
    energy shield counted x4, its numbers run smaller)."""
    have = set()
    for g in engine.skill_groups():
        if not g.get("enabled", True):
            continue
        for a in g.get("actives", []):
            have |= {_SKILL_TYPES[t] for t in a.get("types", []) if t in _SKILL_TYPES}
        for gem in g.get("gems", []):
            if not gem.get("enabled", True):
                continue
            have |= {_GEM_TAGS[t] for t in gem.get("tags", []) if t in _GEM_TAGS}
            m = mechanics_of(gem)
            have |= {_MECHANICS[k] for k in m["creates"] + m["uses"] if k in _MECHANICS}
            text = " ".join([gem.get("description", ""), *gem.get("stats", [])]).lower()
            if "exposure" in text:
                have.add("exposure")
    if have & {"melee", "slam"}:
        have.add("stun")  # every melee hit builds stun
    for item in engine.equipped_item_details():
        if "Swap" in item["slot"]:
            continue
        have |= set(_WEAPONS.get(item["type"], []))
    pools = {"armour": output.get("Armour", 0) or 0, "evasion": output.get("Evasion", 0) or 0,
             "energy_shield": 4 * (output.get("EnergyShield", 0) or 0)}
    top = max(pools.values())
    have |= {k for k, v in pools.items() if top and v >= 0.3 * top}
    if (output.get("BlockChance") or output.get("EffectiveBlockChance") or 0) > 0:
        have.add("block")
    if have & {"fire", "cold", "lightning"}:
        have.add("elemental")
    return have


def fit(lines: list[str], have: set[str]) -> dict:
    """{"fits": topics of the node the build has, "misses": topics it lacks} - damage, mechanics, defences, skills
    and weapons; generic lines (life, attributes, speed) name no topic."""
    fits, misses = [], []
    for topic, _group in node_topics(lines):
        (fits if topic in have else misses).append(topic)
    return {"fits": fits, "misses": misses}
