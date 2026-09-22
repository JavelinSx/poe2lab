"""Exact item comparison: equip a candidate (PoB text or text copied from the game) and compare with the current item."""
import re
from dataclasses import dataclass, field

from .gradients import recovery_per_second

ATTRS = ("Str", "Dex", "Int")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class Comparison:
    slot: str
    dps_pct: float
    life_pct: float
    hit_pct: dict[str, float]  # survivable hit change per damage type
    recovery_pct: float
    # attr -> (have, need): shortfalls the candidate creates or deepens (an existing shortfall alone is not listed)
    unmet_requirements: dict[str, tuple[float, float]] = field(default_factory=dict)


def _pct(new: float, old: float) -> float:
    return (new - old) / old * 100 if old else 0.0


def compare(engine, config: dict, slot: str, item_text: str) -> Comparison:
    base = engine.what_if(config=config)
    new = engine.what_if(config=config, replace_item=(slot, item_text))
    return Comparison(
        slot,
        dps_pct=_pct(new["CombinedDPS"], base["CombinedDPS"]),
        life_pct=_pct(new["Life"], base["Life"]),
        hit_pct={t: _pct(new[f"{t}MaximumHitTaken"], base[f"{t}MaximumHitTaken"])
                 for t in ("Physical", "Fire", "Cold", "Lightning", "Chaos")},
        recovery_pct=_pct(recovery_per_second(new), recovery_per_second(base)),
        unmet_requirements={
            a: (new[a], new[f"Req{a}"]) for a in ATTRS
            if new[f"Req{a}"] - new[a] > max(base[f"Req{a}"] - base[a], 0)
        },
    )


def scale_line(item_text: str, line: str, factor: float) -> str:
    """Scale every number in one mod line of the item (e.g. 'Adds 26 to 42 Physical Damage')."""
    if line not in item_text:
        raise ValueError(f"line not found in item: {line!r}")
    scaled = _NUMBER.sub(lambda m: str(round(float(m.group()) * factor)), line)
    return item_text.replace(line, scaled)


def breakeven(engine, config: dict, slot: str, item_text: str, line: str, iterations: int = 20) -> tuple[float, str] | None:
    """How far `line` on the candidate can shrink before the candidate stops beating the current item.
    Returns (factor, scaled line), or None if the candidate is worse even at full value."""
    target = engine.what_if(config=config)["CombinedDPS"]
    dps = lambda f: engine.what_if(config=config, replace_item=(slot, scale_line(item_text, line, f)))["CombinedDPS"]
    if dps(1.0) < target:
        return None
    lo, hi = 0.0, 1.0
    if dps(0.0) >= target:
        return 0.0, _NUMBER.sub("0", line)
    for _ in range(iterations):
        mid = (lo + hi) / 2
        if dps(mid) >= target:
            hi = mid
        else:
            lo = mid
    return hi, _NUMBER.sub(lambda m: str(round(float(m.group()) * hi)), line)
