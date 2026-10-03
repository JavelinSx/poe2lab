"""How to craft the item a slot needs, starting from a white or blue base: candidate strategies played out many
times on the real mod pool of the base, with the chance to succeed, the currency they eat and its price.

The rules are the currencies' own descriptions from the game data (poe2lab.gamedata, currencyitems), e.g. "Orb of
Augmentation: augments a Magic item with a new random modifier", "Omen of Sinistral Exaltation: your next Exalted Orb
will add only prefix modifiers", "Perfect Essence: removes a random modifier and augments a Rare item with a new
guaranteed modifier". Which mods can roll comes from PoB's data (base tags, item level, families); the minimum
modifier level of Greater / Perfect currency (35 / 50) is not in the client files, it comes from public guides.

PoE2 does not ship mod weights (the client's weight columns only say whether a mod can roll). The craft journal
(poe2lab.journal) measured them. In 2646 draws the tiers of a mod roll equally often on armour and jewellery (the top
tier as often as any), while on weapons a tier's weight halves about every 60 mod levels; mod families differ (life,
all resistances ~2.5x the average). That is the default here; weights estimated from the player's own journal replace
it once applied (%APPDATA%/poe2lab/craft_weights.json: {"weapon" | "other": {mod id: weight}}). Chances are
estimates."""
import bisect
import itertools
import json
import math
import os
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .data.moddb import Mod, ModDB

WEIGHTS_FILE = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "poe2lab" / "craft_weights.json"
# minimum modifier level of the better currency grades (timesaver.gg, PoE2 0.5 currency guide)
MIN_LEVEL = {"": 0, "Greater ": 35, "Perfect ": 50}
# and whether a mod whose best tier is below that level can still roll (at any tier) - the guides do not say;
# the craft journal measures both (poe2lab.journal.thresholds) and applied weights carry them
SIDE_LIMIT = {"magic": 1, "rare": 3}  # modifiers per side
# simulated attempts (one base each) per strategy: batches until enough successes for a steady chance, or the cap
ATTEMPTS = 1500
MAX_ATTEMPTS = 15000
ENOUGH_SUCCESSES = 40
MAX_TRIES = 40  # fresh bases a player would burn before giving up on a strategy
GREATER_EXALT = "Omen of Greater Exaltation"  # the next Exalted Orb adds two random modifiers
BONE = {"Weapon": "Jawbone", "Armour": "Rib", "Jewellery": "Collarbone"}
# the bone's grade by the item level: the game's drop levels of Gnawed / Preserved / Ancient bones (25, 61, 75) - their
# descriptions are the same; Ancient for an endgame weapon is what the player uses
BONE_GRADES = ((75, "Ancient"), (61, "Preserved"), (0, "Gnawed"))
FRACTURE = "Fracturing Orb"  # fractures a random modifier on a rare item with at least 4 modifiers, locking it
LIGHT = "Omen of Light"  # the next Orb of Annulment removes only desecrated modifiers
ECHOES = "Omen of Abyssal Echoes"  # the next reveal of desecrated modifiers can reroll the options once
FRACTURE_ACTIONS = 30  # annulments and exalts a player spends on a fractured base before giving up on it


# item classes counted as weapons: their tiers fall with level (measured), the rest's do not
WEAPONS = {"Bow", "Claw", "Crossbow", "Dagger", "Flail", "One Hand Axe", "One Hand Mace", "One Hand Sword", "Sceptre",
           "Spear", "Staff", "Talisman", "Two Hand Axe", "Two Hand Mace", "Two Hand Sword", "Wand"}
WEAPON_HALF_LEVEL = 60  # the journal's fit: 52 levels at 288 weapon draws, 63 at 982


def is_weapon(item_type: str) -> bool:
    return item_type in WEAPONS


def applied(pool: str | None = None) -> dict:
    """The applied journal weights ({} when none), only when they belong to the mod pool `pool`
    (ModDB.fingerprint): after a patch that changed the mods, weights of the old ones are not used."""
    try:
        data = json.loads(WEIGHTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or (pool and data.get("pool") and data["pool"] != pool):
        return {}
    return data


def _weights(kind: str, pool: str | None = None) -> dict[str, float]:
    """The applied journal weights for "weapon" or "other" items ({} when none or of another mod pool); a weight
    that is not a positive number is left out."""
    data = applied(pool).get(kind)
    if not isinstance(data, dict):
        return {}
    return {k: float(v) for k, v in data.items() if isinstance(v, (int, float)) and math.isfinite(v) and v > 0}


def grade_rule(grade: str, pool: str | None = None) -> tuple[int, bool]:
    """(minimum mod level, can mods with no tier that high still roll) for "", "Greater ", "Perfect " currency:
    measured by the craft journal once applied (for this mod pool), else the guide's level and "yes"."""
    data = applied(pool).get("grades")
    rule = (data.get(grade.strip().lower()) if isinstance(data, dict) else None) or {}
    try:
        return int(rule.get("minLevel", MIN_LEVEL[grade])), bool(rule.get("lowFamilies", True))
    except (TypeError, ValueError):
        return MIN_LEVEL[grade], True


def tier_weight(level: int, weapon: bool = False) -> float:
    """A tier's weight without the journal's estimate (measured, see the module's note)."""
    return 0.5 ** (level / WEAPON_HALF_LEVEL) if weapon else 1.0


@dataclass(frozen=True)
class Target:
    """A mod family the item should have, at this tier level or better."""
    group: str
    patterns: tuple
    side: str
    min_level: int
    label: str  # the best tier's line, for the player


@dataclass(frozen=True)
class Unrevealed:
    """A desecrated modifier not revealed yet: it takes a place on its side (the bone's draw decides which), an Orb of
    Annulment can take it, the Fracturing Orb does not touch it (confirmed by the player in game)."""
    type: str
    group: str = "<unrevealed>"
    patterns: tuple = ()
    level: int = 0
    id: str = "unrevealed"


@dataclass
class Item:
    rarity: str = "normal"
    mods: list = field(default_factory=list)  # Mod (or Unrevealed)
    fractured: object = None  # the fractured mod: nothing removes it

    def side(self, kind: str) -> int:
        return sum(1 for m in self.mods if m.type == kind)

    def families(self) -> set:
        return {(m.group, m.patterns) for m in self.mods}


class Pool:
    """The mods that can roll on one base at one item level, with their weights."""

    def __init__(self, db: ModDB, base_tags, item_level: int, sets=("Item",), item_type: str = ""):
        weapon = is_weapon(item_type)
        self.fingerprint = db.fingerprint()
        weights = _weights("weapon" if weapon else "other", self.fingerprint)
        self.mods = [m for m in db.rollable(base_tags, item_level, sets)]
        self.weight = {m.id: float(weights.get(m.id, tier_weight(m.level, weapon))) for m in self.mods}
        self.family_top = {}
        for m in self.mods:
            key = (m.group, m.patterns)
            self.family_top[key] = max(self.family_top.get(key, 0), m.level)
        self.uniform = len(set(self.weight.values())) <= 1
        # (mod, side, family, level, family's best level, weight): what pick() filters, precomputed
        self.rows = [(m, m.type, (m.group, m.patterns), m.level, self.family_top[(m.group, m.patterns)],
                      self.weight[m.id]) for m in self.mods]
        self.cumulative = list(itertools.accumulate(r[5] for r in self.rows))

    def pick(self, item: Item, rng: random.Random, side: str | None = None, min_level: int = 0,
             low_families: bool = True, exclude: set = frozenset()) -> Mod | None:
        """A random new mod for the item: a family it does not have (nor one of `exclude`), on a side with room, not
        below the minimum level - unless no tier of that family reaches it and `low_families` (then the family rolls
        at any tier)."""
        limit = SIDE_LIMIT.get(item.rarity, 3)
        have = item.families() | set(exclude)
        room = {k for k in ("Prefix", "Suffix") if item.side(k) < limit}
        if side:
            room &= {side}
        if not room:
            return None
        # rejection sampling: draw from the whole pool by weight until the mod is allowed - the same distribution as
        # drawing among the allowed ones, without building that list for every orb
        total = self.cumulative[-1] if self.rows else 0
        for _ in range(64):
            if not total:
                break
            r = self.rows[bisect.bisect_right(self.cumulative, rng.random() * total)]
            if r[1] in room and r[2] not in have and (r[3] >= min_level or (low_families and r[4] < min_level)):
                return r[0]
        # few mods allowed (or none): pick among them directly
        options = [r for r in self.rows if r[1] in room and r[2] not in have
                   and (r[3] >= min_level or (low_families and r[4] < min_level))]
        if not options:
            return None
        if self.uniform:
            return rng.choice(options)[0]
        return rng.choices(options, weights=[r[5] for r in options])[0][0]


def hits(item: Item, targets: list[Target]) -> int:
    got = 0
    for t in targets:
        if any(m.group == t.group and m.patterns == t.patterns and m.level >= t.min_level for m in item.mods):
            got += 1
    return got


def is_target(mod: Mod, targets: list[Target]) -> bool:
    return any(mod.group == t.group and mod.patterns == t.patterns and mod.level >= t.min_level for t in targets)


def reachable(item: Item, targets: list[Target], need: int) -> bool:
    """Whether the goal can still be met: the missing targets that can still roll (family absent, room on their
    side) are enough. A player stops working on a base as soon as it cannot."""
    limit = SIDE_LIMIT.get(item.rarity, 3)
    have = item.families()
    missing = Counter(t.side for t in targets if (t.group, t.patterns) not in have)
    possible = sum(min(n, limit - item.side(side)) for side, n in missing.items())
    return hits(item, targets) + possible >= need


@dataclass
class Strategy:
    key: str
    steps: list[dict]  # what to do: {"k": step key, "n": the English item names for its {0}, {1}...; "mod": a line}
    per_base: float = 0.0  # chance one base reaches the goal
    success: float = 0.0  # chance to reach it within MAX_TRIES bases
    bases: float | None = None  # bases used on average until it works (1 / per_base)
    bases_p90: int | None = None  # a bad-luck run: 9 of 10 finish within this many bases
    use: dict = field(default_factory=dict)  # average currency per finished item
    p90: dict = field(default_factory=dict)  # the same for the bad-luck run
    cost: float | None = None  # average price in divines
    cost_p90: float | None = None
    cost_per_base: float | None = None  # currency one base eats on average: what a batch of bases costs
    priced: bool = False  # every item used has a price
    attempts: int = 0  # attempts played
    successes: int = 0  # of them worked: under ~10 the chance is rough


def _measure(s: "Strategy", attempt, rng: random.Random):
    """Play single attempts (one base each): the chance p that a base works and the currency an attempt eats.
    Bases until success are then geometric: 1/p on average, and 9 of 10 players finish within
    ln(0.1) / ln(1 - p) bases - so a rare success costs no more time to estimate than a common one."""
    total, ok, n = Counter(), 0, 0
    while n < MAX_ATTEMPTS and (n == 0 or ok < ENOUGH_SUCCESSES):
        for _ in range(ATTEMPTS):
            used = Counter()
            ok += attempt(rng, used)
            total.update(used)
        n += ATTEMPTS
    s.attempts, s.successes = n, ok
    s.per_base = ok / n
    if not ok:
        return
    p = s.per_base
    s.success = 1 - (1 - p) ** MAX_TRIES
    s.bases = 1 / p
    s.bases_p90 = 1 if p >= 0.9 else math.ceil(math.log(0.1) / math.log(1 - p))
    per_attempt = {k: v / n for k, v in total.items()}
    s.use = {k: v * s.bases for k, v in per_attempt.items()}
    s.p90 = {k: v * s.bases_p90 for k, v in per_attempt.items()}


def strategies(pool: Pool, targets: list[Target], need: int, grade: str = "", essence: tuple | None = None,
               desecrated: Pool | None = None, bone: str | None = None, must_main: bool = False) -> list[Strategy]:
    """The candidate strategies for reaching `need` of the targets. `essence`: (essence name, mod) guaranteeing a
    target on this item class, if one exists; `desecrated`: the desecrated pool (bones) for this class;
    `must_main`: an item without the main target (the first, worth most) does not count, whatever else it has."""
    lvl, low = grade_rule(grade, getattr(pool, "fingerprint", None))
    out = []
    main = targets[0]

    def done(item: Item) -> bool:
        return hits(item, targets) >= need and (not must_main or hits(item, [main]) == 1)

    def can(item: Item) -> bool:
        """The goal still in reach - with the main target there, or its family absent and room on its side."""
        if not reachable(item, targets, need):
            return False
        if not must_main or hits(item, [main]):
            return True
        return ((main.group, main.patterns) not in item.families()
                and item.side(main.side) < SIDE_LIMIT.get(item.rarity, 3))

    def finish_with_exalts(item: Item, rng, used, greater: bool) -> bool:
        """Exalt until the goal, 6 mods, or the goal is out of reach. With Omen of Greater Exaltation the first
        exalt adds two mods at once (one omen per item, as players use it)."""
        first = greater
        while not done(item) and len(item.mods) < 6 and can(item):
            count = 2 if first and len(item.mods) <= 4 else 1
            if count == 2:
                used[GREATER_EXALT] += 1
            first = False
            used[f"{grade}Exalted Orb"] += 1
            for _ in range(count):
                mod = pool.pick(item, rng, None, lvl, low)
                if mod is None:
                    return done(item)
                item.mods.append(mod)
        return done(item)

    def magic_start(greater: bool):
        """Transmute + augment for a start worth keeping, regal, then exalts."""
        def attempt(rng, used) -> bool:
            item = Item("magic")
            used[f"{grade}Orb of Transmutation"] += 1
            item.mods.append(pool.pick(item, rng, None, lvl, low))
            used[f"{grade}Orb of Augmentation"] += 1
            mod = pool.pick(item, rng, None, lvl, low)
            if mod:
                item.mods.append(mod)
            if hits(item, targets) == 0:
                return False  # nothing worth keeping: the base stays in the pile, the next one is tried
            item.rarity = "rare"
            used[f"{grade}Regal Orb"] += 1
            mod = pool.pick(item, rng, None, lvl, low)
            if mod:
                item.mods.append(mod)
            return finish_with_exalts(item, rng, used, greater)
        return attempt

    def essence_start(greater: bool):
        name, given = essence

        def attempt(rng, used) -> bool:
            item = Item("magic")
            used[f"{grade}Orb of Transmutation"] += 1
            item.mods.append(pool.pick(item, rng, None, lvl, low))
            used[name] += 1
            item.rarity = "rare"
            item.mods = [m for m in item.mods if (m.group, m.patterns) != (given.group, given.patterns)]
            if item.side(given.type) >= SIDE_LIMIT["rare"]:
                return False
            item.mods.append(given)
            return finish_with_exalts(item, rng, used, greater)
        return attempt

    def alchemy(whittle: bool):
        """Alchemy, then chaos until the goal (up to 12 per base); Whittling removes the lowest level mod."""
        def attempt(rng, used) -> bool:
            item = Item("rare")
            used["Orb of Alchemy"] += 1
            for _ in range(4):
                mod = pool.pick(item, rng, None, 0)
                if mod:
                    item.mods.append(mod)
            for _ in range(12):
                if done(item):
                    return True
                if whittle:
                    used["Omen of Whittling"] += 1
                    item.mods.remove(min(item.mods, key=lambda m: m.level))
                else:
                    item.mods.remove(rng.choice(item.mods))
                used[f"{grade}Chaos Orb"] += 1
                mod = pool.pick(item, rng, None, lvl, low)
                if mod:
                    item.mods.append(mod)
            return done(item)
        return attempt

    def annul(item: Item, rng, used):
        """One plain Orb of Annulment: a random mod but the fractured one - sometimes a wanted one, which the exalts
        then bring back (the side omens cost ten to twenty times more than the orb: players annul plainly here)."""
        used["Orb of Annulment"] += 1
        item.mods.remove(rng.choice([m for m in item.mods if m is not item.fractured]))

    def reveal(item: Item, rng, used):
        """The desecrated mod revealed: three options on its side, the player takes a target if one is there; when
        the goal still needs one, Omen of Abyssal Echoes (active before the reveal) rerolls the options once."""
        hidden = next(m for m in item.mods if isinstance(m, Unrevealed))
        item.mods.remove(hidden)
        echoes = not done(item)
        if echoes:
            used[ECHOES] += 1
        for _ in range(2 if echoes else 1):
            options, shown = [], Item(item.rarity, list(item.mods))
            for _ in range(3):
                mod = desecrated.pick(shown, rng, hidden.type)
                if mod:
                    options.append(mod)
                    shown.mods.append(mod)
            good = [m for m in options if is_target(m, targets)]
            if good:
                item.mods.append(good[0])
                return
        if options:
            item.mods.append(options[0])

    def fracture_start(light: bool):
        """The main target from transmute + augment (else a new base), a plain regal and a bone for four mods - the
        unrevealed one is not fractured, so the Fracturing Orb locks the main mod 1 time in 3 (else the next base);
        then exalts (with Omen of Greater Exaltation while two places are free) and annulments of what is not wanted,
        until the goal; the desecrated mod revealed at the end, or (`light`) taken off at once with Omen of Light."""
        def attempt(rng, used) -> bool:
            item = Item("magic")
            used[f"{grade}Orb of Transmutation"] += 1
            item.mods.append(pool.pick(item, rng, None, lvl, low))
            used[f"{grade}Orb of Augmentation"] += 1
            mod = pool.pick(item, rng, None, lvl, low)
            if mod:
                item.mods.append(mod)
            key = next((m for m in item.mods if is_target(m, [main])), None)
            if key is None:
                return False
            item.rarity = "rare"
            used["Regal Orb"] += 1  # a plain one: its mod only fills a place
            mod = pool.pick(item, rng)
            if mod:
                item.mods.append(mod)
            drawn = desecrated.pick(item, rng)
            if drawn is None:
                return False
            used[bone] += 1
            item.mods.append(Unrevealed(drawn.type))
            if len(item.mods) < 4:
                return False
            used[FRACTURE] += 1
            if rng.choice([m for m in item.mods if not isinstance(m, Unrevealed)]) is not key:
                return False
            item.fractured = key
            if light:
                used[LIGHT] += 1
                used["Orb of Annulment"] += 1
                item.mods = [m for m in item.mods if not isinstance(m, Unrevealed)]
            for _ in range(FRACTURE_ACTIONS):
                if done(item):
                    break
                free = 6 - len(item.mods)
                if free and can(item):
                    count = 2 if free >= 2 else 1
                    if count == 2:
                        used[GREATER_EXALT] += 1
                    used[f"{grade}Exalted Orb"] += 1
                    for _ in range(count):
                        mod = pool.pick(item, rng, None, lvl, low)
                        if mod:
                            item.mods.append(mod)
                elif any(not is_target(m, targets) and not isinstance(m, Unrevealed) and m is not item.fractured
                         for m in item.mods):
                    annul(item, rng, used)
                else:
                    break
            if any(isinstance(m, Unrevealed) for m in item.mods):
                reveal(item, rng, used)
            return done(item)
        return attempt

    # steps name their text by key (the UI words them in its language) and the English item names they use
    exalt = {"k": "exalt", "n": [f"{grade}Exalted Orb"]}
    exalt_greater = {"k": "exalt_greater", "n": [f"{grade}Exalted Orb", GREATER_EXALT]}
    plays = {}
    for greater in (False, True):
        key = "magic_greater" if greater else "magic"
        plays[key] = magic_start(greater)
        out.append(Strategy(key, [{"k": "transmute_augment", "n": [f"{grade}Orb of Transmutation",
                                                                  f"{grade}Orb of Augmentation"]},
                                  {"k": "regal", "n": [f"{grade}Regal Orb"]}, exalt_greater if greater else exalt]))
        if essence:
            key = "essence_greater" if greater else "essence"
            plays[key] = essence_start(greater)
            name, given = essence
            out.append(Strategy(key, [{"k": "transmute", "n": [f"{grade}Orb of Transmutation"]},
                                      {"k": "essence", "n": [name], "mod": " / ".join(given.lines)},
                                      exalt_greater if greater else exalt]))
    for whittle in (False, True):
        key = "alchemy_whittle" if whittle else "alchemy"
        plays[key] = alchemy(whittle)
        out.append(Strategy(key, [{"k": "alchemy", "n": ["Orb of Alchemy"]},
                                  {"k": "chaos_whittle", "n": [f"{grade}Chaos Orb", "Omen of Whittling"]} if whittle
                                  else {"k": "chaos", "n": [f"{grade}Chaos Orb"]}]))

    # desecration: a finishing touch when a target family is in the desecrated pool (choose 1 of 3 revealed mods)
    if desecrated and bone:
        dmods = [m for m in desecrated.mods if any(m.group == t.group and m.patterns == t.patterns for t in targets)]
        if dmods:
            for s in out:
                s.steps.append({"k": "desecrate", "n": [bone, ECHOES]})

    # fracturing the main mod: the bone's unrevealed mod makes the fourth one (the desecrated pool must have mods)
    if desecrated and desecrated.mods and bone:
        for light in (False, True):
            key = "fracture_light" if light else "fracture"
            plays[key] = fracture_start(light)
            steps = [{"k": "fracture_main", "n": [f"{grade}Orb of Transmutation", f"{grade}Orb of Augmentation"],
                      "mod": targets[0].label},
                     {"k": "regal_bone", "n": ["Regal Orb", bone]},
                     {"k": "fracture", "n": [FRACTURE]}]
            if light:
                steps.append({"k": "light", "n": ["Orb of Annulment", LIGHT]})
            steps.append({"k": "annul_exalt_greater", "n": ["Orb of Annulment", f"{grade}Exalted Orb", GREATER_EXALT]})
            if not light:
                steps.append({"k": "reveal", "n": [ECHOES]})
            out.append(Strategy(key, steps))

    rng = random.Random(7)
    for s in out:
        _measure(s, plays[s.key], rng)
    return out


def price(strategies_: list[Strategy], prices) -> None:
    """Average and bad-luck (90th percentile) price in divines; bases are not priced (white bases are cheap)."""
    if prices is None:
        return
    for s in strategies_:
        items = list(s.use)
        found = {k: prices.get(k) for k in items}
        s.priced = all(found.values())
        s.cost = sum(s.use[k] * found[k].divine for k in items if found[k])
        s.cost_p90 = sum(s.p90[k] * found[k].divine for k in items if found[k])
        s.cost_per_base = s.cost / s.bases if s.bases else None


# what players spend: a craft within ~100 divines of currency until the item is done (the player's rule: a batch of
# bases for up to 100 div, then think further); a way that costs more on average is not how anyone crafts - it stays
# shown, folded, as "expensive"
BUDGET = 100.0


def lines_index(db: ModDB, base_tags) -> dict[tuple, Mod]:
    """A mod by its lines - one that rolls on this base first: one line ("+4 to Level of all Melee Skills") is a mod
    of several item classes, and only this base's one has tiers here."""
    out = {}
    for m in db.rollable(base_tags, 100):
        out.setdefault(tuple(m.lines), m)
    for m in db.mods:
        out.setdefault(tuple(m.lines), m)
    return out


def pick_targets(db: ModDB, plan, base_tags, item_level: int, count: int = 6, top_tiers: int = 3,
                 first: Mod | None = None) -> list[Target]:
    """The mod families the slot plan values most (what the item has that carries value, then what it could roll),
    each at its top tiers for the item level; `count` of them, at most three per side. `first`: the player's main
    mod, put before them."""
    by_lines = lines_index(db, base_tags)
    by_id = {m.id: m for m in db.mods}
    wanted = [(by_lines.get(tuple(a.template)), a.score) for a in plan.affixes if a.score > 0.5]
    wanted += [(by_id.get(c.mod_id), c.score) for c in plan.candidates if c.score > 0.5]
    mods = [mod for mod, _ in sorted((w for w in wanted if w[0]), key=lambda w: -w[1])]
    return targets_of(db, ([first] if first else []) + mods, base_tags, item_level, count, top_tiers)


def targets_of(db: ModDB, mods: list[Mod], base_tags, item_level: int, count: int = 6, top_tiers: int = 3) -> list[Target]:
    """The mods (most wanted first) as craft targets: each family once, at its top tiers for the item level; `count`
    of them, at most three per side."""
    out, seen, sides = [], set(), Counter()
    for mod in mods:
        key = (mod.group, mod.patterns)
        if key in seen or sides[mod.type] >= 3:
            continue
        tiers = [m for m in db.tiers_of(mod, base_tags) if m.level <= item_level][:top_tiers]
        if not tiers:
            continue
        seen.add(key)
        sides[mod.type] += 1
        out.append(Target(mod.group, mod.patterns, mod.type, tiers[-1].level, " / ".join(tiers[0].lines)))
        if len(out) >= count:
            break
    return out


# how good a target mod must be: its tier among the top N the item level allows (players usually settle for "good")
QUALITY_TIERS = {"top": 2, "good": 4, "any": 99}

# the currency the crafting guide names (poe2lab.web: "Как крафтить"), priced for it
GUIDE_ITEMS = ["Orb of Transmutation", "Orb of Augmentation", "Regal Orb", "Exalted Orb", GREATER_EXALT,
               "Orb of Alchemy", "Chaos Orb", "Orb of Annulment", "Fracturing Orb", "Omen of Abyssal Echoes", "Omen of Light",
               "Omen of Sinistral Annulment", "Omen of Dextral Annulment", "Omen of Homogenising Exaltation",
               "Greater Exalted Orb", "Perfect Exalted Orb", "Gnawed Rib", "Gnawed Jawbone", "Gnawed Collarbone",
               "Ancient Rib", "Ancient Jawbone", "Ancient Collarbone",
               "Greater Essence of the Body", "Perfect Essence of the Body"]


# changing a mod on an item already worn: each way's chance per try, and what a miss costs
SIDE_EXALT = {"Prefix": "Omen of Sinistral Exaltation", "Suffix": "Omen of Dextral Exaltation"}
SIDE_ANNUL = {"Prefix": "Omen of Sinistral Annulment", "Suffix": "Omen of Dextral Annulment"}
SIDE_NECRO = {"Prefix": "Omen of Sinistral Necromancy", "Suffix": "Omen of Dextral Necromancy"}
WORTH, RISKY = 0.25, 0.08  # best chance per try: worth a try / risky / a lottery (buy or craft from a white base)


def modify_routes(db: ModDB, pool: Pool, desecrated: Pool | None, essences: list[dict], item_type: str,
                  base_tags, item_level: int, mod: Mod, have: set, side_count: int, total_mods: int,
                  replace: bool, bone: str | None = None) -> dict:
    """The ways to get `mod`'s family (at a good tier for the item level) onto a worn rare, with the chance per try.
    `have`: the item's mod families that stay; `side_count` / `total_mods`: its mods on that side / in all.
    Adding to a free slot: an exalt with the side omen - a miss takes the slot. Replacing: annul with the side omen
    (removes the wrong mod 1 time in side_count) and then exalt; or a perfect essence (removes a random mod of all)."""
    tiers = [m for m in db.tiers_of(mod, base_tags) if m.level <= item_level][:QUALITY_TIERS["good"]]
    if not tiers:
        return {"routes": [], "verdict": "lottery", "chance": 0.0, "minLevel": None}
    family, side, min_level = (mod.group, mod.patterns), mod.type, tiers[-1].level
    rows = [r for r in pool.rows if r[1] == side and r[2] not in have]
    total = sum(r[5] for r in rows)
    exalt = sum(r[5] for r in rows if r[2] == family and r[3] >= min_level) / total if total else 0.0
    routes = []
    if replace:
        routes.append({"k": "annul_exalt", "n": ["Orb of Annulment", SIDE_ANNUL[side], "Exalted Orb", SIDE_EXALT[side]],
                       "chance": exalt / max(side_count, 1), "risk": "mod"})
        by_id = {m.id: m for m in db.mods}
        for es in essences:
            given = by_id.get(es["mods"].get(item_type, ""))
            if (es["name"].startswith("Perfect") and given and (given.group, given.patterns) == family
                    and given.level >= min_level):
                routes.append({"k": "perfect_essence", "n": [es["name"]], "chance": 1 / max(total_mods, 1),
                               "risk": "mod", "mod": " / ".join(given.lines)})
                break
    else:
        routes.append({"k": "exalt_side", "n": ["Exalted Orb", SIDE_EXALT[side]], "chance": exalt, "risk": "slot"})
    if desecrated and bone:
        drows = [r for r in desecrated.rows if r[1] == side and r[2] not in have]
        dtotal = sum(r[5] for r in drows)
        q = sum(r[5] for r in drows if r[2] == family) / dtotal if dtotal else 0.0
        if q:  # three options revealed, one chosen; the echoes omen rerolls them once
            room = 1 / max(side_count, 1) if replace else 1.0  # replacing: the annul must hit the right mod first
            necro = [bone, SIDE_NECRO[side], "Omen of Abyssal Echoes"]
            routes.append({"k": "annul_desecrate" if replace else "desecrate",
                           "n": (["Orb of Annulment", SIDE_ANNUL[side]] if replace else []) + necro,
                           "chance": room * (1 - (1 - q) ** 3), "echoes": room * (1 - (1 - q) ** 6),
                           "risk": "mod" if replace else "slot"})
    best = max((r["chance"] for r in routes), default=0.0)
    verdict = "worth" if best >= WORTH else "risky" if best >= RISKY else "lottery"
    return {"routes": routes, "verdict": verdict, "chance": best, "minLevel": min_level}


# every desecrated mod is an abyssal lord's (its id names him); the lord's omen guarantees a random mod of his on a
# weapon or jewellery desecration
LORD_OMEN = {"Ulaman": "Omen of the Sovereign", "Amanamu": "Omen of the Liege", "Kurgal": "Omen of the Blackblooded"}
JEWELLERY = {"Ring", "Amulet", "Belt"}
# "guarantee a random Ulaman modifier": one of the three revealed options is his, the other two random (confirmed by
# the player in game). After it: the options rerolled once at once (Omen of Abyssal Echoes; counted as a plain
# reroll), or the desecration taken off (an annulment with Omen of Light) and the procedure done again
LORD_OPTIONS = 1
DESECRATE_TRIALS = 20000


def lord_of(mod) -> str | None:
    return next((lord for lord in LORD_OMEN if lord in mod.id), None)


def lord_omens_apply(item_type: str) -> bool:
    return is_weapon(item_type) or item_type in JEWELLERY or item_type == "Quiver"


def desecration_ways(desecrated: Pool, wanted: Mod, item_type: str, bone: str, have: set = frozenset()) -> list[dict]:
    """The ways to get the desecrated mod `wanted` from a bone, with the chance it is among the revealed options: the
    bone alone, with the side omen (Sinistral / Dextral Necromancy: the unrevealed mod on its side), with its lord's
    omen (weapons and jewellery), both; each also with Omen of Abyssal Echoes (the options rerolled once). `have`:
    the item's mod families (none of them is offered). The side of a plain desecration is drawn like its mod."""
    lord, side, family = lord_of(wanted), wanted.type, (wanted.group, wanted.patterns)
    lords = lord is not None and lord_omens_apply(item_type)
    mine = [r for r in desecrated.rows if r[1] == side and lord_of(r[0]) == lord and r[2] not in have]
    out = []
    for side_omen, lord_omen, echoes in itertools.product((False, True), (False, True) if lords else (False,),
                                                          (False, True)):
        rng = random.Random(11)
        got = 0
        for _ in range(DESECRATE_TRIALS):
            drawn = side if side_omen else (desecrated.pick(Item("rare", []), rng) or wanted).type
            for round_ in range(2 if echoes else 1):
                shown = Item("rare", [])
                if lord_omen and round_ == 0 and drawn == side and mine:
                    for _ in range(LORD_OPTIONS):
                        shown.mods.append(rng.choices(mine, weights=[r[5] for r in mine])[0][0])
                while len(shown.mods) < 3:
                    mod = desecrated.pick(shown, rng, drawn, exclude=have)
                    if mod is None:
                        break
                    shown.mods.append(mod)
                if any((m.group, m.patterns) == family for m in shown.mods):
                    got += 1
                    break
        names = [bone] + ([SIDE_NECRO[side]] if side_omen else []) + ([LORD_OMEN[lord]] if lord_omen else []) + \
                ([ECHOES] if echoes else [])
        out.append({"n": names, "chance": got / DESECRATE_TRIALS})
    return out


def price_desecration(ways: list[dict], prices) -> int | None:
    """Each way's price per try and, as an average until it works, with a miss taken off before the next try (an Orb
    of Annulment with Omen of Light); the index of the cheapest (or, unpriced, the likeliest)."""
    if not ways:
        return None
    removal = None
    if prices is not None:
        light, annul = prices.get(LIGHT), prices.get("Orb of Annulment")
        removal = light.divine + annul.divine if light and annul else None
    for w in ways:
        found = [prices.get(n) for n in w["n"]] if prices is not None else []
        w["priced"] = bool(found) and all(found)
        w["cost"] = sum(p.divine for p in found if p) if found else None
        p = w["chance"]
        w["expected"] = (w["cost"] / p + (removal or 0) * (1 - p) / p) if w["priced"] and p > 0 else None
    priced = [i for i, w in enumerate(ways) if w["expected"] is not None]
    if priced:
        return min(priced, key=lambda i: ways[i]["expected"])
    return max(range(len(ways)), key=lambda i: ways[i]["chance"])


def bone_for(item_type: str, item_level: int = 82) -> str | None:
    grade = next(g for level, g in BONE_GRADES if item_level >= level)
    if item_type in ("Ring", "Amulet", "Belt"):
        return f"{grade} {BONE['Jewellery']}"
    if item_type in ("Helmet", "Body Armour", "Gloves", "Boots", "Shield", "Focus"):
        return f"{grade} {BONE['Armour']}"
    return f"{grade} {BONE['Weapon']}"
