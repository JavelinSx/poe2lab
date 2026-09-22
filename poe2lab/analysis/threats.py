"""What can kill the character on maps: survivable monster hit per damage type, and life recovery.

PoB has no data on real PoE2 monster skill damage, so this reports the largest monster hit you survive
(before map modifiers) instead of guessing what monsters actually deal."""
from dataclasses import dataclass

DAMAGE_TYPES = ["Physical", "Fire", "Cold", "Lightning", "Chaos"]
BASE_MONSTER_CRIT_BONUS = 30  # data.monsterConstants.base_critical_hit_damage_bonus


@dataclass
class MapProfile:
    enemy_level: int = 79  # area level of a tier 15 waystone
    boss: str = "None"  # PoB enemyIsBoss: None / Boss / Pinnacle / Uber
    damage_pct: float = 50  # map/juice "monsters deal increased damage"
    crit_bonus: float = 50  # map/juice extra monster critical damage bonus
    rage: int | None = None  # current Rage in combat; None = maximum (PoB caps it). No effect on builds without Rage
    mana_sustained: bool = False  # confirmed in game: mana is not a constraint, skip mana-deficit checks

    def config(self, crit: bool = False, crit_bonus: float = 0) -> dict:
        cfg = {"enemyLevel": self.enemy_level, "enemyIsBoss": self.boss,
               "multiplierRage": 9999 if self.rage is None else self.rage}
        if crit:
            cfg |= {"enemyCritChance": 100, "enemyCritDamage": BASE_MONSTER_CRIT_BONUS + crit_bonus}
        return cfg


@dataclass
class HitRow:
    damage_type: str
    normal: float  # largest monster base hit survived from full life
    crit: float  # same, if the hit crits
    juiced: float  # crit on a map with profile.damage_pct / crit_bonus


def survivable_hits(engine, profile: MapProfile) -> list[HitRow]:
    normal = engine.what_if(config=profile.config())
    crit = engine.what_if(config=profile.config(crit=True))
    juice_mods = [f"{profile.damage_pct:g}% increased Damage"] if profile.damage_pct else []
    juiced = engine.what_if(config=profile.config(crit=True, crit_bonus=profile.crit_bonus), enemy_mods=juice_mods)
    rows = []
    for t in DAMAGE_TYPES:
        key = f"{t}MaximumHitTaken"
        # MaximumHitTaken already includes enemy damage mods but not the crit multiplier.
        rows.append(HitRow(t, normal[key], crit[key] / crit["EnemyCritEffect"], juiced[key] / juiced["EnemyCritEffect"]))
    return rows


@dataclass
class Recovery:
    life: float
    leech: float  # includes life on hit
    regen: float
    recoup: float
    leech_capped_per_hit: bool
    energy_shield: float = 0.0
    es_recharge: float = 0.0  # per second once recharge starts
    es_recharge_delay: float = 0.0  # seconds without taking damage before recharge starts

    @property
    def total(self) -> float:
        """Life regained per second while fighting (leech, regeneration, recoup)."""
        return self.leech + self.regen + self.recoup

    @property
    def half_life_refill_seconds(self) -> float | None:
        """None when life does not come back at all in combat (only flasks)."""
        return self.life * 0.5 / self.total if self.total else None

    @property
    def es_primary(self) -> bool:
        """Energy shield is the larger part of the pool, so it is what gets restored between hits."""
        return self.energy_shield > self.life


def recovery(engine, profile: MapProfile) -> Recovery:
    out = engine.what_if(config=profile.config())
    per_hit, cap = out.get("LifeLeechPerHit", 0.0), out.get("MaxLifeLeechInstance", 0.0)
    return Recovery(
        life=out["Life"],
        leech=out.get("LifeLeechGainRate", 0.0),
        regen=out.get("LifeRegenRecovery", 0.0),
        recoup=out.get("LifeRecoupRecoveryAvg", 0.0),
        leech_capped_per_hit=cap > 0 and per_hit >= cap * 0.999,
        energy_shield=out.get("EnergyShield", 0.0),
        es_recharge=out.get("EnergyShieldRecharge", 0.0),
        es_recharge_delay=out.get("EnergyShieldRechargeDelay", 0.0),
    )
