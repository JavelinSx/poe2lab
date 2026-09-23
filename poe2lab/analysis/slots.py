"""Per-slot plan: what each affix on an item is worth, what the best rollable mods would add, and what to do.

Every value is computed by equipping an edited copy of the item, so local mods (weapon damage, armour) count right."""
from dataclasses import dataclass, field
from types import SimpleNamespace

from ..data.moddb import ModDB, max_roll
from ..engine import PobError
from .gradients import metric_changes
from .items import add_lines, remove_lines

AFFIX_LIMIT = {"RARE": 3, "MAGIC": 1}
SKIP_TYPES = {"Flask", "Charm", "Jewel"}
APPROX = 0.05  # rolled value this far outside every tier: probably several mods merged into one line
MIN_GAIN = 0.5  # score points; smaller improvements are not worth an action
# Mods PoB gives no value to but players keep on purpose; never suggested for replacement.
UTILITY = ("Movement Speed", "Rarity of Items", "Light Radius", "Charm", "Flask")
ATTRS = ("Str", "Dex", "Int")


def is_utility(lines: list[str]) -> bool:
    return any(u in l for u in UTILITY for l in lines)


def mana_balance(out: dict) -> float:
    """Mana regained per second minus what the main skill spends per second."""
    gain = out.get("ManaRegenRecovery", 0) + out.get("ManaLeechGainRate", 0) + out.get("ManaOnHitRate", 0)
    return gain - out.get("ManaPerSecondCost", 0)


def holds(base: dict, without: dict, check_mana: bool = True) -> list[str]:
    """What stops working in game if this affix goes: Spirit for reservations, attribute requirements,
    resistance caps and (unless the build's mana is confirmed fine) mana to keep casting the main skill."""
    out = []
    if without.get("SpiritUnreserved", 0) < 0 <= base.get("SpiritUnreserved", 0):
        out.append("spirit на резервы")
    if check_mana:
        before, after = mana_balance(base), mana_balance(without)
        if after < 0 <= before:
            out.append("мана на основной скилл")
        elif before < 0 and after < before - max(10.0, 0.1 * abs(before)):
            out.append(f"мана: дефицит {before:.0f}/с станет {after:.0f}/с")
    for res in ("Fire", "Cold", "Lightning"):
        if without.get(f"{res}Resist", 0) < 75 <= base.get(f"{res}Resist", 0):
            out.append(f"кап резиста {res}")
    for a in ATTRS:
        # PoB leaves Req<attr> out of the output when nothing requires that attribute
        if without.get(a, 0) < without.get(f"Req{a}", 0) and base.get(a, 0) >= base.get(f"Req{a}", 0):
            out.append(f"требования {a}")
    return out


@dataclass
class AffixValue:
    type: str
    lines: list[str]
    template: list[str]
    tier: int
    tiers: int
    merged: bool  # value exceeds every tier: likely the sum of several mods
    score: float  # share of the build it provides (report score units): the loss if it went, as % of now
    changes: dict[str, float]
    holds: list[str] = field(default_factory=list)  # what breaks in game without it
    utility: bool = False  # PoB does not value it, but it is usually kept on purpose

    @property
    def replaceable(self) -> bool:
        return not self.holds and not self.utility


@dataclass
class Candidate:
    type: str
    lines: list[str]  # top roll of the best tier allowed by the item level
    template: list[str]
    level: int
    score: float
    changes: dict[str, float]
    mod_id: str = ""


@dataclass
class SlotPlan:
    slot: str
    item: str
    base: str
    item_level: int
    rarity: str
    corrupted: bool
    limit: int
    affixes: list[AffixValue]
    candidates: list[Candidate]
    unknown: list[str]
    actions: list[str] = field(default_factory=list)

    def count(self, kind: str) -> int:
        return sum(a.type == kind for a in self.affixes)

    @property
    def uncertain(self) -> bool:
        return bool(self.unknown) or any(a.merged for a in self.affixes)


def _score(changes: dict, mode: str, weights: dict) -> float:
    from .report import score
    return score(SimpleNamespace(one=changes), mode, weights)


def plan_slot(engine, db: ModDB, config: dict, item: dict, mode: str, weights: dict, top: int = 5,
              check_mana: bool = True) -> SlotPlan:
    slot, tags, ilvl = item["slot"], item["tags"], item["itemLevel"]
    text = engine.item_text(slot)
    base = engine.what_if(config=config)
    found, unknown = db.identify([x["line"] for x in item["explicit"]], tags, ilvl)

    affixes = []
    for a in found:
        without = engine.what_if(config=config, replace_item=(slot, remove_lines(text, a.rolled)))
        # contribution as a share of the current build (removal loss, sign flipped); stays sane when
        # removing the affix drops a metric to nearly zero
        changes = {m: -v for m, v in metric_changes(without, base).items()}
        affixes.append(AffixValue(a.mod.type, a.rolled, list(a.mod.lines), a.tier, a.tiers,
                                  a.mod.distance(a.rolled) > APPROX, _score(changes, mode, weights), changes,
                                  holds(base, without, check_mana), is_utility(a.rolled)))

    present = {a.mod.group for a in found}
    candidates = []
    for mod in db.best_tiers(tags, ilvl):
        if mod.group in present:
            continue
        lines = [max_roll(l) for l in mod.lines]
        try:
            out = engine.what_if(config=config, replace_item=(slot, add_lines(text, lines)))
        except PobError:
            continue
        changes = metric_changes(out, base)
        candidates.append(Candidate(mod.type, lines, list(mod.lines), mod.level, _score(changes, mode, weights),
                                    changes, mod.id))
    candidates.sort(key=lambda c: -c.score)

    limit = AFFIX_LIMIT.get(item["rarity"], 0)
    plan = SlotPlan(slot, item["name"], item["baseName"], ilvl, item["rarity"], item["corrupted"], limit,
                    sorted(affixes, key=lambda a: -a.score), [c for c in candidates if c.score > 0][: top * 2], unknown)
    plan.actions = _actions(plan, candidates)
    return plan


def _actions(plan: SlotPlan, candidates: list[Candidate]) -> list[str]:
    actions = []
    for kind, word in (("Prefix", "префикс"), ("Suffix", "суффикс")):
        best = next((c for c in candidates if c.type == kind and c.score >= MIN_GAIN), None)
        if not best:
            continue
        mine = [a for a in plan.affixes if a.type == kind]
        free = plan.limit - len(mine)
        what = " / ".join(best.lines)
        if free > 0:
            maybe = " (счёт приблизительный — проверь в игре, что слот свободен)" if plan.uncertain else ""
            if plan.corrupted:
                actions.append(f"свободный {word}, но предмет испорчен: в замене искать ещё и «{what}» (+{best.score:.1f})")
            else:
                actions.append(f"докрафтить {word}: «{what}» (+{best.score:.1f}){maybe}")
            continue
        weakest = min((a for a in mine if a.replaceable), key=lambda a: a.score, default=None)
        if weakest and best.score - weakest.score >= MIN_GAIN:
            swap = f"«{' / '.join(weakest.lines)}» ({weakest.score:+.1f}) → «{what}» ({best.score:+.1f})"
            verb = "в замене искать" if plan.corrupted else "заменить"
            actions.append(f"{verb} {word}: {swap}")
    return actions


@dataclass
class CraftStep:
    slot: str
    removed: list[str]  # affix lines taken off (empty when filling a free slot)
    added: list[str]
    score: float  # this step alone
    changes: dict[str, float]  # this step alone
    total: dict[str, float]  # all steps so far vs the original build
    uncertain: bool  # the item's free-slot count was approximate
    mod_id: str = ""
    item_type: str = ""


def craft_path(engine, db: ModDB, config: dict, mode: str, weights: dict, steps: int = 6,
               per_kind: int = 3, check_mana: bool = True) -> list[CraftStep]:
    """Greedy crafting across all craftable items: apply the single best add/replace, recompute everything
    (so a capped resistance stops being attractive), repeat. The build is restored afterwards."""
    originals = {it["slot"]: engine.item_text(it["slot"]) for it in engine.equipped_item_details()}
    start = engine.what_if(config=config)
    path: list[CraftStep] = []
    try:
        for _ in range(steps):
            current = engine.what_if(config=config)
            best = None
            for item in engine.equipped_item_details():
                if (item["corrupted"] or item["type"] in SKIP_TYPES or "Swap" in item["slot"]
                        or item["rarity"] not in AFFIX_LIMIT):
                    continue
                plan = plan_slot(engine, db, config, item, mode, weights, top=per_kind, check_mana=check_mana)
                text = engine.item_text(item["slot"])
                for kind in ("Prefix", "Suffix"):
                    mine = [a for a in plan.affixes if a.type == kind]
                    weakest = min((a for a in mine if a.replaceable), key=lambda a: a.score, default=None)
                    removed = [] if plan.limit - len(mine) > 0 else (weakest.lines if weakest else None)
                    if removed is None:
                        continue
                    for cand in [c for c in plan.candidates if c.type == kind][:per_kind]:
                        new_text = add_lines(remove_lines(text, removed) if removed else text, cand.lines)
                        out = engine.what_if(config=config, replace_item=(item["slot"], new_text))
                        if holds(current, out, check_mana):
                            continue  # would uncap a resistance or break spirit / attributes / mana
                        changes = metric_changes(out, current)
                        s = _score(changes, mode, weights)
                        if best is None or s > best[0]:
                            best = (s, item["slot"], removed, cand, new_text, changes, plan.uncertain, item["type"])
            if best is None or best[0] < MIN_GAIN:
                break
            s, slot, removed, cand, new_text, changes, uncertain, item_type = best
            engine.equip_item(slot, new_text)
            path.append(CraftStep(slot, list(removed), list(cand.lines), s, changes,
                                  metric_changes(engine.what_if(config=config), start), uncertain,
                                  cand.mod_id, item_type))
    finally:
        for step_slot in {st.slot for st in path}:
            engine.equip_item(step_slot, originals[step_slot])
    return path


def plan_all(engine, db: ModDB, config: dict, mode: str, weights: dict, top: int = 5,
             check_mana: bool = True) -> list[SlotPlan]:
    plans = []
    for item in engine.equipped_item_details():
        if item["type"] in SKIP_TYPES or "Swap" in item["slot"] or item["rarity"] not in AFFIX_LIMIT:
            continue
        plans.append(plan_slot(engine, db, config, item, mode, weights, top, check_mana))
    return plans
