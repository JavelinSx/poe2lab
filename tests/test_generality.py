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
