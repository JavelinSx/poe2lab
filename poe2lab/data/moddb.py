"""Item affix database built from PoB's game data: what can roll on a base, tiers, and which mod a line comes from.

Spawn weights in PoB's data are availability flags (0/1), not real drop weights, so this answers "can it roll"
and "which tier", not "how likely"."""
import re
from dataclasses import dataclass

_RANGE = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*\)")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def pattern(line: str) -> str:
    """Line with every number or range replaced by '#', so a roll and its mod template compare equal."""
    return _NUMBER.sub("#", _RANGE.sub("#", line)).replace("+#", "#").strip()


def ranges(line: str) -> list[tuple[float, float]]:
    """Value ranges of a mod template line, in order; a fixed number is a (n, n) range."""
    out, pos = [], 0
    for m in re.finditer(r"\(\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*\)|(-?\d+(?:\.\d+)?)", line):
        if m.group(3) is not None:
            out.append((float(m.group(3)), float(m.group(3))))
        else:
            out.append((float(m.group(1)), float(m.group(2))))
    return out


def numbers(line: str) -> list[float]:
    return [float(x) for x in _NUMBER.findall(line)]


def max_roll(line: str) -> str:
    """Template line with every range at its top value."""
    return _RANGE.sub(lambda m: _fmt(float(m.group(2))), line)


def _fmt(x: float) -> str:
    return str(int(x)) if x == int(x) else f"{x:g}"


@dataclass(frozen=True)
class Mod:
    id: str
    set: str
    type: str  # Prefix / Suffix
    affix: str
    lines: tuple[str, ...]
    level: int
    group: str
    weight_key: tuple[str, ...]
    weight_val: tuple[int, ...]
    tags: tuple[str, ...]
    trade_hashes: tuple[str, ...]

    def weight_for(self, base_tags) -> int:
        """PoE spawn rule: the first weight key present in the item's tags decides."""
        for key, val in zip(self.weight_key, self.weight_val):
            if key in base_tags:
                return val
        return 0

    @property
    def patterns(self) -> tuple[str, ...]:
        return tuple(pattern(l) for l in self.lines)

    def matches(self, rolled: list[str]) -> bool:
        """Same lines as this mod, ignoring the numbers."""
        return len(rolled) == len(self.lines) and all(pattern(t) == pattern(r) for t, r in zip(self.lines, rolled))

    def distance(self, rolled: list[str]) -> float:
        """0 if every rolled number lies inside this tier's range, otherwise how far outside (relative)."""
        total = 0.0
        for tmpl, roll in zip(self.lines, rolled):
            for (lo, hi), n in zip(ranges(tmpl), numbers(roll)):
                lo, hi = min(lo, hi), max(lo, hi)
                if n < lo:
                    total += (lo - n) / max(abs(lo), 1)
                elif n > hi:
                    total += (n - hi) / max(abs(hi), 1)
        return total


@dataclass
class Affix:
    """An explicit affix found on an item."""
    mod: Mod
    rolled: list[str]  # the item's lines for this affix
    tier: int  # game numbering: 1 = best tier that can roll on this base
    tiers: int


class ModDB:
    def __init__(self, exported: dict):
        self.mods = [
            Mod(m["id"], m["set"], m["type"], m["affix"], tuple(m["lines"]), int(m["level"]), m["group"],
                tuple(m["weightKey"]), tuple(int(v) for v in m["weightVal"]), tuple(m["tags"]), tuple(m["tradeHashes"]))
            for m in exported["mods"] if m["type"] in ("Prefix", "Suffix") and m["lines"]
        ]
        self.bases = {b["name"]: b for b in exported["bases"]}

    @classmethod
    def from_engine(cls, engine) -> "ModDB":
        return cls(engine.export_item_data())

    def rollable(self, base_tags, item_level: int = 100, sets=("Item",)) -> list[Mod]:
        tags = set(base_tags)
        return [m for m in self.mods if m.set in sets and m.level <= item_level and m.weight_for(tags) > 0]

    def tiers_of(self, mod: Mod, base_tags) -> list[Mod]:
        """All tiers of the mod's family that can roll on the base, best first."""
        tags = set(base_tags)
        family = [m for m in self.mods if m.set == mod.set and m.group == mod.group and m.patterns == mod.patterns
                  and m.weight_for(tags) > 0]
        return sorted(family, key=lambda m: -m.level)

    def best_tiers(self, base_tags, item_level: int, sets=("Item",)) -> list[Mod]:
        """For every mod family rollable on the base, its top tier allowed by the item level."""
        best: dict[tuple, Mod] = {}
        for m in self.rollable(base_tags, item_level, sets):
            key = (m.set, m.group, m.patterns)
            if key not in best or m.level > best[key].level:
                best[key] = m
        return list(best.values())

    def identify(self, lines: list[str], base_tags, item_level: int = 100,
                 sets=("Item", "Desecrated")) -> tuple[list[Affix], list[str]]:
        """Split an item's explicit lines into affixes. Multi-line (hybrid) mods are matched first.
        Returns (affixes, lines that match no rollable mod)."""
        tags = set(base_tags)
        candidates = [m for m in self.mods if m.set in sets and (m.weight_for(tags) > 0 or m.set == "Desecrated")]
        by_pattern: dict[str, list[Mod]] = {}
        for m in candidates:
            for p in m.patterns:
                by_pattern.setdefault(p, []).append(m)
        remaining = list(lines)
        affixes = []
        for size in (3, 2, 1):
            i = 0
            while i < len(remaining):
                window = remaining[i:i + size]
                if len(window) < size:
                    break
                options = [m for m in by_pattern.get(pattern(window[0]), []) if m.matches(window)]
                if options:
                    # an exact tier if one fits; otherwise the closest (values can exceed tiers via quality etc.)
                    mod = min(options, key=lambda m: (m.distance(window), -m.level))
                    family = self.tiers_of(mod, tags) or [mod]
                    tier = next((k + 1 for k, t in enumerate(family) if t.id == mod.id), len(family))
                    affixes.append(Affix(mod, window, tier, len(family)))
                    del remaining[i:i + size]
                else:
                    i += 1
        return affixes, remaining
