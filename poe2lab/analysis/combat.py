"""How often the build itself keeps the enemy in a state PoB asks about, from PoB's own numbers for the main skill.

PoB's Configuration asks yes or no ("Is the enemy Shocked?"); in a fight the answer is "this share of the time". For
the ailments PoB gives a chance per hit and a duration: with the main skill's hits per second, the chance that at
least one hit of the last `duration` seconds applied it is the share of the fight the enemy has it:
    uptime = 1 - (1 - chance) ** (hits per second * duration)
Cold hits always chill (PoB gives a chill duration only when the skill can chill). Rage: a build that generates it
(regeneration, "gain Rage on hit") fights at its maximum.

A rough model - one enemy, the main skill hitting all the time - but it moves the right way: a 10% shock chance on a
slow skill is not "shocked", 80% on five hits a second is."""
import re

# Configuration checkbox -> (PoB's chance per hit in %, or None: always on a hit that can apply it; its duration)
AILMENTS = {
    "conditionEnemyShocked": ("ShockChance", "ShockDuration"),
    "conditionEnemyIgnited": ("IgniteChance", "IgniteDuration"),
    "conditionEnemyBleeding": ("BleedChance", "BleedDuration"),
    "conditionEnemyPoisoned": ("PoisonChance", "PoisonDuration"),
    "conditionEnemyChilled": (None, "ChillDuration"),
}
HELD = 0.5  # from this share of the fight on, a yes/no setting is answered "yes"
_RAGE_TEXT = re.compile(r"\b(gain|gains|grant|grants|generate|generates)\b[^.;]{0,50}?\brage\b", re.I)


def uptime(chance: float, hits_per_second: float, duration: float) -> float:
    """The share of the fight an effect with this chance per hit (0..1) and duration holds."""
    if chance <= 0 or hits_per_second <= 0 or duration <= 0:
        return 0.0
    if chance >= 1:
        return 1.0
    return 1 - (1 - chance) ** (hits_per_second * duration)


def ailment_uptimes(out: dict) -> dict[str, dict]:
    """Configuration checkbox -> {uptime, chance, duration} for each ailment the main skill applies (PoB's output of
    a calculation), the ones it cannot apply left out."""
    hits = (out.get("Speed") or 0) * (out.get("HitChance") or 0) / 100
    found = {}
    for var, (chance_key, duration_key) in AILMENTS.items():
        duration = out.get(duration_key) or 0
        chance = 1.0 if chance_key is None else min(1.0, (out.get(chance_key) or 0) / 100)
        if duration <= 0 or chance <= 0:
            continue
        found[var] = {"uptime": uptime(chance, hits, duration), "chance": chance, "duration": duration}
    return found


def generates_rage(out: dict, lines) -> bool:
    """The build builds Rage itself: it regenerates it, or a gem, passive or item line gains it."""
    return (out.get("MaximumRage") or 0) > 0 and ((out.get("RageRegen") or 0) > 0
                                                  or any(_RAGE_TEXT.search(line) for line in lines))


def expected_dps(base: float, impacts, uptimes: dict[str, dict]) -> float:
    """Damage with each ailment counted for the share of the fight it holds, not all or nothing: a condition PoB
    counts as off adds its gain times its uptime, one it counts as on loses its gain for the time it does not hold.
    Conditions this model does not cover stay as PoB counts them. `impacts`: poe2lab.analysis.conditions.audit."""
    factor = 1.0
    for c in impacts:
        u = uptimes.get(c.var)
        if u is None:
            continue
        if c.checked:  # dps_pct: the loss if it were off
            factor *= 1 + (1 - u["uptime"]) * c.dps_pct / 100
        else:  # dps_pct: the gain if it were on
            factor *= 1 + u["uptime"] * c.dps_pct / 100
    return base * factor
