"""The skills tab: gems per skill, links between skills from the mechanics dictionary, and the levelling plan."""
from pathlib import Path

import pytest

from poe2lab.analysis import skills as sk
from poe2lab.analysis.threats import MapProfile
from poe2lab.engine import PobEngine

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def gem(description="", stats=(), tags=(), support=False, name="X"):
    return {"name": name, "description": description, "stats": list(stats), "tags": list(tags), "support": support}


@pytest.fixture
def regex_only(monkeypatch):
    """The dictionary's own reading of these made-up texts: Jev's labels (by the real gems' names) left out."""
    monkeypatch.setattr(sk, "_labels", {})


def test_creating_and_using_a_mechanic_read_from_the_game_text(regex_only):
    cascade = gem("Frozen enemies hit by the final spike are dealt heavy damage but the Freeze is Consumed. "
                  "Ice Crystals hit by the final spike explode.", ["never_freeze"], ["cold", "attack"])
    assert sk.mechanics_of(cascade) == {"creates": ["combo"], "uses": ["impale", "ice_crystal", "freeze"]}
    locus = gem("Leap backward and crack the ground with your staff to call forth an Ice Crystal", [], ["cold", "attack"])
    assert {"ice_crystal", "freeze"} <= set(sk.mechanics_of(locus)["creates"])
    # a support mentioning an ailment, or tagged with a damage type, does not inflict it
    assert sk.mechanics_of(gem("Culling a Shocked enemy with Supported Skills infuses", support=True)) == \
        {"creates": [], "uses": ["shock"]}
    assert sk.mechanics_of(gem("causing Ignite applied to you to last shorter", tags=["fire"], support=True)) == \
        {"creates": [], "uses": []}
    assert "shock" not in sk.mechanics_of(gem("Hits create a damaging shockwave"))["creates"]
    # the skill that spends Combo is not one of those that build it
    bell = gem("Build Combo by successfully Striking Enemies with other skills. After reaching maximum Combo, use this",
               ["active_skill_required_number_of_combo_stacks"], ["attack"])
    assert sk.mechanics_of(bell) == {"creates": [], "uses": ["impale", "combo"]}


def test_links_pair_different_gems_and_flag_what_nothing_creates(regex_only):
    def group(i, *gems):
        return {"index": i, "enabled": True, "actives": [{"name": gems[0]["name"]}],
                "gems": [g | {"enabled": True, "mechanics": sk.mechanics_of(g)} for g in gems]}
    locus = gem("call forth an Ice Crystal", tags=["cold", "attack"], name="Frozen Locus")
    cascade = gem("the Freeze is Consumed. Ice Crystals hit by the final spike explode.", ["never_freeze"],
                  ["cold", "attack"], name="Glacial Cascade")
    found = {l["key"]: l for l in sk.links([group(1, cascade), group(2, locus)])}
    assert [r["gem"] for r in found["freeze"]["creates"]] == ["Frozen Locus"]
    assert [r["gem"] for r in found["ice_crystal"]["uses"]] == ["Glacial Cascade"]
    alone = {l["key"]: l for l in sk.links([group(1, cascade)])}
    assert alone["freeze"]["missing"]  # nothing in that build freezes


def test_availability_follows_uncut_gem_drops():
    assert sk.available_level({"support": True, "tier": 3}) == 33
    assert sk.available_level({"support": False, "tier": 7, "reqLevel": 22}) == 23
    assert sk.available_level({"support": False, "tier": 0}) is None  # a weapon's skill or a lineage support


@pytest.fixture(scope="module")
def titan():
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text())
    e.set_main_skill(5)
    return e


def test_build_view(titan):
    v = sk.build_view(titan, MapProfile().config(), titan.mechanics_raw())
    slam = next(g for g in v["groups"] if g["index"] == 5)
    close = next(x for x in slam["gems"] if x["name"] == "Close Combat II")
    assert close["because"] == ["атака"] and close["worth"]["dps"] > 1 and close["lines"]
    rage = next(l for l in v["links"] if l["key"] == "rage")
    assert "Furious Slam" in {r["gem"] for r in rage["uses"]} and rage["creates"]
    assert titan.what_if()["CombinedDPS"] > 0  # the build is left as it was


def test_leveling_view(titan):
    base = titan.what_if()["CombinedDPS"]
    v = sk.leveling_view(titan, MapProfile().config())
    assert [row["level"] for row in v["timeline"]] == sorted(row["level"] for row in v["timeline"])
    slam = next(p for p in v["plans"] if p["skill"] == "Furious Slam")
    first = slam["stages"][0]
    assert first["level"] == 1 and first["later"] and first["options"]
    assert all(o["tier"] == 1 and o["dps"] > 0 for o in first["options"])  # tier 1 supports drop from the start
    assert titan.what_if()["CombinedDPS"] == base  # every tried gem was taken out again


def test_one_option_per_support_family(titan):
    v = sk.leveling_view(titan, MapProfile().config())
    for plan in v["plans"]:
        for stage in plan["stages"]:
            names = [o["name"].rstrip(" I") for o in stage["options"]]
            assert len(names) == len(set(names)), (plan["skill"], stage["level"], names)


def test_meta_gems_say_what_feeds_their_energy():
    """Cast on Elemental Ailment gains energy on freeze, shock and ignite: the build's own skills that inflict them
    feed it; the spell it triggers, other meta gems and curses do not."""
    from poe2lab.analysis.skills import meta_view
    from poe2lab.profile import open_build
    engine, _ = open_build(Path(__file__).resolve().parent / "fixtures" / "elemental-storm.txt")
    groups = engine.skill_groups()
    meta_view(groups)
    metas = {g["meta"]["gem"]: g["meta"] for g in groups if g.get("meta")}
    coea = metas["Cast on Elemental Ailment"]
    assert coea["kind"] == "energy" and coea["socketed"] == ["Firestorm"]
    assert set(coea["sources"]) == {"ignite", "shock", "freeze"} and not coea["missing"]
    fed = {n for xs in coea["feeders"].values() for n in xs}
    assert "Frost Bomb" in fed and not fed & {"Firestorm", "Living Bomb", "Elemental Invocation", "Elemental Weakness"}
    assert metas["Blasphemy"]["kind"] == "aura" and metas["Blasphemy"]["socketed"] == ["Temporal Chains"]
    assert metas["Spellslinger"]["sources"] == ["spell_cast"]


EE_TEXT = ("Create a fiery explosion, an arcing bolt of lightning, or an icy wave of projectiles. The chance for an "
           "explosion is proportional to your Strength, for a bolt proportional to your Dexterity, and for a wave "
           "proportional to your Intelligence.")


class PartsStub:
    """Elemental Expression as PoB shows it: its first stat set (the skill itself) has a small hit no support moves;
    the explosion, wave and bolt the game picks between are the others."""
    def what_if(self, config=None, main_socket_group=None, disable_gems=()):
        return {"CombinedDPS": 0.2, "AverageHit": 331, "Str": 41, "Dex": 69, "Int": 83}

    def stat_set_hits(self, group, name, config=None, disable_gems=()):
        return [{"index": 1, "label": "Elemental Expression", "hit": 331}, {"index": 2, "label": "Fiery Explosion", "hit": 225},
                {"index": 3, "label": "Icy Wave", "hit": 214}, {"index": 4, "label": "Arcing Bolt", "hit": 219}]


def test_a_skill_of_parts_is_read_by_its_parts():
    g = {"index": 1, "enabled": True, "mainActive": 1, "actives": [{"name": "Elemental Expression"}],
         "gems": [{"name": "Elemental Expression", "support": False, "description": EE_TEXT}]}
    m = sk._measure_group(PartsStub(), {}, g)
    assert m["how"] == "hit" and set(m["sets"]) == {2, 3, 4}  # not the first set, which none of them is
    assert m["sets"][3] == pytest.approx(83 / 193) and m["sets"][2] == pytest.approx(41 / 193)
    assert sk._part_weights("A storm of fire.", PartsStub().stat_set_hits(1, ""), {}) == {}


def test_stat_sets_shown_one_by_one_and_put_back():
    from poe2lab.profile import open_build
    engine, _ = open_build(FIXTURES / "elemental-storm.txt")
    before = engine.what_if(main_socket_group=1)["AverageHit"]
    sets = engine.stat_set_hits(1, "Elemental Storm")
    assert [s["label"] for s in sets] == ["Elemental Storm", "Fire", "Lightning", "Cold"]
    assert sets[0]["hit"] == 0 and all(s["hit"] > 0 for s in sets[1:])
    assert engine.what_if(main_socket_group=1)["AverageHit"] == before  # the build's own choice is back
    assert engine.stat_set_hits(1, "Frost Bomb") == []  # a skill of one set


def test_a_support_waiting_for_a_configuration_box():
    """Blazing Critical's damage is "if you've crit recently": the box PoB leaves unticked until told."""
    from poe2lab.profile import open_build
    engine, _ = open_build(FIXTURES / "monk.txt")
    group = next(g for g in engine.skill_groups() if g["actives"] and g["actives"][0]["name"] == "Devour")
    blazing = next(x for x in group["gems"] if x["name"] == "Blazing Critical")
    assert [c["var"] for c in engine.gem_conditions(group["index"], blazing["index"])] == ["conditionCritRecently"]
    rend = next(g for g in engine.skill_groups() if g["actives"] and g["actives"][0]["name"] == "Rend")
    assert all(not engine.gem_conditions(rend["index"], x["index"]) for x in rend["gems"] if x["name"] == "Rapid Attacks II")
