"""The build's target (a guide at its end game) next to the character now: where each gets its power, for the
assistant to tell what matters at this stage from what the build maxes later."""
import json
from pathlib import Path

import pytest

from poe2lab.analysis import target as tg
from poe2lab.analysis.threats import MapProfile
from poe2lab.assistant.agent import build_context
from poe2lab.assistant.tools import Toolbox
from poe2lab.profile import BuildProfile, open_build

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def monk():
    engine, bp = open_build(FIXTURES / "monk.txt")
    return engine, MapProfile.for_level(engine.info()["level"], rage=bp.rage, mana_sustained=bp.mana_sustained)


@pytest.fixture(scope="module")
def titan():
    engine, bp = open_build(FIXTURES / "titan.txt")
    return engine, MapProfile(rage=bp.rage, mana_sustained=bp.mana_sustained), bp


def test_where_the_power_comes_from(monk):
    engine, profile = monk
    groups = tg.investments(engine, profile.config())
    assert groups and all(g["nodes"] >= tg.MIN_NODES for g in groups)
    worth = [abs(g["dps"]) + abs(g["ehp"]) for g in groups]
    assert worth == sorted(worth, reverse=True)
    crit = next(g for g in groups if g["key"] == "crit")  # the public monk is a crit build
    assert crit["dps"] < -10
    # a keystone is not a group member: taking it away is another build, not "less crit"
    assert all(g["dps"] > -99 for g in groups)


def test_the_assistant_sees_both_pictures(monk, titan):
    t_engine, t_profile = monk
    engine, profile, bp = titan
    now = tg.summary(engine, profile.config(), "titan")
    target = tg.summary(t_engine, t_profile.config(), "monk guide")
    text = tg.context_text(now, target)
    assert "Цель билда" in text and "«monk guide»" in text and "Сейчас:" in text and "пассивок" in text
    context = build_context(engine, bp, None, profile.config(), text)
    assert "Цель билда — гайд" in context and "monk guide" in context
    box = Toolbox(engine, profile, target={"name": "monk guide", "engine": t_engine, "profile": t_profile})
    report = json.loads(box.call("target_report", {}))
    assert report["target"]["name"] == "monk guide" and report["now"]["level"] == engine.info()["level"]
    on_target = json.loads(box.call("evaluate_mods_on_target", {"mods": ["25% increased Critical Hit Chance"]}))
    assert on_target["target"] == "monk guide" and on_target["percentChange"]["dps"] > 0
    lonely = Toolbox(engine, profile)
    assert "error" in json.loads(lonely.call("target_report", {}))


def test_the_profile_names_the_target(tmp_path):
    build = tmp_path / "mine.txt"
    build.write_text("code", encoding="utf-8")
    (tmp_path / "mine.profile.json").write_text(json.dumps({"target": "Гайд X"}), encoding="utf-8")
    assert BuildProfile.for_build(build).target == "Гайд X"
