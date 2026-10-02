"""How the build works (poe2lab.analysis.explain): its crit made of PoB's own modifiers, its mana, its meta gems."""
import pytest

from poe2lab.analysis import explain as ex
from poe2lab.analysis.threats import MapProfile
from poe2lab.profile import open_build


@pytest.fixture(scope="module")
def monk():
    engine, bp = open_build("monk")
    cfg = MapProfile(rage=bp.rage).config()
    return engine, cfg, engine.skill_damage(cfg)


def test_crit_is_made_of_its_sources(monk):
    engine, cfg, rows = monk
    g = ex.main_group(engine, engine.skill_groups(), rows)
    c = ex.crit(engine, cfg, g)
    adds = sum(x["value"] for x in c["adds"])
    built = (c["base"] + adds) * (1 + c["incTotal"] / 100) * c["moreTotal"]
    assert c["value"] > 0 and (c["value"] >= 100 or built == pytest.approx(c["value"], rel=0.02))
    # small passives of one name are one row with their count; each row says where it comes from
    assert all(x["kind"] in ("tree", "asc", "jewel", "item", "gem", "other") for x in c["inc"])
    assert any(x["count"] > 1 for x in c["inc"] if x["small"])
    # a condition it stands on is named with its Configuration box, and the crit without it is lower
    for w in c["without"]:
        assert w["box"].startswith("condition") and w["crit"] < c["value"]


def test_the_conditions_of_a_modifier_name_their_box(monk):
    engine, cfg, rows = monk
    src = engine.stat_sources(["CritChance"])
    conds = [c for t in ("INC", "MORE") for r in src["stats"]["CritChance"][t] for c in r["conds"]]
    blinded = [c for c in conds if c["var"] == "Blinded"]
    assert all(c["enemy"] and c["box"] == "conditionEnemyBlinded" for c in blinded)


def test_mana_balance_and_its_fixes(monk):
    engine, cfg, rows = monk
    g = ex.main_group(engine, engine.skill_groups(), rows)
    m = ex.mana(engine, cfg, g)
    assert m["net"] == pytest.approx(m["regen"] + m["leech"] - m["spent"])
    assert sum(m["shares"].values()) == pytest.approx(100, abs=0.5) or not m["shares"]
    for f in m["fixes"]:
        assert f["mana"] > 0 and f["dps"] > ex.MANA_DPS_FLOOR and f["name"] not in ("Hourglass", "Expanse")


def test_meta_gems_say_what_they_give():
    engine, bp = open_build("elemental-storm")
    cfg = MapProfile(rage=bp.rage).config()
    rows = engine.skill_damage(cfg)
    metas = {m["gem"]: m for m in ex.metas(engine, cfg, engine.skill_groups(), None, rows)}
    coea = metas["Cast on Elemental Ailment"]
    assert coea["energy"]["gains"] and coea["cost"] > 0 and coea["spirit"] >= 0
    assert "Elemental Storm" in metas  # triggered on spell crits by the ascendancy


def test_crit_damage_speed_and_defences_are_made_of_their_sources(monk):
    engine, cfg, rows = monk
    g = ex.main_group(engine, engine.skill_groups(), rows)
    cd = ex.crit_damage(engine, cfg, g)
    # PoE2's crit bonus starts at +100%; when the formula gives PoB's number it is marked exact
    assert sum(x["value"] for x in cd["adds"]) >= 100 and cd["value"] > 1
    if cd["exact"]:
        assert 1 + cd["bonus"] / 100 == pytest.approx(cd["value"], rel=ex.EXACT)
    sp = ex.speed(engine, cfg, g)
    assert sp["value"] > 0 and sp["base"] > 0
    defs = {d["stat"]: d for d in ex.defences(engine, cfg)}
    assert defs and all(d["value"] >= ex.DEFENCE_MIN for d in defs.values())
    for d in defs.values():
        assert all(gear["slot"] in ex.GEAR_SLOTS for gear in d["gear"])
        if d["exact"]:
            assert d["base"] * (1 + d["incTotal"] / 100) * d["moreTotal"] == pytest.approx(d["value"], rel=ex.EXACT)


class ChargesStub:
    """A build whose main attack spends frenzy charges (any skill, any charge: nothing here is Flicker Strike's):
    each charge adds three hits; a passive and a skill make the charges, a buff spends them too, a support puts a
    condition on the attack's use."""
    def __init__(self):
        def gem(index, name, support=False, types=(), description=""):
            return {"index": index, "name": name, "support": support, "enabled": True, "types": list(types),
                    "description": description}
        self.groups = [
            {"index": 1, "main": True, "enabled": True, "slot": "", "actives": [{"name": "Frenzy Slam", "types": []}],
             "gems": [gem(1, "Frenzy Slam", types=["Attack", "SkillConsumesFrenzyChargesOnUse"],
                          description="Consumes Frenzy Charges to Slam again."),
                      gem(2, "Steady Feet", True, description="Supported Skills can only be used while standing still.")]},
            {"index": 2, "main": False, "enabled": True, "slot": "", "actives": [{"name": "Frenzy Maker", "types": []}],
             "gems": [gem(1, "Frenzy Maker", types=["Spell"], description="Grants you a Frenzy Charge on use.")]},
            {"index": 3, "main": False, "enabled": True, "slot": "", "actives": [{"name": "Frenzy Buff", "types": []}],
             "gems": [gem(1, "Frenzy Buff", types=["Buff", "SkillConsumesFrenzyChargesOnUse"],
                          description="Consume all Frenzy Charges for a buff.")]}]

    def main_skill_of(self, group):
        from contextlib import nullcontext
        return nullcontext()

    def what_if(self, config=None, **_):
        config = config or {}
        n = 0 if not config.get("useFrenzyCharges") else config.get("overrideFrenzyCharges", 4)
        return {"FrenzyChargesMax": 4, "FrenzyCharges": n, "AverageBurstHits": 1 + 3 * n,
                "AverageBurstDamage": 100.0 * (1 + 3 * n), "AverageDamage": 100.0}

    def stat_sources(self, names, player=False, flags=()):
        row = lambda v, kind, name: {"value": v, "source": {"kind": kind, "name": name}, "conds": []}
        return {"stats": {"FrenzyChargesMax": {"BASE": [row(3, "Base", "Base"), row(1, "Tree", "Frenzied")],
                                               "INC": [], "MORE": []}}}

    def tree_graph(self):
        return {"nodes": [{"alloc": True, "name": "Frenzied", "stats": ["+1 to Maximum Frenzy Charges"]},
                          {"alloc": True, "name": "Rush", "stats": ["10% chance to gain a Frenzy Charge on Hit"]}]}

    def equipped_item_details(self):
        return []


def test_a_skill_spending_charges_shows_one_use_at_each_count(monkeypatch):
    from poe2lab.analysis import skills as sk
    monkeypatch.setattr(sk, "_labels", {})  # the dictionary's own reading of these made-up texts
    stub = ChargesStub()
    groups = stub.groups
    view = [{"group": 2, "kind": "energy", "rate": {"boss": [0.5, 0.5], "pack": [0.1, 0.1]},
             "skills": [{"name": "Frenzy Maker"}]}]
    c = ex.charges(stub, {}, groups[0], groups, [{"group": 1, "name": "Frenzy Slam", "speed": 2.0}], view)
    assert c["kind"] == "frenzy" and c["max"] == 4 and c["now"] == 0 and c["perCharge"] == 3
    assert [(x["charges"], x["hits"], x["damage"]) for x in c["steps"]] == [
        (0, 1, 100), (1, 4, 400), (2, 7, 700), (3, 10, 1000), (4, 13, 1300)]
    assert [x["name"] for x in c["maxFrom"]] == ["Base", "Frenzied"]
    assert c["makers"] == [{"skill": "Frenzy Maker", "group": 2, "meta": None, "rate": {"boss": [0.5, 0.5], "pack": [0.1, 0.1]}}]
    assert [l["line"] for l in c["lines"]] == ["10% chance to gain a Frenzy Charge on Hit"]
    assert c["spenders"] == ["Frenzy Buff"] and c["conditions"] == ["Steady Feet"] and c["speed"] == 2.0


def test_charges_of_another_build(monk):
    """The monk's Hollow Form spends power charges too: their maximum and its sources, the skill and the lines that
    make them; PoB counts only "charges or none" for it (one hit; the same damage from one charge to five)."""
    engine, cfg, rows = monk
    groups = engine.skill_groups()
    c = ex.charges(engine, cfg, ex.main_group(engine, groups, rows), groups, rows, [])
    assert c["skill"] == "Hollow Form" and c["kind"] == "power" and c["max"] == 5 and c["perCharge"] == 0
    assert [x["name"] for x in c["maxFrom"]] == ["Base", "Overflowing Power"]
    assert [m["skill"] for m in c["makers"]] == ["Devour"] and c["lines"]
    damage = [x["damage"] for x in c["steps"]]
    assert damage[1] > damage[0] and damage[-1] == pytest.approx(damage[1])
    # a skill that spends no charges has no such card
    stub = ChargesStub()
    assert ex.charges(stub, {}, stub.groups[1], stub.groups, [], []) is None
