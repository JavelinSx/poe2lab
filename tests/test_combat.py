"""How often the build itself keeps the enemy in a state (analysis/combat.py): from PoB's chance per hit, hits per
second and duration; Rage when the build builds it; the damage with each state for the share of the fight it holds."""
from types import SimpleNamespace

import pytest

from poe2lab.analysis import combat


def test_uptime_from_chance_hits_and_duration():
    assert combat.uptime(1.0, 1, 1) == 1.0 and combat.uptime(0, 5, 8) == 0.0
    # 10% per hit, one hit a second, 2 s: 1 - 0.9^2
    assert combat.uptime(0.1, 1, 2) == pytest.approx(0.19)
    # 80% on five hits a second for 8 s: always on
    assert combat.uptime(0.8, 5, 8) > 0.999


def test_ailments_the_main_skill_applies():
    out = {"Speed": 2.0, "HitChance": 50, "ShockChance": 10, "ShockDuration": 4, "IgniteChance": 0,
           "IgniteDuration": 4, "ChillDuration": 2}
    ups = combat.ailment_uptimes(out)
    assert set(ups) == {"conditionEnemyShocked", "conditionEnemyChilled"}  # no ignite chance: not listed
    assert ups["conditionEnemyShocked"]["uptime"] == pytest.approx(1 - 0.9 ** 4)
    assert ups["conditionEnemyChilled"]["uptime"] == 1.0  # a cold hit always chills


def test_rage_counts_when_the_build_builds_it():
    assert combat.generates_rage({"MaximumRage": 30, "RageRegen": 4}, [])
    assert combat.generates_rage({"MaximumRage": 30}, ["Gain 5 Rage on Melee Hit"])
    assert not combat.generates_rage({"MaximumRage": 30}, ["20% increased Rage effect"])
    assert not combat.generates_rage({"MaximumRage": 0, "RageRegen": 4}, [])


def test_expected_damage_between_the_ends():
    impact = lambda var, checked, pct: SimpleNamespace(var=var, checked=checked, dps_pct=pct)  # noqa: E731
    ups = {"conditionEnemyShocked": {"uptime": 0.5}, "conditionEnemyChilled": {"uptime": 0.25}}
    impacts = [impact("conditionEnemyShocked", False, 20.0),  # off in PoB: +20% if on, held half the fight
               impact("conditionEnemyChilled", True, -8.0),  # on in PoB: -8% if off, off 3/4 of the fight
               impact("conditionEnemyFrozen", False, 50.0)]  # not modelled: stays as PoB counts it
    assert combat.expected_dps(100.0, impacts, ups) == pytest.approx(100 * 1.10 * (1 - 0.75 * 0.08))
