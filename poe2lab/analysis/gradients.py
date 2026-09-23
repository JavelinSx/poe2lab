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
    """What refills the pool the build actually stands on, per second.

    Life builds: leech + life on hit (both in LifeLeechGainRate), regeneration, recoup - all work while fighting.
    Energy shield builds (ES above life, incl. Chaos Inoculation at 1 life): ES regeneration and leech, plus
    recharge. Recharge only starts after a pause without damage, so its rate is discounted by that delay:
    rate / (1 + delay in seconds). A heuristic, but it moves the right way for both "faster recharge" and
    "faster start of recharge" mods."""
    if out.get("EnergyShield", 0.0) > out.get("Life", 0.0):
        recharge = out.get("EnergyShieldRecharge", 0.0) / (1 + out.get("EnergyShieldRechargeDelay", 0.0))
        return out.get("EnergyShieldRegenRecovery", 0.0) + out.get("EnergyShieldLeechRate", 0.0) + recharge
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


IMMUNE_HIT = 1e9  # the engine's value for an infinite survivable hit, see analysis.threats
IMMUNITY_PCT = 100.0  # gaining (losing) immunity to a damage type counts as +100% (-100%) for that type
# Recovery is measured against at least this share of the pool per second: a build that barely recovers would
# otherwise read +2000% for its first leech mod, and such percentages swamp every ranking.
RECOVERY_FLOOR = 0.03


def _pct(new: dict, base: dict, metric: str) -> float:
    b, n = metric_value(base, metric), metric_value(new, metric)
    if metric.endswith("_hit") and (b >= IMMUNE_HIT or n >= IMMUNE_HIT):
        # a percentage against infinity means nothing and would swamp every ranking: count it as a big, finite step
        return 0.0 if (b >= IMMUNE_HIT) == (n >= IMMUNE_HIT) else (IMMUNITY_PCT if n >= IMMUNE_HIT else -IMMUNITY_PCT)
    if metric == "recovery":
        pool = max(base.get("Life", 0.0), base.get("EnergyShield", 0.0))
        b_ref = max(b, RECOVERY_FLOOR * pool)
        return (n - b) / b_ref * 100 if b_ref else 0.0
    return (n - b) / b * 100 if b else 0.0


def recovery_change(new: dict, base: dict) -> float:
    """% change of recovery, against at least RECOVERY_FLOOR of the pool per second."""
    return _pct(new, base, "recovery")


def hit_change(new: dict, base: dict, damage_type: str) -> float:
    """% change of the survivable hit of one damage type, immunity counted as a finite step."""
    return _pct(new, base, HIT_METRICS[damage_type])


HIT_METRICS = {"Physical": "phys_hit", "Fire": "fire_hit", "Cold": "cold_hit", "Lightning": "lightning_hit",
               "Chaos": "chaos_hit"}


def metric_changes(new: dict, base: dict) -> dict[str, float]:
    """% change of every tracked metric between two what_if outputs."""
    return {m: _pct(new, base, m) for m in METRICS}


def compute(runner, stats: list[Stat] = STATS, config: dict | None = None,
            base_mods: list[str] = ()) -> tuple[dict, list[Gradient]]:
    """runner: a PobEngine or EnginePool with the build loaded and main skill selected.
    config: Configuration tab overrides (e.g. enemy level/boss) applied to every calculation.
    base_mods: mod lines treated as already on the character (e.g. earlier steps of an upgrade path)."""
    extra = {"config": config} if config else {}
    base_mods = list(base_mods)
    calls = [{"mods": base_mods, **extra}] + [
        {"mods": base_mods + [mod_line(s, m)], **extra} for s in stats for m in (1, 2)
    ]
    if hasattr(runner, "map"):
        results = runner.map("what_if", calls)
    else:
        results = [runner.what_if(**c) for c in calls]
    base, rest = results[0], results[1:]
    grads = []
    for i, stat in enumerate(stats):
        r1, r2 = rest[2 * i], rest[2 * i + 1]
        grads.append(Gradient(stat, metric_changes(r1, base), metric_changes(r2, base)))
    return base, grads
