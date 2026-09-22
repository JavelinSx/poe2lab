"""Per-build facts the user confirmed in game and corrections for mechanics PoB does not model.

Stored next to the build as builds/<name>.profile.json and applied by every command, so answers like
"Rage is always at maximum" or "mana is sustained" are given once, not per run."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .analysis.threats import MapProfile
from .engine import PobEngine

CORRECTION_BLOCK = "poe2lab corrections"
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class Correction:
    mod: str  # full-strength mod line, e.g. "Gain 30% of Damage as Extra Fire Damage"
    source: str  # why PoB misses it
    uptime: float = 1.0  # share of combat time the effect is active; numbers in `mod` are scaled by it
    confirmed: bool = False  # uptime confirmed by the user

    @property
    def line(self) -> str:
        if self.uptime >= 1:
            return self.mod
        return _NUMBER.sub(lambda m: f"{float(m.group()) * self.uptime:g}", self.mod, count=1)


@dataclass
class BuildProfile:
    group: int | None = None
    skill: int = 1
    rage: int | None = None  # None = maximum
    mana_sustained: bool = False  # confirmed in game: the main skill can be spammed
    league: str | None = None
    corrections: list[Correction] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # filled when applied
    correction_dps_pct: float = 0.0
    path: Path | None = None

    @classmethod
    def for_build(cls, build: Path) -> "BuildProfile":
        path = build.with_name(build.stem + ".profile.json")
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        main = raw.get("main_skill", {})
        return cls(
            group=main.get("group"), skill=main.get("skill", 1), rage=raw.get("rage"),
            mana_sustained=raw.get("mana_sustained", False), league=raw.get("league"),
            corrections=[Correction(**c) for c in raw.get("corrections", [])],
            notes=raw.get("notes", []), path=path,
        )


def open_build(build: Path, group: int | None = None, skill: int | None = None,
               corrections: bool = True) -> tuple[PobEngine, BuildProfile]:
    """Load a build with its profile: main skill (arguments override the profile) and corrections applied."""
    build = Path(build).resolve()
    code = build.read_text()
    profile = BuildProfile.for_build(build)
    engine = PobEngine()
    engine.load_code(code)
    group = group or profile.group
    if group:
        engine.set_main_skill(group, skill or (profile.skill if group == profile.group else 1))
    if corrections and profile.corrections:
        config = MapProfile(rage=profile.rage).config()  # same enemy as the reports, not the build's saved one
        before = engine.what_if(config=config)["CombinedDPS"]
        engine.set_custom_mods(CORRECTION_BLOCK, [c.line for c in profile.corrections])
        after = engine.what_if(config=config)["CombinedDPS"]
        profile.correction_dps_pct = (after - before) / before * 100 if before else 0.0
    return engine, profile


def describe(profile: BuildProfile) -> list[str]:
    if not profile.path:
        return ["профиль билда не найден — всё считается по данным PoB без поправок"]
    lines = [f"профиль: {profile.path.name}"]
    lines.append("свирепость: максимум" if profile.rage is None else f"свирепость: {profile.rage}")
    if profile.mana_sustained:
        lines.append("мана: держится в игре (подтверждено) — проверки дефицита маны отключены")
    for c in profile.corrections:
        up = f", аптайм {c.uptime:.0%}" + ("" if c.confirmed else " — не подтверждён")
        lines.append(f"поправка: «{c.line}» ({c.source}{up})")
    if profile.corrections:
        lines.append(f"поправки меняют DPS на {profile.correction_dps_pct:+.1f}% (против моба 79 ур.)")
    lines += [f"заметка: {n}" for n in profile.notes]
    return lines
