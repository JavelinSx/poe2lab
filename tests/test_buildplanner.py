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


def test_everything_the_format_holds_is_read():
    # the format's forms: a level or [from, to]; a note naming the attribute; bare ids for passives and skills
    assert buildplanner.interval(14) == [14, 100] and buildplanner.interval([41, 90]) == [41, 90]
    assert buildplanner.interval(None) is None and buildplanner.interval("x") is None
    assert buildplanner.attribute_choice("+5 to Dexterity") == "dex"
    assert buildplanner.attribute_choice("<b>{+5 к интеллекту}") == "int" and buildplanner.attribute_choice("Сила") == "str"
    assert buildplanner.attribute_choice("Strength or Intelligence") is None and buildplanner.attribute_choice("") is None
    bare = buildplanner.parse(json.dumps({"name": "x", "passives": ["dexterity5"], "skills": ["Metadata/Items/Gems/SkillGemIceStrike"]}))
    assert bare["passives"] == [{"id": "dexterity5"}] and bare["inventory_slots"] == []
    odd = dict(PLAN, extra=1, passives=PLAN["passives"] + [{"id": "dexterity6", "colour": "red"}])
    assert buildplanner.unknown_fields(odd) == ["extra", "passives.colour"]


def test_the_guide_s_levels_and_notes_are_kept():
    plan = json.loads(json.dumps(PLAN))
    plan["description"] = "<b>{Ice Strike} from act 2"
    plan["skills"][0]["level_interval"] = [14, 100]
    plan["skills"][0]["support_skills"][0]["level_interval"] = 22
    plan["inventory_slots"][0]["level_interval"] = [40, 100]
    plan["passives"][2]["additional_text"] = "+5 to Intelligence"  # the neutral attribute node: its choice
    code, report = buildplanner.to_code(json.dumps(plan), PobEngine())
    assert report["description"] == "Ice Strike from act 2" and report["unknown"] == []
    ice = report["skills"][0]
    assert (ice["name"], ice["from"], ice["supports"][0]["from"]) == ("Ice Strike", 14, 22)
    ring = next(i for i in report["items"] if i["slot"] == "Ring 1")
    assert (ring["kind"], ring["from"]) == ("rare", 40)
    assert report["passives"]["attributesChosen"] == 1 and report["attributes"]["chosen"] == {"Str": 0, "Dex": 0, "Int": 0}
    assert report["plan"]["skills"][0]["from"] == 14 and report["plan"]["notes"] == {"attributes28": "+5 to Intelligence"}


@pytest.fixture(scope="module")
def rich():
    """The monk (3 jewels, attribute choices) exported the way poe2lab writes it for the game, then imported back."""
    source = PobEngine()
    source.load_code((FIXTURES / "monk.txt").read_text())
    levels = {"Ice Strike": 15}
    text = buildplanner.export_rich(source, "monk", levels=levels, description="<b>{monk}", lang="ru",
                                    plan={"source": {"author": "someone", "link": "https://example.org/guide"}})
    engine = PobEngine()
    code, report = buildplanner.to_code(text, engine)
    return source, engine, report, json.loads(text)


def test_the_export_carries_what_the_format_has_no_field_for(rich):
    source, _, _, data = rich
    assert data["author"] == "someone" and data["link"] == "https://example.org/guide" and data["description"] == "<b>{monk}"
    jewel_notes = [p for p in data["passives"] if p["id"].startswith("jewel_slot") and p.get("additional_text")]
    assert len(jewel_notes) == 3
    assert any(p.get("additional_text", "").startswith("+5 к ") for p in data["passives"])
    # an item's level requirement is when to take it; a unique is named for the game
    assert all(e.get("level_interval", [0])[0] > 1 for e in data["inventory_slots"] if "level_interval" in e)
    worn = {u["slot"] for u in source.equipped_item_details() if u["rarity"] == "UNIQUE"}
    assert len([e for e in data["inventory_slots"] if e.get("unique_name")]) == len(worn)


def test_jewels_and_attribute_choices_come_back(rich):
    source, engine, report, _ = rich
    assert report["missing"] == [] and len(report["passives"]["jewels"]) == 3
    assert report["attributes"]["chosen"] == {"Str": 0, "Dex": 0, "Int": 0}  # every choice read, none guessed

    def jewels(e):
        return sorted(e._json("""
local out = _poe2lab_array({})
for nodeId, slot in pairs(build.itemsTab.sockets) do
  local item = build.itemsTab.items[slot.selItemId]
  if item and build.spec.allocNodes[nodeId] then out[#out + 1] = item.name end
end
return _poe2lab_json(out)"""))
    assert [j.split(",")[0] for j in jewels(engine)] == [j.split(",")[0] for j in jewels(source)]
    for attr in ("Str", "Dex", "Int"):
        assert engine.stats()[attr] == pytest.approx(source.stats()[attr], abs=10)


def test_the_game_s_planner_folder(tmp_path, monkeypatch):
    from poe2lab.web.server import app, session
    monkeypatch.setenv("POE2LAB_BUILDPLANNER", str(tmp_path / "planner"))
    monkeypatch.setattr(library, "PROJECT_BUILDS", tmp_path / "builds")
    monkeypatch.setattr(library, "TRASH", tmp_path / "builds" / ".trash")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    h = {"X-Poe2lab": "1"}
    with TestClient(app) as client:
        assert client.get("/api/planner").json() == {"dir": str(tmp_path / "planner"), "exists": False, "files": []}
        client.post("/api/load", json={"name": "titan"}, headers=h)
        first = client.post("/api/planner/export?build=titan", json={"lang": "ru"}, headers=h).json()
        assert first["file"] == "titan.build" and not first["overwritten"]
        written = json.loads((tmp_path / "planner" / "titan.build").read_text(encoding="utf-8"))
        assert "poe2lab" in written["description"] and any(s.get("level_interval") for s in written["skills"])
        assert client.post("/api/planner/export?build=titan", json={}, headers=h).status_code == 409
        assert client.post("/api/planner/export?build=titan", json={"overwrite": True}, headers=h).json()["overwritten"]
        listed = client.get("/api/planner").json()
        assert [f["file"] for f in listed["files"]] == ["titan.build"]
        assert client.post("/api/planner/import", json={"file": "../titan.txt"}, headers=h).status_code == 404
        added = client.post("/api/planner/import", json={"file": "titan.build"}, headers=h).json()
    session.engine = None
    assert added["report"]["missing"] == [] and len(added["report"]["passives"]["jewels"]) == 3
    profile = json.loads((tmp_path / "builds" / f"{added['name']}.profile.json").read_text(encoding="utf-8"))
    assert profile["planner"]["skills"] and "plan" not in added["report"]

