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
