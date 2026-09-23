"""Item comparison and Rage checks on a public Titan (a Rage-scaling build; tests/fixtures/titan.txt).
Its main skill, Furious Slam, hits with the second weapon set: the rare talisman in "Weapon 1 Swap"."""
from pathlib import Path

import pytest

from poe2lab.analysis.items import add_lines, breakeven, compare, scale_line
from poe2lab.analysis.threats import MapProfile
from poe2lab.engine import PobEngine, PobError

TITAN = (Path(__file__).resolve().parent / "fixtures" / "titan.txt").read_text()
SLOT = "Weapon 1 Swap"
FLAT = "Adds 34 to 55 Physical Damage"


@pytest.fixture(scope="module")
def titan():
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(5)
    return e


def test_rage_is_the_core_and_defaults_to_maximum(titan):
    none = titan.what_if(config=MapProfile(rage=0).config())
    full = titan.what_if(config=MapProfile().config())
    assert full["Rage"] == full["MaximumRage"] == 68
    assert full["CombinedDPS"] > none["CombinedDPS"] * 1.5


def test_same_item_text_changes_nothing(titan):
    c = compare(titan, MapProfile().config(), SLOT, titan.item_text(SLOT))
    assert c.dps_pct == pytest.approx(0, abs=1e-6) and not c.unmet_requirements


def test_rage_talisman_beats_current_and_breakeven(titan):
    cfg = MapProfile().config()
    candidate = add_lines(titan.item_text(SLOT), ["+10 to Maximum Rage"])
    c = compare(titan, cfg, SLOT, candidate)
    assert c.dps_pct == pytest.approx(6.0, abs=0.5)
    factor, line = breakeven(titan, cfg, SLOT, candidate, FLAT)
    assert 0.7 < factor < 0.95
    worse = compare(titan, cfg, SLOT, scale_line(candidate, FLAT, factor * 0.8))
    assert worse.dps_pct < 0


def test_unreadable_item_raises(titan):
    with pytest.raises(PobError):
        titan.what_if(replace_item=("Weapon 1", "Rarity: RARE\nNothing\nNo Such Base"))
