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


def test_supports_worth_more_than_the_weakest(titan):
    """For each skill: supports PoB finds worth more than its weakest, that the character can have, that the build
    does not use; a gem suggested to one skill only."""
    out = sk.better_supports(titan, MapProfile().config(), level=95)
    assert out
    used = {x["name"] for g in titan.skill_groups() for x in g["gems"] if x["support"] and x["enabled"]}
    names = [b["name"] for x in out for b in x["better"]]
    assert len(names) == len(set(names)) and not set(names) & used
    for x in out:
        assert 1 <= len(x["better"]) <= sk.BETTER_TOP and all(b["net"] >= sk.BETTER_MIN for b in x["better"])
    # at level 1 only the first tier's supports drop
    low = sk.better_supports(titan, MapProfile().config(), level=1)
    assert all(b["tier"] == 1 for x in low for b in x["better"])


def test_unique_prices(monkeypatch):
    from poe2lab.economy import ninja

    def fake(path, **params):
        if params["type"] == "UniqueArmours":
            return {"lines": [{"name": "Cloak of Flame", "baseType": "Silk Robe", "primaryValue": 0.02, "listingCount": 40},
                              {"name": "Cloak of Flame", "baseType": "Silk Robe", "primaryValue": 0.5, "listingCount": 3}]}
        return {"lines": []}
    monkeypatch.setattr(ninja, "_get", fake)
    assert ninja.unique_prices("Standard") == {"Cloak of Flame": {"div": 0.02, "listings": 40}}  # the cheapest line


class RolesStub:
    """A build of a main strike, a buff of it, a defence, a skill of its own damage and a charge maker in two
    groups (cast by hand with Unleash, and through Cast on Critical with Boundless Energy)."""
    def __init__(self):
        def g(index, gems, main=False, slot=""):
            gems = [{"index": i + 1, "enabled": True, "level": 20, **x} for i, x in enumerate(gems)]
            return {"index": index, "main": main, "enabled": True, "slot": slot, "label": "",
                    "actives": [{"name": x["name"], "types": x.get("types", [])} for x in gems if not x["support"]],
                    "gems": gems}
        strike = {"name": "Flicker Strike", "support": False, "types": ["Attack"],
                  "description": "Teleport to an enemy and Strike them. Consumes Power Charges to perform additional "
                                 "teleporting Strikes on nearby enemies."}
        ritual = {"name": "Profane Ritual", "support": False, "types": ["Spell"],
                  "description": "Mark a Corpse with a profane rune. When the ritual is complete the Corpse is "
                                 "consumed and you gain a Power Charge."}
        self.groups = [
            g(1, [strike], main=True),
            g(2, [{"name": "Charged Staff", "support": False, "types": ["Buff"], "description": "A buff."}]),
            g(3, [{"name": "Wind Dancer", "support": False, "types": ["Buff"], "description": "More evasion."}]),
            g(4, [{"name": "Whirling Assault", "support": False, "types": ["Attack"], "description": "Spin."}]),
            g(5, [ritual, {"name": "Unleash", "support": True}, {"name": "Charge Profusion II", "support": True}]),
            g(6, [{"name": "Cast on Critical", "support": False, "types": ["Meta", "Triggers", "GeneratesEnergy"],
                   "description": "Triggers socketed Spells on reaching maximum Energy."}, ritual,
                  {"name": "Boundless Energy II", "support": True}, {"name": "Charge Profusion II", "support": True}])]

    def skill_groups(self):
        import copy
        return copy.deepcopy(self.groups)

    def what_if(self, config=None, main_socket_group=None, disable_gems=()):
        off = {g for g, _ in disable_gems}
        return {"CombinedDPS": 100.0 * (0.8 if 2 in off else 1.0), "TotalEHP": 1000.0 * (0.75 if 3 in off else 1.0)}


def test_roles_say_what_each_skill_does_for_the_main_one(regex_only):
    rows = [{"group": 1, "name": "Flicker Strike", "dps": 100.0}, {"group": 4, "name": "Whirling Assault", "dps": 3.0}]
    r = sk.roles(RolesStub(), {}, rows)
    assert r["main"] == 1 and r["skill"] == "Flicker Strike"
    by = {g["group"]: g for g in r["groups"]}
    assert by[1]["main"]
    assert by[2]["dps"] == pytest.approx(-20) and by[2]["ehp"] == 0  # a buff of the main skill
    assert by[3]["ehp"] == pytest.approx(-25) and by[3]["dps"] == 0  # a defence
    assert by[4]["own"] == pytest.approx(3) and by[4]["dps"] == 0 and not by[4]["gives"]  # nothing PoB counts for the main
    assert [m["key"] for m in by[5]["gives"]] == ["power"]  # the charges the main skill spends
    # the same skill twice: how each copy is used and the supports only it has
    assert by[5]["copies"] == [{"group": 6, "skill": "Profane Ritual", "meta": "Cast on Critical", "slot": None}]
    assert by[5]["only"] == ["Unleash"] and by[6]["only"] == ["Boundless Energy II"] and by[6]["meta"] == "Cast on Critical"
    # a skill PoB gives no damage because it is triggered: its damage from how often it goes off
    view = [{"group": 4, "skills": [{"name": "Whirling Assault", "dps": {"boss": [12.0, 20.0], "pack": [30.0, 30.0]}}]}]
    assert sk.roles(RolesStub(), {}, rows, view)["groups"][3]["own"] == pytest.approx(12)
