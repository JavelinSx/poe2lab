"""What PoB does not count but what moves the numbers (poe2lab.analysis.unmodeled): game lines read the way PoB
can, priced on the skill they belong to, the corrections already counted not offered again."""
from conftest import FIXTURES

from poe2lab.analysis import unmodeled
from poe2lab.knowledge import Gap
from poe2lab.profile import Correction

PARSES = {"35% more Damage", "Gain 40% of Damage as Extra Fire Damage", "13% more Armour, Evasion and Energy Shield",
          "52% more Armour, Evasion and Energy Shield", "70% more Armour", "759 Life"}


def parses(line):
    return line in PARSES


def test_game_lines_read_the_way_pob_can():
    assert unmodeled.pob_line("Detonations from supported Skills deal 35% more Damage", parses)["line"] == "35% more Damage"
    assert unmodeled.pob_line("Buff grants 40% of damage Gained as Fire damage", parses)["line"] == \
        "Gain 40% of Damage as Extra Fire Damage"
    # a per-stage line: at the stages the skill names
    found = unmodeled.pob_line("Buff grants 13% more Armour, Evasion and Energy Shield per Stage", parses,
                               ("Maximum 4 Stages",))
    assert found == {"line": "52% more Armour, Evasion and Energy Shield", "stages": 4}


def test_lines_that_only_look_alike_are_not_read():
    # breaking the enemy's armour is not the player's armour; a life cost is not life gained
    assert unmodeled.pob_line("Supported Skills Break 70% more Armour", parses) is None
    assert unmodeled.pob_line("Sacrifices up to 759 Life", parses) is None
    # a bonus under a condition is not a lasting one
    assert unmodeled.pob_line("When you Freeze a target with Supported Skills, for each 2 Rage you have 35% more Damage",
                              parses) is None


def test_on_a_build_a_buff_counts_for_the_main_skill_and_a_correction_is_not_offered_twice():
    from poe2lab.engine import PobEngine
    from poe2lab.knowledge import collect
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text(encoding="utf-8").strip())
    gaps = collect(e).gaps
    r = unmodeled.estimates(e, gaps, {}, 1, set())
    buff = next(x for x in r["big"] if x["line"] == "Gain 40% of Damage as Extra Fire Damage")
    # Walking Calamity's buff is the player's: it moves the main skill's damage, though it is another skill's line
    assert buff["changes"]["dps"] > 10 and not buff["otherSkill"]
    # counted already (written down another way): not offered again
    done = unmodeled.covered_by([Correction(mod="Gain 40% of Damage as Extra Fire Damage", source="the buff, by hand")])
    again = unmodeled.estimates(e, gaps, {}, 1, done)
    assert all(x["line"] != buff["line"] for x in again["big"] + again["small"])
    # the gaps the knowledge module lists are what is priced here
    assert all(isinstance(g, Gap) for g in gaps)


def test_a_correction_is_priced_by_taking_it_out():
    from poe2lab.engine import PobEngine
    from poe2lab.profile import CORRECTION_BLOCK
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text(encoding="utf-8").strip())
    lines = ["Gain 40% of Damage as Extra Fire Damage", "+500 to maximum Life"]
    e.set_custom_mods(CORRECTION_BLOCK, lines)
    before = e.what_if()
    fx = unmodeled.corrections_effect(e, CORRECTION_BLOCK, lines, {}, None)
    assert fx[0]["dps"] > 5 and abs(fx[0]["ehp"]) < 0.5
    assert fx[1]["ehp"] > 1 and abs(fx[1]["dps"]) < 0.5
    # the corrections are back as they were
    assert e.what_if()["CombinedDPS"] == before["CombinedDPS"]


# ---- a line PoB cannot read even its own way, counted with the player's numbers ----

def gap(where, text):
    return Gap("skill", where, text, text, True)


SLAM = {3: [{"name": "Furious Slam", "minion": False}], 5: [{"name": "Wardbound Minions", "minion": True}]}


def test_how_a_line_is_counted_with_the_players_numbers():
    yes = lambda line: True  # noqa: E731
    m = unmodeled.model_for(gap("Unleash (группа 3)", "Supported Skills Repeat 1 time per Seal broken"), SLAM, yes)
    # a repeat is one more use of the skill it supports - that skill's damage, not the whole build's
    assert m["kind"] == "repeat" and m["skill"] == "Furious Slam"
    assert unmodeled.line_for(m, {"n": 2}) == "Furious Slam deals 200% more Damage"
    # a minion skill cast again is not its minions hitting twice: the player says how much, for the minions
    m = unmodeled.model_for(gap("Unleash (группа 5)", "Supported Skills Repeat 1 time per Seal broken"), SLAM, yes)
    assert m["kind"] == "more" and m["minion"]
    assert unmodeled.line_for(m, {"pct": 40}) == "Minions deal 40% more Damage"
    m = unmodeled.model_for(gap("Armour Break III (группа 3)",
                                "20% chance to gain an Endurance Charge when Supported Skills Fully Break Armour"), SLAM, yes)
    assert m["kind"] == "charges" and unmodeled.line_for(m, {"n": 2}) == "+2 to Minimum Endurance Charges"
    m = unmodeled.model_for(gap("Uruk's Smelting (группа 3)", "Fully Breaking Armour with Supported Skills causes "
                                "affected targets to permanently take 5% increased Physical Damage, up to 20%"), SLAM, yes)
    assert m["kind"] == "taken" and unmodeled.line_for(m, {}) == "Nearby Enemies take 20% increased Physical Damage"
    m = unmodeled.model_for(gap("Uruk's Smelting (группа 3)", "Supported Skills Break 70% more Armour"), SLAM, yes)
    assert m["kind"] == "armour"
    # a skill set off by breaking armour is its own damage, not broken armour
    m = unmodeled.model_for(gap("Armour Explosion (группа 3)",
                                "Supported Skills trigger an Explosion when they Fully Break an enemy's Armour"), SLAM, yes)
    assert m["kind"] == "more"
    # a skill PoB cannot name: the whole build's damage
    m = unmodeled.model_for(gap("Tireless (группа 3)", "Something unknown"), SLAM, lambda line: False)
    assert m["skill"] is None and unmodeled.line_for(m, {"pct": 15}) == "15% more Damage"


def test_a_line_kept_in_whole_numbers_at_any_uptime():
    # PoB reads "17.5% more Damage" as nothing: a line in whole numbers stays in whole numbers
    assert Correction("35% more Damage", "test", uptime=0.5).line == "18% more Damage"
    assert Correction("30% increased Skill Speed", "test", uptime=0.75).line == "23% increased Skill Speed"


def test_broken_armour_is_counted_once():
    from poe2lab.engine import PobEngine
    from poe2lab.knowledge import collect
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text(encoding="utf-8").strip())
    gaps = collect(e).gaps
    actives = unmodeled.actives_by_damage(e.skill_groups(), e.skill_damage({}))
    armour = [r for r in unmodeled.estimates(e, gaps, {}, 1, set(), actives)["unpriced"] if r["model"]["kind"] == "armour"]
    assert armour and not any(r["model"]["counted"] for r in armour)
    line = unmodeled.line_for(armour[0]["model"], {}, e, {}, 1)
    assert line.endswith("% more Damage") and e.can_parse_mod(line)
    # one correction for the state, and every breaking line says it is counted
    again = unmodeled.estimates(e, gaps, {}, 1, {unmodeled.ARMOUR_KEY}, actives)["unpriced"]
    assert all(r["model"]["counted"] for r in again if r["model"]["kind"] == "armour")
