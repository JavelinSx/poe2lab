"""Stats to probe. Each unit is sized like one mid-tier affix, so rows compare "one mod of X" against "one mod of Y".
The table is the knob to tune: PoB must be able to parse every line (see tests)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Stat:
    key: str
    label: str
    mod: str  # one unit; "{n}" is replaced by the multiple for the second step
    unit: float
    group: str


def _s(key, label, template, unit, group):
    return Stat(key, label, template, unit, group)


STATS: list[Stat] = [
    # offence: generic
    _s("inc_damage", "% increased Damage", "{v}% increased Damage", 20, "offence"),
    _s("inc_attack_damage", "% increased Attack Damage", "{v}% increased Attack Damage", 20, "offence"),
    _s("inc_melee_damage", "% increased Melee Damage", "{v}% increased Melee Damage", 20, "offence"),
    _s("inc_area_damage", "% increased Area Damage", "{v}% increased Area Damage", 20, "offence"),
    _s("inc_phys", "% increased Physical Damage", "{v}% increased Physical Damage", 20, "offence"),
    _s("inc_elemental", "% increased Elemental Damage", "{v}% increased Elemental Damage", 20, "offence"),
    _s("inc_fire", "% increased Fire Damage", "{v}% increased Fire Damage", 20, "offence"),
    _s("inc_cold", "% increased Cold Damage", "{v}% increased Cold Damage", 20, "offence"),
    _s("inc_lightning", "% increased Lightning Damage", "{v}% increased Lightning Damage", 20, "offence"),
    _s("attack_speed", "% increased Attack Speed", "{v}% increased Attack Speed", 8, "offence"),
    _s("crit_chance", "% increased Critical Hit Chance", "{v}% increased Critical Hit Chance", 25, "offence"),
    _s("crit_damage", "% increased Critical Damage Bonus", "{v}% increased Critical Damage Bonus", 20, "offence"),
    _s("accuracy_flat", "+ Accuracy Rating", "+{v} to Accuracy Rating", 150, "offence"),
    _s("accuracy_inc", "% increased Accuracy Rating", "{v}% increased Accuracy Rating", 20, "offence"),
    _s("added_phys_attacks", "Adds Physical Damage to Attacks", "Adds {v} to {v2} Physical Damage to Attacks", 10, "offence"),
    _s("added_fire_attacks", "Adds Fire Damage to Attacks", "Adds {v} to {v2} Fire Damage to Attacks", 10, "offence"),
    _s("added_cold_attacks", "Adds Cold Damage to Attacks", "Adds {v} to {v2} Cold Damage to Attacks", 10, "offence"),
    _s("added_lightning_attacks", "Adds Lightning Damage to Attacks", "Adds {v} to {v3} Lightning Damage to Attacks", 5, "offence"),
    _s("gain_fire", "% of Damage as extra Fire", "Gain {v}% of Damage as Extra Fire Damage", 8, "offence"),
    _s("melee_levels", "+ Level of all Melee Skills", "+{v} to Level of all Melee Skills", 1, "offence"),
    _s("aoe", "% increased Area of Effect", "{v}% increased Area of Effect", 15, "offence"),
    _s("max_rage", "+ Maximum Rage", "+{v} to Maximum Rage", 5, "offence"),
    # spells
    _s("inc_spell", "% increased Spell Damage", "{v}% increased Spell Damage", 25, "offence"),
    _s("cast_speed", "% increased Cast Speed", "{v}% increased Cast Speed", 8, "offence"),
    _s("spell_levels", "+ Level of all Spell Skills", "+{v} to Level of all Spell Skills", 1, "offence"),
    _s("spell_crit", "% increased Critical Hit Chance for Spells", "{v}% increased Critical Hit Chance for Spells", 30, "offence"),
    # projectiles, damage over time, chaos
    _s("inc_projectile", "% increased Projectile Damage", "{v}% increased Projectile Damage", 20, "offence"),
    _s("projectile_levels", "+ Level of all Projectile Skills", "+{v} to Level of all Projectile Skills", 1, "offence"),
    _s("inc_chaos", "% increased Chaos Damage", "{v}% increased Chaos Damage", 20, "offence"),
    _s("inc_dot", "% increased Damage over Time", "{v}% increased Damage over Time", 20, "offence"),
    # minions
    _s("minion_damage", "Minions deal % increased Damage", "Minions deal {v}% increased Damage", 25, "offence"),
    _s("minion_speed", "Minions have % increased Attack and Cast Speed",
       "Minions have {v}% increased Attack and Cast Speed", 8, "offence"),
    _s("minion_levels", "+ Level of all Minion Skills", "+{v} to Level of all Minion Skills", 1, "offence"),
    _s("minion_life", "Minions have % increased maximum Life", "Minions have {v}% increased maximum Life", 20, "defence"),
    # charges
    _s("power_charges", "+ maximum Power Charges", "+{v} to Maximum Power Charges", 1, "offence"),
    _s("frenzy_charges", "+ maximum Frenzy Charges", "+{v} to Maximum Frenzy Charges", 1, "offence"),
    _s("endurance_charges", "+ maximum Endurance Charges", "+{v} to Maximum Endurance Charges", 1, "defence"),
    _s("str", "+ Strength", "+{v} to Strength", 20, "attributes"),
    _s("dex", "+ Dexterity", "+{v} to Dexterity", 20, "attributes"),
    _s("int", "+ Intelligence", "+{v} to Intelligence", 20, "attributes"),
    # defence
    _s("life_flat", "+ maximum Life", "+{v} to maximum Life", 80, "defence"),
    _s("life_inc", "% increased maximum Life", "{v}% increased maximum Life", 8, "defence"),
    _s("armour_flat", "+ Armour", "+{v} to Armour", 300, "defence"),
    _s("armour_inc", "% increased Armour", "{v}% increased Armour", 40, "defence"),
    _s("evasion_flat", "+ Evasion Rating", "+{v} to Evasion Rating", 300, "defence"),
    _s("es_flat", "+ maximum Energy Shield", "+{v} to maximum Energy Shield", 60, "defence"),
    _s("es_inc", "% increased maximum Energy Shield", "{v}% increased maximum Energy Shield", 15, "defence"),
    _s("evasion_inc", "% increased Evasion Rating", "{v}% increased Evasion Rating", 40, "defence"),
    _s("fire_res", "+% Fire Resistance", "+{v}% to Fire Resistance", 20, "defence"),
    _s("cold_res", "+% Cold Resistance", "+{v}% to Cold Resistance", 20, "defence"),
    _s("lightning_res", "+% Lightning Resistance", "+{v}% to Lightning Resistance", 20, "defence"),
    _s("chaos_res", "+% Chaos Resistance", "+{v}% to Chaos Resistance", 13, "defence"),
    _s("max_fire_res", "+% maximum Fire Resistance", "+{v}% to Maximum Fire Resistance", 1, "defence"),
    _s("block", "+% Block chance", "+{v}% to Block chance", 5, "defence"),
    _s("phys_as_fire", "% phys taken as Fire", "{v}% of Physical Damage from Hits taken as Fire Damage", 10, "defence"),
    _s("life_regen", "Life Regeneration per second", "Regenerate {v} Life per second", 30, "defence"),
    # recovery
    _s("life_on_hit", "Life per enemy Hit with Attacks", "Gain {v} Life per Enemy Hit with Attacks", 10, "recovery"),
    _s("life_recovery_rate", "% increased Life Recovery rate", "{v}% increased Life Recovery rate", 10, "recovery"),
    _s("life_regen_pct", "% of maximum Life regenerated per second", "Regenerate {v}% of maximum Life per second", 1, "recovery"),
    _s("life_recoup", "% of Damage taken Recouped as Life", "{v}% of Damage taken Recouped as Life", 10, "recovery"),
    _s("life_leech_amount", "% increased amount of Life Leeched", "{v}% increased amount of Life Leeched", 10, "recovery"),
    _s("life_leech", "% of Physical Attack Damage Leeched as Life", "Leech {v}% of Physical Attack Damage as Life", 5, "recovery"),
]


def mod_line(stat: Stat, multiple: int = 1) -> str:
    v = stat.unit * multiple
    fmt = lambda x: f"{x:g}"
    return stat.mod.format(v=fmt(v), v2=fmt(v * 2), v3=fmt(v * 4))
