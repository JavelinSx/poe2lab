"""What matters in a gear slot (poe2lab.analysis.slotadvice): each mod priced in a good item, the best item made of
them, and why - from what the build is made of."""
from contextlib import nullcontext

import pytest

from poe2lab import itemcraft
from poe2lab.analysis import slotadvice
from poe2lab.analysis.threats import MapProfile
from poe2lab.data.moddb import ModDB
from poe2lab.profile import open_build


@pytest.fixture(scope="module")
def monk():
    engine, bp = open_build("monk")
    return engine, MapProfile(rage=bp.rage).config(), ModDB.from_engine(engine), engine.export_item_data()["bases"]


def test_a_slot_advice_prices_mods_and_makes_the_best_item(monk):
    engine, cfg, db, all_bases = monk
    names = set(engine.slot_bases("Weapon 1"))
    bases = itemcraft.endgame_bases([b for b in all_bases if b["name"] in names])
    worn = engine.equipped_bases()["Weapon 1"]
    a = slotadvice.advise(engine, db, cfg, "Weapon 1", bases, worn)
    base = next(b for b in all_bases if b["name"] == a["base"])
    assert base["type"] == worn["type"] and base["subType"] == worn["subType"]  # the worn item's kind
    assert a["mods"] and a["mods"][0]["dps"] + a["mods"][0]["ehp"] >= a["mods"][-1]["dps"] + a["mods"][-1]["ehp"]
    best = next(iter(a["best"].values()))
    assert 1 <= len(best["picks"]) <= 6 and len(best["picks"]) <= len(best["lines"])
    assert best["text"].startswith("Rarity:")
    assert engine.what_if(config=cfg, replace_item=("Weapon 1", best["text"]))["CombinedDPS"] > 0  # PoB reads it
    # each mod priced inside that item, its worth alone kept
    assert a["inItem"] and all("aloneDps" in m and "aloneEhp" in m for m in a["mods"])
    # why: what the build is made of, and the kinds of mod the slot pays for most, best first
    f = a["facts"]
    assert abs(sum(f["hit"].values()) - 100) < 0.5 and f["skill"] and f["defences"]
    kinds = dict(slotadvice.KINDS)
    assert a["why"] and all(w["kind"] in kinds for w in a["why"]) and len(a["why"]) <= slotadvice.WHY_TOP
    assert [w["value"] for w in a["why"]] == sorted((w["value"] for w in a["why"]), reverse=True)


def test_a_character_gets_what_it_can_wear(monk):
    engine, cfg, db, all_bases = monk
    names = set(engine.slot_bases("Weapon 1"))
    bases = [b for b in all_bases if b["name"] in names]
    worn = engine.equipped_bases()["Weapon 1"]
    # the character going toward a build (here the build is itself): the best items tried on it too
    a = slotadvice.advise(engine, db, cfg, "Weapon 1", bases, worn, level=40, player=(engine, cfg, None, worn))
    base = next(b for b in all_bases if b["name"] == a["base"])
    assert base["level"] <= 40 and a["itemLevel"] == 40 and a["forLevel"] == 40
    assert a["you"]["worn"] == worn and a["best"]
    for b in a["best"].values():  # the same build: the same change
        assert b["you"]["dps"] == pytest.approx(b["dps"]) and b["you"]["ehp"] == pytest.approx(b["ehp"])


def test_links_and_kinds_from_pobs_names():
    """PoB's links between stats read from their names; a mod's kind from its lines."""
    def link(name):
        m = slotadvice._LINK.match(name)
        return m["src"] or "All", m["how"], m["dst"]
    assert link("DamageGainAsCold") == ("All", "GainAs", "Cold")
    assert link("PhysicalDamageConvertToFire") == ("Physical", "ConvertTo", "Fire")
    assert link("SkillPhysicalDamageConvertToCold") == ("Physical", "ConvertTo", "Cold")
    assert link("PhysicalDamageSkillConvertToLightning") == ("Physical", "ConvertTo", "Lightning")
    assert link("ElementalDamageConvertToLightning") == ("Elemental", "ConvertTo", "Lightning")
    assert link("EvasionGainAsDeflection") == ("Evasion", "GainAs", "Deflection")
    kind = slotadvice.kind_of
    assert kind(["(135-154)% increased Physical Damage"]) == "phys"
    assert kind(["Adds (56-70) to (84-107) Fire Damage"]) == "elemental"
    assert kind(["(100-119)% increased Elemental Damage with Attacks"]) == "elemental"
    assert kind(["+4 to Level of all Melee Skills"]) == "gems"
    assert kind(["(23-25)% increased Attack Speed"]) == "speed"
    assert kind(["+(20-22)% to Critical Damage Bonus"]) == "crit"
    assert kind(["(39-42)% increased Evasion and Energy Shield", "+(42-49) to maximum Life"]) == "evasion"
    assert kind(["+(41-45)% to Fire Resistance"]) == "resist"
    assert kind(["Gain Deflection Rating equal to (18-20)% of Evasion Rating"]) == "deflect"
    assert kind(["+(200-214) to maximum Life"]) == "life"
    assert kind(["(101-151) to (152-220) Physical Thorns damage"]) == "other"


class _Build:
    """A build's numbers as PoB gives them: a staff's hit 25% physical, 75% cold - cold the staff and a ring add and
    damage gained as cold (a gem and a passive), scaled by elemental damage - and evasion granting deflection (two
    items)."""
    def main_skill_of(self, group):
        return nullcontext()

    def what_if(self, config):
        return {"MainHand.PhysicalHitAverage": 250.0, "MainHand.ColdHitAverage": 750.0, "CritChance": 34.0,
                "Life": 1.0, "EnergyShield": 1600.0, "Evasion": 6800.0, "DeflectChance": 30.0}

    def stat_names(self, parts):
        return ["DamageGainAsCold", "EvasionGainAsDeflection", "CannotGainSpiritFromEquipment"]

    def stat_sources(self, names):
        def row(value, kind, name):
            return {"value": value, "source": {"kind": kind, "name": name}, "conds": []}
        return {"skill": "Flicker Strike", "attack": True,
                "weaponDamage": {"Physical": {"min": 82, "max": 172}, "Cold": {"min": 43, "max": 62}}, "stats": {
            "ColdMin": {"BASE": [row(24, "Item", "Rune Finger, Iron Ring")], "INC": [], "MORE": []},
            "ColdMax": {"BASE": [row(32, "Item", "Rune Finger, Iron Ring")], "INC": [], "MORE": []},
            "Damage": {"BASE": [], "INC": [row(119, "Tree", "Attack Damage")], "MORE": [row(30, "Skill", "Concentrated Area")]},
            "ElementalDamage": {"BASE": [], "INC": [row(165, "Tree", "Elemental Damage")],
                                "MORE": [row(25, "Skill", "Elemental Armament II")]},
            "DamageGainAsCold": {"BASE": [row(30, "Skill", "Freezing Mark"), row(10, "Tree", "I am the Blizzard...")],
                                 "INC": [], "MORE": []},
            "EvasionGainAsDeflection": {"BASE": [row(27, "Item", "Phoenix Sanctuary, Sleek Jacket"),
                                                row(18, "Item", "Pain Trail, Wanderer Shoes")], "INC": [], "MORE": []},
            "CannotGainSpiritFromEquipment": {"BASE": [], "INC": [], "MORE": []}}}


def test_facts_say_what_the_build_is_made_of():
    f = slotadvice.facts(_Build(), {})
    assert f["skill"] == "Flicker Strike" and f["hit"] == {"Physical": 25.0, "Cold": 75.0} and f["crit"] == 34.0
    # a defence of a Chaos Inoculation build's 1 life is no defence
    assert f["defences"] == {"EnergyShield": 1600.0, "Evasion": 6800.0} and f["deflection"] == 30.0
    assert [(l["from"], l["how"], l["to"], l["value"]) for l in f["links"]] == [
        ("Evasion", "gain", "Deflection", 45), ("All", "gain", "Cold", 40)]
    cold = f["links"][1]
    assert [(x["kind"], x["name"], x["value"]) for x in cold["sources"]] == [
        ("gem", "Freezing Mark", 30), ("tree", "I am the Blizzard...", 10)]
    # where the hit's cold comes from, though the skill's description names none: the staff, a ring, the scaling
    frm = f["hitFrom"]
    assert frm["Cold"]["weapon"] == {"min": 43, "max": 62}
    assert frm["Cold"]["added"] == [{"kind": "item", "name": "Rune Finger, Iron Ring", "min": 24, "max": 32}]
    assert frm["Cold"]["inc"] == 284 and frm["Cold"]["more"] == pytest.approx(1.3 * 1.25)
    assert frm["Physical"]["weapon"] == {"min": 82, "max": 172} and frm["Physical"]["added"] == []
    assert frm["Physical"]["inc"] == 119 and frm["Physical"]["more"] == pytest.approx(1.3)


def test_why_names_the_kinds_the_slot_pays_for_most():
    mods = [{"lines": ["(135-154)% increased Physical Damage"], "dps": 66.0, "ehp": 0.0},
            {"lines": ["Adds (23-35) to (39-59) Physical Damage"], "dps": 40.0, "ehp": 0.0},
            {"lines": ["+4 to Level of all Melee Skills"], "dps": 43.0, "ehp": 0.0},
            {"lines": ["(23-25)% increased Attack Speed"], "dps": 33.0, "ehp": 0.0},
            {"lines": ["Adds (56-70) to (84-107) Fire Damage"], "dps": 36.0, "ehp": 0.0},
            {"lines": ["Adds (46-57) to (70-88) Cold Damage"], "dps": -12.0, "ehp": 0.0},
            {"lines": ["(101-151) to (152-220) Physical Thorns damage"], "dps": 0.0, "ehp": 0.0}]
    why = slotadvice.why_of(mods)
    assert [(w["kind"], w["value"]) for w in why] == [("phys", 66.0), ("gems", 43.0), ("elemental", 36.0)]
