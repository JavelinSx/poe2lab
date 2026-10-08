"""A build from a maxroll.gg planner: its tree history replayed, its mods' rolled values put in PoB's lines, a stage
made a PoB build through the build planner format (the main skill: the guide's first group, on its weapon set)."""
import pytest

from poe2lab import gamedata, maxroll


def test_tree_history_replayed():
    """Nodes taken, taken for one weapon set, given back - the tree a stage ends with, in the order taken."""
    history = [1, 2, {"id": 3, "set": 2}, {"remove": [2]}, 4, {"id": 2, "set": 1}]
    assert maxroll.allocation(history) == [(1, 0), (3, 2), (4, 0), (2, 1)]


def test_mod_lines_take_the_rolled_values():
    assert maxroll.mod_lines(["Adds (13-18) to (26-32) Physical Damage"], [17, 30]) == ["Adds 17 to 30 Physical Damage"]
    # a per-minute stat in a per-second line: scaled to fit; a value fitting no scale: the middle of the range
    assert maxroll.mod_lines(["(18.1-23) Life Regeneration per second"], [1200]) == ["20 Life Regeneration per second"]
    assert maxroll.mod_lines(["+(40-50) to maximum Life"], [7]) == ["+45 to maximum Life"]
    assert maxroll.mod_lines(["+(40-50) to maximum Life", "+(10-20) to Spirit"], [44]) == [
        "+44 to maximum Life", "+15 to Spirit"]


def test_planner_links():
    assert maxroll.planner_id("https://maxroll.gg/poe2/planner/lq6fv0yy#2") == "lq6fv0yy"
    assert maxroll.planner_id("eNrtvWtz...") is None and maxroll.planner_id("https://pobb.in/abc") is None


PLANNER = {"id": "test0001", "name": "Test Monk", "data": {
    "author": {"name": "tester"},
    "profiles": [{
        "name": "Endgame", "class": "DexIntFourb", "ascendancy": "Monk1", "level": 90,
        "passives": {"variants": [{"name": "Endgame", "history": [10364, 42857, {"id": 20024, "set": 2}],
                                   "attributes": {}, "jewels": {}}]},
        "skills": {"steps": [{"name": "Default", "skills": [
            {"gems": [{"id": "Metadata/Items/Gems/SkillGemWhirlingAssault", "level": 20, "quality": 20}], "weaponSet": 2}]}]},
        "equipment": {"variants": [{"name": "Set 1", "items": {"Weapon2": 1}}]},
    }],
    "items": {"1": {"base": "Metadata/Items/Weapons/TwoHandWeapons/Staves/FourQuarterstaff8Cruel", "rarity": "rare",
                    "sockets": ["Metadata/Items/SoulCores/RuneEnhanceGreater"],
                    "mods": {"explicit": {"LocalAddedPhysicalDamageTwoHand5": {"min": 17, "max": 35},
                                          "LocalIncreasedPhysicalDamagePercent4": {"pct": 90}}}}},
}}


def test_a_stage_becomes_a_pob_build():
    if not (gamedata.RAW / "data/balance/uniquestashlayout.datc64").is_file():
        pytest.skip("the game's tables are not unpacked here")
    from poe2lab.engine import PobEngine
    engine = PobEngine()
    code, report = maxroll.to_code(PLANNER, 0, engine)
    assert code and report["variant"] == "Endgame" and not report["missing"]
    staff = engine.item_text("Weapon 1 Swap")
    assert "Guardian Quarterstaff" in staff and "Rune: Greater Iron Rune" in staff and "90% increased Physical Damage" in staff
    # the guide's first group is its main skill, used with the second weapon set (the staff is there)
    assert engine.main_skill() == "Whirling Assault" and engine.second_weapon_set()
    assert engine.what_if()["CombinedDPS"] > 0
