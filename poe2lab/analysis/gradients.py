"""Marginal value of stats: how much one (and two) extra units change DPS and defences."""
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
}


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


def _pct(new: dict, base: dict, key: str) -> float:
    b = base.get(key, 0.0)
    return (new.get(key, 0.0) - b) / b * 100 if b else 0.0


def compute(runner, stats: list[Stat] = STATS) -> tuple[dict, list[Gradient]]:
    """runner: a PobEngine or EnginePool with the build loaded and main skill selected."""
    calls = [{}] + [{"mods": [mod_line(s, m)]} for s in stats for m in (1, 2)]
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
            {m: _pct(r1, base, k) for m, k in METRICS.items()},
            {m: _pct(r2, base, k) for m, k in METRICS.items()},
        ))
    return base, grads
