"""Report checks on a public Titan (Furious Slam, Rage; tests/fixtures/titan.txt)."""
import json
from pathlib import Path

import pytest

from poe2lab.analysis import attributes as attrs
from poe2lab.analysis.report import attribute_gates, build_report, defence_weights, gates, upgrade_path
from poe2lab.analysis.threats import MapProfile, recovery, survivable_hits
from poe2lab.engine import PobEngine

TITAN = (Path(__file__).resolve().parent / "fixtures" / "titan.txt").read_text()
FURIOUS_SLAM = 5


@pytest.fixture(scope="module")
def titan():
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(FURIOUS_SLAM)
    return e


@pytest.fixture(scope="module")
def short_on_dex():
    """The same Titan 10 Dexterity short of its gems' needs (73 of 70 in the build)."""
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(FURIOUS_SLAM)
    e.set_custom_mods("test", ["-10 to Dexterity"])
    return e


def _attribute_analysis(engine, profile):
    stats = engine.what_if(config=profile.config())
    sources = engine.requirement_sources()
    statuses = attrs.status(stats, sources, engine.attribute_node_counts())
    return (statuses, attrs.node_swaps(engine, profile.config(), statuses),
            attrs.item_dependencies(engine, profile.config(), sources))


def test_attribute_status_and_cheapest_fix(short_on_dex):
    statuses, swaps, _ = _attribute_analysis(short_on_dex, MapProfile())
    by = {s.attr: s for s in statuses}
    assert (by["Dex"].have, by["Dex"].need) == (63, 70)
    assert "Herald of Ice 17/20" in by["Dex"].needed_by
    assert by["Str"].margin > 40  # a Strength surplus to move from
    fix = next(w for w in swaps if w.all_met)
    assert (fix.donor, fix.target) == ("Str", "Dex") and fix.nodes >= 1


def test_supports_at_risk_ranks_main_skill_support_first(titan):
    risk = attrs.supports_at_risk(titan, MapProfile().config(), "Dex")
    top = risk[0]
    assert (top.name, top.skill) == ("Rapid Attacks II", "Furious Slam")
    assert top.main_dps_pct == pytest.approx(-16.3, abs=0.5)
    assert [r.main_dps_pct for r in risk] == sorted(r.main_dps_pct for r in risk)  # biggest loss first
    assert all(g["enabled"] for g in titan.gems())


def test_conditions_audit_flips_each_box_and_restores(titan):
    from poe2lab.analysis.conditions import audit
    cfg = MapProfile().config()
    before = titan.what_if(config=cfg)
    found = {c.label: c for c in audit(titan, cfg)}
    heavy = found["Is the enemy Heavy Stunned?"]
    assert not heavy.checked and heavy.dps_pct > 0
    quest = found["Interlude 2: Khari Crossing"]
    assert quest.checked and quest.life_pct < 0
    after = titan.what_if(config=cfg)
    assert after["CombinedDPS"] == pytest.approx(before["CombinedDPS"]) and after["Life"] == before["Life"]


def test_damage_range_brackets_enemy_debuffs(titan):
    from poe2lab.analysis.conditions import audit, damage_range
    cfg = MapProfile().config()
    rng = damage_range(titan, cfg, audit(titan, cfg))
    assert rng["high"] > rng["low"] == pytest.approx(titan.what_if(config=cfg)["CombinedDPS"])
    assert "Is the enemy Heavy Stunned?" in rng["conditions"]
    assert not any("Adrenaline" in c for c in rng["conditions"])  # player buffs are not enemy debuffs


def test_energy_shield_build_gets_es_recovery_not_infinity():
    from poe2lab.profile import open_build
    engine, _ = open_build("monk")
    profile = MapProfile()
    rec = recovery(engine, profile)
    assert rec.es_primary and rec.es_recharge > 0 and rec.half_life_refill_seconds is None
    found = gates(engine.what_if(config=profile.config()), survivable_hits(engine, profile), rec)
    texts = " ".join(g.title + g.detail for g in found)
    assert "энергощит" in texts and "inf" not in texts


def test_item_dependency_detects_break(titan):
    # The helmet carries the Dexterity and Intelligence that just cover the gems (margin 3 each).
    deps = {d.slot: d for d in attrs.item_dependencies(titan, MapProfile().config(), titan.requirement_sources())}
    assert any("Furious Slam" in b for b in deps["Helmet"].breaks)


def test_gates_find_known_problems(titan, short_on_dex):
    profile = MapProfile()

    def titles(engine):
        found = attribute_gates(*_attribute_analysis(engine, profile)) + gates(
            engine.what_if(config=profile.config()), survivable_hits(engine, profile), recovery(engine, profile))
        return {(g.level, g.title) for g in found}

    ok = titles(titan)
    assert ("warn", "Интеллект на грани") in ok
    assert ("priority", "Слабость к физическим ударам") in ok
    assert not any(level == "must" and "ловкост" in t for level, t in ok)
    assert ("must", "Не хватает ловкости") in titles(short_on_dex)


def test_weaker_types_weigh_more(titan):
    w = defence_weights(survivable_hits(titan, MapProfile()))
    assert w["Physical"] > w["Chaos"] > w["Fire"]
    assert sum(w.values()) == pytest.approx(1)


def test_upgrade_path_uses_each_stat_once(titan):
    profile = MapProfile()
    w = defence_weights(survivable_hits(titan, profile))
    path = upgrade_path(titan, profile, "defence", 5, w)
    mods = [s.mod for s in path]
    assert len(mods) == len(set(mods)) == 5
    assert any(v > 0 for v in path[-1].total_defence.values()) or path[-1].total_recovery > 0


def test_report_is_json_serialisable(titan):
    report = build_report(titan, MapProfile(), steps=2, top=5)
    assert json.loads(json.dumps(report))["build"]["mainSkill"] == "Furious Slam"


def test_a_much_stronger_skill_than_the_main_one_is_pointed_out():
    """Every damage advice is counted for the chosen main skill: when another skill of the build hits several times
    harder, the overview says so (a guide's build can come with a secondary skill chosen as the main one)."""
    from types import SimpleNamespace
    from poe2lab.analysis.report import zero_damage_gates
    engine = SimpleNamespace(main_skill=lambda: "Glacial Cascade", skill_damage=lambda config: [
        {"name": "Ice Strike", "dps": 774.0}, {"name": "Glacial Cascade", "dps": 218.0}])
    gates = zero_damage_gates(engine, {"CombinedDPS": 218.0}, {})
    assert len(gates) == 1 and gates[0].level == "warn" and "Ice Strike" in gates[0].title and gates[0].title_en
    close = SimpleNamespace(main_skill=lambda: "Glacial Cascade", skill_damage=lambda config: [
        {"name": "Ice Strike", "dps": 300.0}, {"name": "Glacial Cascade", "dps": 218.0}])
    assert zero_damage_gates(close, {"CombinedDPS": 218.0}, {}) == []  # not that much stronger: nothing to say
