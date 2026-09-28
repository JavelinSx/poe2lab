"""Exact item comparison: equip a candidate (PoB text or text copied from the game) and compare with the current item."""
import re
from dataclasses import dataclass, field

from .gradients import hit_change, recovery_change, recovery_per_second

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
    # absolute values with the current item and with the candidate, for a side-by-side view
    before: dict[str, float] = field(default_factory=dict)
    after: dict[str, float] = field(default_factory=dict)


def _values(out: dict) -> dict[str, float]:
    v = {"dps": out["CombinedDPS"], "life": out["Life"], "es": out.get("EnergyShield", 0.0),
         "ehp": out.get("TotalEHP", 0.0), "recovery": recovery_per_second(out)}
    v |= {f"hit_{t}": out[f"{t}MaximumHitTaken"] for t in ("Physical", "Fire", "Cold", "Lightning", "Chaos")}
    v |= {f"res_{t}": out.get(f"{t}Resist", 0.0) for t in ("Fire", "Cold", "Lightning", "Chaos")}
    return v


def _pct(new: float, old: float) -> float:
    return (new - old) / old * 100 if old else 0.0


def compare(engine, config: dict, slot: str, item_text: str, keep_quality: bool = False) -> Comparison:
    """The item in place of the slot's. keep_quality: its quality as written (one set on purpose); otherwise below
    20% counts as 20%, as PoB takes a pasted item."""
    base = engine.what_if(config=config)
    new = engine.what_if(config=config, replace_item=(slot, item_text), keep_quality=keep_quality)
    return Comparison(
        slot,
        dps_pct=_pct(new["CombinedDPS"], base["CombinedDPS"]),
        life_pct=_pct(new["Life"], base["Life"]),
        hit_pct={t: hit_change(new, base, t) for t in ("Physical", "Fire", "Cold", "Lightning", "Chaos")},
        recovery_pct=recovery_change(new, base),
        unmet_requirements={
            a: (new.get(a, 0), new.get(f"Req{a}", 0)) for a in ATTRS  # no Req<attr> when nothing requires it
            if new.get(f"Req{a}", 0) - new.get(a, 0) > max(base.get(f"Req{a}", 0) - base.get(a, 0), 0)
        },
        before=_values(base), after=_values(new),
    )


_FLAG_LINES = ("Corrupted", "Mirrored", "Unmodifiable", "Sanctified")
_TAG = re.compile(r"^(\{[^}]*\})+")


def remove_lines(item_text: str, lines: list[str]) -> str:
    """Drop explicit mod lines (matched after stripping PoB tags like {crafted})."""
    out, todo = [], list(lines)
    for raw in item_text.split("\n"):
        plain = _TAG.sub("", raw).strip()
        if plain in todo:
            todo.remove(plain)
            continue
        out.append(raw)
    if todo:
        raise ValueError(f"lines not found in item: {todo}")
    return "\n".join(out)


def add_lines(item_text: str, lines: list[str]) -> str:
    """Append explicit mod lines, keeping trailing flags such as 'Corrupted' last."""
    rows = item_text.rstrip("\n").split("\n")
    cut = len(rows)
    while cut > 0 and rows[cut - 1].strip() in _FLAG_LINES:
        cut -= 1
    return "\n".join(rows[:cut] + list(lines) + rows[cut:])


def _scaled(line: str, factor: float) -> str:
    """Every number of the line times factor: whole numbers stay whole, decimals keep two places (7.21% leech)."""
    def one(m):
        v = float(m.group()) * factor
        return str(round(v)) if "." not in m.group() else f"{v:.2f}".rstrip("0").rstrip(".")
    return _NUMBER.sub(one, line)


def scale_line(item_text: str, line: str, factor: float) -> str:
    """Scale every number in one mod line of the item (e.g. 'Adds 26 to 42 Physical Damage'): the item's line that
    is this line (PoB tags like {crafted} aside), not every place its text occurs in."""
    rows = item_text.split("\n")
    for i, raw in enumerate(rows):
        tags = _TAG.match(raw)
        if raw[tags.end() if tags else 0:].strip() == line:
            rows[i] = raw.replace(line, _scaled(line, factor), 1)
            return "\n".join(rows)
    raise ValueError(f"line not found in item: {line!r}")


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
    return hi, _scaled(line, hi)
