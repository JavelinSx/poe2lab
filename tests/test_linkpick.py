"""Links picked for levelling (poe2lab.analysis.linkpick): what a skill's damage is, the links of a theme."""
from poe2lab.analysis import linkpick


def test_a_skill_s_theme_is_its_ailment_or_its_biggest_hit():
    assert linkpick.theme_of({"CombinedDPS": 100, "ColdHitAverage": 90, "FireHitAverage": 5}) == "cold"
    assert linkpick.theme_of({"CombinedDPS": 100, "MainHand.PhysicalHitAverage": 40, "BleedDPS": 60}) == "bleed"
    assert linkpick.theme_of({"CombinedDPS": 100, "MainHand.PhysicalHitAverage": 40, "BleedDPS": 20}) == "physical"
    assert linkpick.theme_of({"CombinedDPS": 50, "DpsFromMinions": 1}) == "minion"
    assert linkpick.theme_of({"CombinedDPS": 0, "ColdHitAverage": 9}) is None


def row(name, weapon, dps):
    return {"gem": {"name": name, "id": name}, "weapon": weapon, "base": weapon and f"{weapon} base", "level": 10,
            "supports": [], "supportIds": [], "dps": dps, "bare": dps}


def test_a_theme_takes_the_weapon_whose_skills_deal_most_spells_with_any():
    # the bow: 100 + 90/2 + 80/4 = 165; the mace: 120 + 80/2 = 160
    rows = [row("Bow A", "Bow", 100), row("Bow B", "Bow", 90), row("Mace A", "Two Hand Mace", 120),
            row("Spell", None, 80), row("Weak", "Bow", 10)]
    got = linkpick._package("cold", rows)
    assert got["weapon"]["type"] == "Bow" and [s["name"] for s in got["skills"]] == ["Bow A", "Bow B", "Spell"]
    lone = linkpick._package("fire", [row("Mace A", "Two Hand Mace", 150), row("Tiny", "Two Hand Mace", 20)])
    assert [s["name"] for s in lone["skills"]] == ["Mace A", "Tiny"]  # two always; a third only if it deals enough
