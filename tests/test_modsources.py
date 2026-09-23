"""Where a mod comes from, from PoB's game data - so the assistant never has to guess whether a mod exists."""
import json
from pathlib import Path

import pytest

from poe2lab.analysis.threats import MapProfile
from poe2lab.assistant.tools import Toolbox
from poe2lab.data import modsources
from poe2lab.engine import PobEngine

TITAN = (Path(__file__).resolve().parent / "fixtures" / "titan.txt").read_text().strip()


@pytest.fixture(scope="module")
def tools():
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(5)
    return Toolbox(e, MapProfile())


def test_numbers_do_not_matter():
    assert modsources.search_text("+(23-31)% of Armour also applies to Chaos Damage") == \
        modsources.search_text("+30% of Armour also applies to Chaos Damage") == "of armour also applies to chaos damage"


def test_armour_against_chaos_is_found_everywhere_it_exists(tools):
    r = json.loads(tools.call("find_mod", {"text": "+30% of Armour also applies to Chaos Damage"}))
    assert r["found"]
    assert any(a["source"] == "desecrated affix" and "Helmet" in a["itemTypes"] for a in r["affixes"])
    assert [u["name"] for u in r["uniques"]] == ["Blackheart"]  # current version only (Loreweave had it before)
    kinds = {p["name"]: p for p in r["passives"]}
    assert kinds["Dedication to Kitava"]["kind"].startswith("ascendancy Smith of Kitava")
    assert kinds["Path of the Renegade"]["trees"] == [r["gameTree"]]  # only on the game's current tree
    assert {x["name"] for x in r["runes"]} >= {"Panther Idol"}


def test_affix_tiers_and_item_types(tools):
    r = json.loads(tools.call("find_mod", {"text": "of Armour also applies to Elemental Damage"}))
    regular = next(a for a in r["affixes"] if a["source"] == "affix")
    assert regular["tiers"] >= 5 and regular["fromItemLevel"] == 1 and "Boots" in regular["itemTypes"]
    assert r["baseImplicits"] and all("Elemental" in b["implicit"] for b in r["baseImplicits"])


def test_not_found_is_not_a_verdict(tools):
    r = json.loads(tools.call("find_mod", {"text": "of Armour also applies to Friendship"}))
    assert not r["found"] and "does not prove" in r["note"]
    assert "error" in json.loads(tools.call("find_mod", {"text": "+5%"}))


def test_the_report_carries_resistances(tools):
    r = json.loads(tools.call("build_report", {}))
    assert r["resistances"]["Chaos"]["value"] == 75 and r["resistances"]["Chaos"]["uncapped"] >= 75
