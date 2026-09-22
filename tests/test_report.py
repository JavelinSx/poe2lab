"""Report checks on the user's Titan (Furious Slam); its PoB numbers were confirmed against the game."""
import json
from pathlib import Path

import pytest

from poe2lab.analysis import attributes as attrs
from poe2lab.analysis.report import attribute_gates, build_report, defence_weights, gates, upgrade_path
from poe2lab.analysis.threats import MapProfile, recovery, survivable_hits
from poe2lab.engine import PobEngine

TITAN = (Path(__file__).resolve().parents[1] / "builds" / "titan.txt").read_text()


@pytest.fixture(scope="module")
def titan():
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(4)
    return e


def _attribute_analysis(engine, profile):
    stats = engine.what_if(config=profile.config())
    sources = engine.requirement_sources()
    statuses = attrs.status(stats, sources, engine.attribute_node_counts())
    return (statuses, attrs.node_swaps(engine, profile.config(), statuses),
            attrs.item_dependencies(engine, profile.config(), sources))


def test_attribute_status_and_cheapest_fix(titan):
    statuses, swaps, deps = _attribute_analysis(titan, MapProfile())
    by = {s.attr: s for s in statuses}
    assert (by["Dex"].have, by["Dex"].need) == (22, 25)
    assert by["Dex"].needed_by == ["5 Dexterity Support Gems"]
    assert by["Int"].from_nodes == 13
    fix = next(w for w in swaps if w.all_met)
    assert (fix.donor, fix.target, fix.nodes) == ("Str", "Dex", 1)
    assert {d.slot for d in deps} == {"Body Armour", "Boots", "Amulet", "Belt"}
    assert all(not d.breaks for d in deps)  # Strength surplus covers any single item


def test_supports_at_risk_ranks_main_skill_support_first(titan):
    risk = attrs.supports_at_risk(titan, MapProfile().config(), "Dex")
    assert len(risk) == 5
    top = risk[0]
    assert (top.name, top.skill) == ("Rapid Attacks II", "Furious Slam")
    assert top.main_dps_pct == pytest.approx(-15.6, abs=0.3)
    assert all(g["enabled"] for g in titan.gems())


def test_conditional_support_is_valued_with_its_condition(titan):
    # In game the Titan's Momentum (on Rampage) is the support switched off by the Dexterity shortfall.
    momentum = next(s for s in attrs.supports_at_risk(titan, MapProfile().config(), "Dex") if s.name == "Momentum")
    assert momentum.skill == "Rampage"
    assert momentum.conditions == ["Moved 2m during Skill use?"]
    assert momentum.skill_dps_pct == pytest.approx(-29.3, abs=0.5)
    assert titan.config().get("momentumDamage") is None


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


def test_item_dependency_detects_break():
    # Strip Strength so that the amulet alone holds the 126 Strength gem requirement.
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(4)
    profile = MapProfile()
    sources = e.requirement_sources()
    base = e.what_if(config=profile.config(), mods=["-80 to Strength"])
    assert base["Str"] >= base["ReqStr"]
    without_amulet = e.what_if(config=profile.config(), mods=["-80 to Strength"], remove_slot="Amulet")
    assert without_amulet["Str"] < without_amulet["ReqStr"]
    assert any(s["req"] > without_amulet["Str"] for s in sources if s["attr"] == "Str")


def test_gates_find_known_problems(titan):
    profile = MapProfile()
    found = attribute_gates(*_attribute_analysis(titan, profile)) + gates(
        titan.what_if(config=profile.config()), survivable_hits(titan, profile), recovery(titan, profile))
    titles = {(g.level, g.title) for g in found}
    assert ("must", "Не хватает ловкости") in titles
    assert ("warn", "Интеллект на грани") in titles
    assert ("priority", "Хаос-резист ниже капа") in titles
    assert ("priority", "Слабость к физическим ударам") in titles
    assert not any(g.title.startswith("Резист к холоду") for g in found)


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
    assert path[0].mod == "+13% to Chaos Resistance"


def test_report_is_json_serialisable(titan):
    report = build_report(titan, MapProfile(), steps=2, top=5)
    assert json.loads(json.dumps(report))["build"]["mainSkill"] == "Furious Slam"
