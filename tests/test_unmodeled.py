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
