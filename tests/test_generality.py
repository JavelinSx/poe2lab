"""Builds unlike the Titan: an item PoB drops, a main skill PoB cannot compute, an energy shield pool."""
import re
from pathlib import Path

from poe2lab.analysis.gradients import recovery_per_second
from poe2lab.analysis.report import zero_damage_gates
from poe2lab.engine import PobEngine
from poe2lab.engine.pobcode import decode_pob_code
from poe2lab.profile import open_build

BUILDS = Path(__file__).resolve().parent / "fixtures"


def test_items_with_unknown_bases_are_reported():
    xml = decode_pob_code((BUILDS / "titan.txt").read_text(encoding="utf-8"))
    helmet_id = re.search(r'<Slot itemId="(\d+)"[^>]*name="Helmet"', xml).group(1)  # this order in the Titan's file
    item = re.search(rf'<Item id="{helmet_id}"[^>]*>(.*?)</Item>', xml, re.S).group(1)
    base = [l.strip() for l in item.strip().splitlines() if l.strip()][2]  # Rarity, name, base
    engine = PobEngine()
    engine.load_xml(xml.replace(base, "Expert Imaginary Helm"))  # a base renamed in a later game version
    unread = engine.unread_items()
    assert [(u["slot"], u["base"]) for u in unread] == [("Helmet", "Expert Imaginary Helm")]


def test_zero_damage_main_skill_points_at_the_skills_that_do_damage():
    engine, _ = open_build(BUILDS / "elemental-storm.txt")  # public build; PoB gives Elemental Storm 0 DPS
    gate = zero_damage_gates(engine, engine.what_if(), {})[0]
    assert gate.level == "must" and "Firestorm" in gate.detail
    assert engine.main_skill() == "Elemental Storm"  # the build's own choice is restored


def test_recovery_follows_the_pool_the_build_stands_on():
    es_build = {"Life": 1, "EnergyShield": 3000, "EnergyShieldRecharge": 500, "EnergyShieldRechargeDelay": 4,
                "LifeRegenRecovery": 50}
    assert recovery_per_second(es_build) == 100  # 500 / (1 + 4); life regen does not count at 1 life
    life_build = {"Life": 2000, "EnergyShield": 0, "LifeRegenRecovery": 50, "LifeLeechGainRate": 150}
    assert recovery_per_second(life_build) == 200


def test_recovery_change_is_measured_against_a_floor_of_the_pool():
    from poe2lab.analysis.gradients import RECOVERY_FLOOR, recovery_change
    base = {"Life": 3000, "EnergyShield": 0, "LifeRegenRecovery": 25}
    new = {"Life": 3000, "EnergyShield": 0, "LifeRegenRecovery": 115}  # +90/s
    assert recovery_change(new, base) == 90 / (RECOVERY_FLOOR * 3000) * 100  # +100%, not +360%
    strong = {"Life": 3000, "EnergyShield": 0, "LifeRegenRecovery": 300}
    assert recovery_change({**strong, "LifeRegenRecovery": 330}, strong) == 10  # a real base keeps plain percent


def test_the_enemy_follows_the_characters_stage():
    """A levelling character meets monsters of its level with its act's resistance penalty; from level 65, or
    when the level is unknown, the map enemy (level 79, -60%)."""
    from poe2lab.analysis.threats import MapProfile
    assert (MapProfile.for_level(7).enemy_level, MapProfile.for_level(7).resist_penalty) == (7, 0)
    assert MapProfile.for_level(40).stage == "act3" and MapProfile.for_level(40).resist_penalty == -20
    assert MapProfile.for_level(60).stage == "interlude"
    for level in (65, 95, None):
        p = MapProfile.for_level(level, rage=10)
        assert (p.enemy_level, p.resist_penalty, p.stage, p.rage) == (79, -60, "maps", 10)
    assert MapProfile.for_level(7).config()["resistancePenalty"] == 0


def test_campaign_resistances_are_a_weakness_not_broken():
    from types import SimpleNamespace
    from poe2lab.analysis.report import gates
    rec = SimpleNamespace(es_primary=False, energy_shield=0, life=1000, es_recharge=0, es_recharge_delay=2, regen=50,
                          half_life_refill_seconds=5, total=50, leech_capped_per_hit=0)
    stats = {"FireResist": 13, "ColdResist": 20, "LightningResist": 75, "LightningResistOverCap": 0, "ChaosResist": 0}
    on_maps = {g.title: g.level for g in gates(stats, [], rec)}
    levelling = {g.title: g.level for g in gates(stats, [], rec, leveling=True)}
    assert on_maps["Резист к огню не в капе"] == "must" and levelling["Резист к огню не в капе"] == "priority"
    assert "Резист к молнии без запаса" in on_maps and "Резист к молнии без запаса" not in levelling
    assert levelling["Хаос-резист ниже капа"] == "warn"
