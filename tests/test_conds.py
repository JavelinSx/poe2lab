"""The build's conditions (poe2lab.analysis.conds): a line's condition by its words, the share of the fight the
program can tell, the player's answer over it, the damage with every condition at its share."""
from conftest import FIXTURES

from poe2lab.analysis import conds
from poe2lab.knowledge import Gap


def test_a_lines_condition_by_its_words():
    assert conds.condition_of("20% increased Damage if you've Killed Recently")["var"] == "conditionKilledRecently"
    assert conds.condition_of("Hits against Frozen enemies deal 30% more damage")["var"] == "conditionEnemyFrozen"
    assert conds.condition_of("40% increased Critical Hit Chance while on Low Life")["var"] == "conditionLowLife"
    # an event with an effect for a while after it
    ev = conds.condition_of("When you Freeze a target with Supported Skills, you deal 1% more Damage for 15 seconds")
    assert ev["event"] == "freeze" and ev["seconds"] == 15
    assert conds.condition_of("+20 to maximum Life") is None


def test_the_share_the_program_can_tell():
    out = {"Speed": 2.0, "HitChance": 100, "CritChance": 30, "ShockChance": 20, "ShockDuration": 4, "Life": 1000}
    shock = conds.suggest("conditionEnemyShocked", out)
    assert shock["how"] == "ailment" and 0.8 < shock["uptime"] < 0.9  # 1 - 0.8 ** (2 * 4)
    assert conds.suggest("conditionHitRecently", out)["uptime"] > 0.99
    assert 0.9 < conds.suggest("conditionCritRecently", out)["uptime"] < 0.92  # 1 - e^(-2 * 0.3 * 4)
    assert conds.suggest("conditionKilledRecently", out, boss=True)["uptime"] == 0
    assert conds.suggest("conditionLowLife", out | {"LifeReserved": 800})["uptime"] == 1
    assert conds.suggest("conditionMoving", out) is None  # the player's answer only


def test_damage_with_every_condition_at_its_share():
    # off in PoB, +20% if always, half the fight: +10%; on in PoB, -30% if never, 80% of the fight: -6%
    assert round(conds.combine(100, [(20, 0.5, False), (-30, 0.8, True)]), 6) == round(100 * 1.1 * 0.94, 6)
    impacts = [{"var": "conditionEnemyShocked", "label": "Is the enemy Shocked?", "checked": True, "dps_pct": -20,
                "phys_hit_pct": 0, "ele_hit_pct": 0, "chaos_hit_pct": 0, "recovery_pct": 0, "life_pct": 0}]
    out = {"CombinedDPS": 1000, "Speed": 1.0, "HitChance": 100, "ShockChance": 50, "ShockDuration": 2}
    gap = Gap("item", "Ring (Ring 1)", "x", "Shocked enemies take 10% increased damage", True)
    src = [{"var": "conditionEnemyShocked", "source": {"kind": "Item", "name": "Ring"}},
           {"var": "conditionEnemyShocked", "source": {"kind": "Base", "name": "Base"}}]
    v = conds.view(impacts, src, out, {}, [gap])
    row = v["conditions"][0]
    assert row["share"] == 0.75 and row["sources"] == [{"kind": "Item", "name": "Ring"}] and len(row["lines"]) == 1
    assert v["dps"]["expected"] == 1000 * (1 + 0.25 * -20 / 100)
    # the player's answer takes the estimate's place
    assert conds.view(impacts, src, out, {"conditionEnemyShocked": 1.0}, [])["dps"]["expected"] == 1000


def test_where_a_condition_comes_from_on_a_build():
    from poe2lab.engine import PobEngine
    e = PobEngine()
    e.load_code((FIXTURES / "monk.txt").read_text(encoding="utf-8").strip())
    rows = e.condition_sources()
    low = [r for r in rows if r["var"] == "conditionLowLife" and r["source"]["kind"] == "Tree"]
    assert any(r["source"]["name"] == "Killer Instinct" for r in low)
