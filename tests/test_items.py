"""Item comparison and Rage checks on the user's Titan (a Rage-scaling build)."""
import re
from pathlib import Path

import pytest

from poe2lab.analysis.items import breakeven, compare, scale_line
from poe2lab.analysis.threats import MapProfile
from poe2lab.engine import PobEngine, PobError

TITAN = (Path(__file__).resolve().parents[1] / "builds" / "titan.txt").read_text()
FLAT = "Adds 26 to 42 Physical Damage"


@pytest.fixture(scope="module")
def titan():
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(4)
    return e


def maji_variant(text: str, rage: int) -> str:
    text = text.replace("Spiny Talisman", "Maji Talisman")
    text = re.sub(r"Implicits: (\d+)", lambda m: f"Implicits: {int(m.group(1)) + 1}", text)
    return text.replace("{enchant}20% increased Physical Damage",
                        f"{{enchant}}20% increased Physical Damage\n+{rage} to Maximum Rage")


def test_rage_is_the_core_and_defaults_to_maximum(titan):
    none = titan.what_if(config=MapProfile(rage=0).config())
    full = titan.what_if(config=MapProfile().config())
    assert full["Rage"] == full["MaximumRage"] == 67
    assert full["CombinedDPS"] > none["CombinedDPS"] * 2


def test_same_item_text_changes_nothing(titan):
    c = compare(titan, MapProfile().config(), "Weapon 1", titan.item_text("Weapon 1"))
    assert c.dps_pct == pytest.approx(0, abs=1e-6) and not c.unmet_requirements


def test_rage_talisman_beats_current_and_breakeven(titan):
    cfg = MapProfile().config()
    candidate = maji_variant(titan.item_text("Weapon 1"), 10)
    c = compare(titan, cfg, "Weapon 1", candidate)
    assert c.dps_pct == pytest.approx(10.4, abs=0.5)
    factor, line = breakeven(titan, cfg, "Weapon 1", candidate, FLAT)
    assert 0.5 < factor < 0.8
    worse = compare(titan, cfg, "Weapon 1", scale_line(candidate, FLAT, factor * 0.8))
    assert worse.dps_pct < 0


def test_unreadable_item_raises(titan):
    with pytest.raises(PobError):
        titan.what_if(replace_item=("Weapon 1", "Rarity: RARE\nNothing\nNo Such Base"))
