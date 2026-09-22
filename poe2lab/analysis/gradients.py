"""Marginal value of stats: how much one (and two) extra units change DPS, defences and recovery."""
from dataclasses import dataclass

from .stats import STATS, Stat, mod_line

METRICS = {
    "dps": "CombinedDPS",
    "ehp": "TotalEHP",
    "phys_hit": "PhysicalMaximumHitTaken",
    "fire_hit": "FireMaximumHitTaken",
    "cold_hit": "ColdMaximumHitTaken",
    "lightning_hit": "LightningMaximumHitTaken",
    "chaos_hit": "ChaosMaximumHitTaken",
    "recovery": None,  # derived, see recovery_per_second
}


def recovery_per_second(out: dict) -> float:
    """Life regained per second while attacking: leech + life on hit (both in LifeLeechGainRate), regen, recoup."""
    return out.get("LifeLeechGainRate", 0.0) + out.get("LifeRegenRecovery", 0.0) + out.get("LifeRecoupRecoveryAvg", 0.0)


def metric_value(out: dict, metric: str) -> float:
    key = METRICS[metric]
    return recovery_per_second(out) if key is None else out.get(key, 0.0)


@dataclass
class Gradient:
    stat: Stat
    one: dict[str, float]  # % change per metric for one unit
    two: dict[str, float]  # % change per metric for two units

    def saturation(self, metric: str) -> float | None:
        """Second unit's gain relative to the first: 1 = linear, <1 diminishing, ~0 capped. None if no effect."""
        first = self.one[metric]
        if abs(first) < 1e-3:
            return None
        return (self.two[metric] - first) / first


def _pct(new: dict, base: dict, metric: str) -> float:
    b = metric_value(base, metric)
    return (metric_value(new, metric) - b) / b * 100 if b else 0.0


def compute(runner, stats: list[Stat] = STATS, config: dict | None = None) -> tuple[dict, list[Gradient]]:
    """runner: a PobEngine or EnginePool with the build loaded and main skill selected.
    config: Configuration tab overrides (e.g. enemy level/boss) applied to every calculation."""
    extra = {"config": config} if config else {}
    calls = [dict(extra)] + [{"mods": [mod_line(s, m)], **extra} for s in stats for m in (1, 2)]
    if hasattr(runner, "map"):
        results = runner.map("what_if", calls)
    else:
        results = [runner.what_if(**c) for c in calls]
    base, rest = results[0], results[1:]
    grads = []
    for i, stat in enumerate(stats):
        r1, r2 = rest[2 * i], rest[2 * i + 1]
        grads.append(Gradient(
            stat,
            {m: _pct(r1, base, m) for m in METRICS},
            {m: _pct(r2, base, m) for m in METRICS},
        ))
    return base, grads
