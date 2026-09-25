"""The game's build planner format (.build: what Mobalytics and PoB's exporter write) as a PoB build."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poe2lab import buildplanner, library
from poe2lab.engine import PobEngine

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# a small plan in the format, as Mobalytics writes it: numbered mods, a unique by unique_name
PLAN = {
    "name": "Test - [0.5.5] Ice Strike", "author": "someone", "ascendancy": "Monk2",
    "passives": [{"id": "passive_keystone_hollow_palm_technique"}, {"id": "dexterity5"}, {"id": "attributes28"},
                 {"id": "AscendancyMonk2Start"}, {"id": "AscendancyMonk2Notable6"}],
    "skills": [{"id": "Metadata/Items/Gems/SkillGemIceStrike",
                "support_skills": [{"id": "Metadata/Items/Gems/SupportGemCloseCombat"}]}],
    "inventory_slots": [
        {"inventory_id": "Ring1", "slot_x": 0,
         "additional_text": "Breach Ring\n1. Adds 1 to 28 Lightning damage to Attacks\n2. Adds 21 to 32 Cold damage to Attacks"},
        {"inventory_id": "Belt1", "slot_x": 0, "unique_name": "Ingenuity"},
    ],
}


def test_parse_and_item_text():
    assert buildplanner.parse(json.dumps(PLAN))["ascendancy"] == "Monk2"
    assert buildplanner.parse("eNrtfWlz2zi...") is None and buildplanner.parse('{"a": 1}') is None
    assert buildplanner.item_lines("Kamasan Tiara\n1. +34 to maximum Energy Shield\n2. 95% increased Energy Shield") == [
        "Kamasan Tiara", "+34 to maximum Energy Shield", "95% increased Energy Shield"]
    # PoB's export: a coloured bold header with the name and the base, mod lines in colour
    assert buildplanner.item_lines("<rgb(255,255,119)>{<b>{Grim Grip\nBreach Ring}}\n<rgb(136,136,255)>{+20 to Dexterity}") == [
        "Grim Grip", "Breach Ring", "+20 to Dexterity"]
    assert buildplanner._middle("+(20-30) to maximum Life") == "+25 to maximum Life"
    bases = {"Breach Ring": {"implicit": "Maximum Quality is (40-50)%"}, "Utility Belt": {}}
    uniques = {"Ingenuity": "Ingenuity\nUtility Belt\n..."}
    # the base found among the lines; its implicit from the text when listed there, else at the middle
    listed = buildplanner.item_text({"additional_text": "Grim Grip\nBreach Ring\nMaximum Quality is 47%\n+20 to Dexterity"},
                                    bases, uniques)
    assert listed.splitlines()[2:] == ["Breach Ring", "Item Level: 82", "Implicits: 1", "Maximum Quality is 47%",
                                       "+20 to Dexterity"]
    middle = buildplanner.item_text({"additional_text": "Breach Ring\n1. +20 to Dexterity"}, bases, uniques)
    assert "Maximum Quality is 45%" in middle
    # a unique by its name, with or without unique_name
    assert buildplanner.item_text({"unique_name": "Ingenuity"}, bases, uniques).startswith("Rarity: UNIQUE\nIngenuity")
    assert buildplanner.item_text({"additional_text": "Ingenuity\nUtility Belt\n+5 to x"}, bases, uniques).startswith(
        "Rarity: UNIQUE")


@pytest.fixture(scope="module")
def roundtrip():
    """A public build exported by PoB's own exporter to the planner format, then imported back."""
    source = PobEngine()
    source.load_code((FIXTURES / "monk.txt").read_text())
    plan = buildplanner.export(source, "monk")
    engine = PobEngine()
    code, report = buildplanner.to_code(plan, engine)
    return source, engine, code, report, json.loads(plan)


def test_a_build_exported_by_pob_comes_back(roundtrip):
    source, engine, code, report, plan = roundtrip
    assert report["missing"] == [] and len(report["worn"]) == len(plan["inventory_slots"])
    assert (engine.info()["class"], engine.info()["ascendancy"]) == (source.info()["class"], source.info()["ascendancy"])
    assert {n["id"] for n in engine.allocated_nodes()} == {n["id"] for n in source.allocated_nodes()}
    assert {g["name"] for g in engine.skill_damage()} >= {g["name"] for g in source.skill_damage() if g["dps"] > 0}
    # the format has no jewels, runes, quality or PoB's configuration (charges, the enemy's state): the numbers are
    # not the source's - what the import report says; the main skill is the one dealing the most damage
    assert engine.main_skill() == engine.skill_damage()[0]["name"]
    again = PobEngine()
    again.load_code(code)  # an ordinary PoB code: the same numbers once loaded again
    assert again.stats()["CombinedDPS"] == pytest.approx(engine.stats()["CombinedDPS"], rel=1e-6)


def test_added_from_the_interface(tmp_path, monkeypatch):
    from poe2lab.web.server import app, session
    monkeypatch.setattr(library, "PROJECT_BUILDS", tmp_path)
    monkeypatch.setattr(library, "TRASH", tmp_path / ".trash")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    with TestClient(app) as client:
        r = client.post("/api/builds", json={"code": json.dumps(PLAN)}, headers={"X-Poe2lab": "1"}).json()
    session.engine = None
    assert r["name"] == "Test - 0.5.5 Ice Strike" and r["report"]["author"] == "someone"
    assert r["report"]["missing"] == [] and set(r["report"]["worn"]) == {"Ring 1", "Belt"}
    assert (tmp_path / f"{r['name']}.txt").is_file()
