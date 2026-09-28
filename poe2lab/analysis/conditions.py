"""Configuration audit: which checkboxes relevant to the build are off (PoB undervalues the build if they hold in
game) or on (PoB assumes them - worth confirming), and how much each one moves damage and defences."""
from dataclasses import dataclass

from .combat import ailment_uptimes, expected_dps
from .gradients import hit_change, recovery_change, recovery_per_second

NOISE_PCT = 0.5


@dataclass
class ConditionImpact:
    var: str
    label: str
    checked: bool
    # % change from flipping the box: for unchecked boxes it is the gain if it were true, for checked ones the loss if false
    dps_pct: float
    phys_hit_pct: float
    chaos_hit_pct: float
    ele_hit_pct: float
    recovery_pct: float
    life_pct: float

    def _values(self):
        return (self.dps_pct, self.phys_hit_pct, self.chaos_hit_pct, self.ele_hit_pct, self.recovery_pct, self.life_pct)

    @property
    def magnitude(self) -> float:
        """Size of the effect in its meaningful direction: gain for an unchecked box, loss for a checked one.
        Side effects the other way (e.g. less recoup because a frozen enemy hits less) are ignored."""
        return max(self._values()) if not self.checked else -min(self._values())


def _pct(new: float, old: float) -> float:
    return (new - old) / old * 100 if old else 0.0


ENEMY_PREFIX = "conditionEnemy"
# PoB's quest reward boxes ("Act 1: Ogham Castle"...): the character's progress, not a condition of the fight
QUEST_PREFIX = "quest"


def damage_range(engine, config: dict, impacts: list[ConditionImpact]) -> dict:
    """DPS with no enemy debuffs assumed vs with every unticked enemy debuff that adds damage at once.
    For when the player cannot say how often enemies are stunned/crushed/shocked: reality is in between - and
    `expected` is where the build's own ailments put it (each for the share of the fight it holds, see
    poe2lab.analysis.combat), with those shares in `uptimes`."""
    out = engine.what_if(config=config)
    base = out["CombinedDPS"]
    ups = ailment_uptimes(out)
    shares = [{"var": c.var, "label": c.label, "uptime": ups[c.var]["uptime"], "checked": c.checked}
              for c in impacts if c.var in ups]
    expected = expected_dps(base, impacts, ups)
    debuffs = [c for c in impacts if not c.checked and c.var.startswith(ENEMY_PREFIX) and c.dps_pct >= NOISE_PCT]
    if not debuffs:
        return {"low": base, "high": base, "conditions": [], "expected": expected, "uptimes": shares}
    high = engine.what_if(config=config | {c.var: True for c in debuffs})["CombinedDPS"]
    return {"low": base, "high": high, "conditions": [c.label for c in debuffs], "expected": expected,
            "uptimes": shares}


def audit(engine, config: dict) -> list[ConditionImpact]:
    base = engine.what_if(config=config)
    out = []
    for opt in engine.config_checkboxes():
        if opt["var"].startswith(QUEST_PREFIX):
            continue
        r = engine.what_if(config=config | {opt["var"]: not opt["checked"]})
        ele = min(r[f"{t}MaximumHitTaken"] for t in ("Fire", "Cold", "Lightning"))
        ele_base = min(base[f"{t}MaximumHitTaken"] for t in ("Fire", "Cold", "Lightning"))
        out.append(ConditionImpact(
            opt["var"], opt["label"], opt["checked"],
            dps_pct=_pct(r["CombinedDPS"], base["CombinedDPS"]),
            phys_hit_pct=hit_change(r, base, "Physical"),
            chaos_hit_pct=hit_change(r, base, "Chaos"),
            ele_hit_pct=hit_change({"FireMaximumHitTaken": ele}, {"FireMaximumHitTaken": ele_base}, "Fire"),
            recovery_pct=recovery_change(r, base),
            life_pct=_pct(r["Life"], base["Life"]),
        ))
    return sorted((c for c in out if c.magnitude >= NOISE_PCT), key=lambda c: -c.magnitude)
