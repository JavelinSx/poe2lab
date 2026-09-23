"""Loot filter block for a build: what it marks, its syntax, and merging on top of the player's filter."""
from pathlib import Path

import pytest

from poe2lab import lootfilter as lf
from poe2lab.analysis.report import defence_weights
from poe2lab.analysis.threats import MapProfile, survivable_hits
from poe2lab.data.moddb import ModDB
from poe2lab.engine import PobEngine

TITAN = (Path(__file__).resolve().parent / "fixtures" / "titan.txt").read_text()
KEYWORDS = {"Identified", "Rarity", "Class", "BaseType", "ItemLevel", "HasExplicitMod", "BaseArmour", "BaseEvasion",
            "BaseEnergyShield", "SetFontSize", "SetTextColor", "SetBorderColor", "SetBackgroundColor",
            "PlayAlertSound", "PlayEffect", "MinimapIcon"}


@pytest.fixture(scope="module")
def rules():
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(5)
    profile = MapProfile()
    return lf.slot_rules(e, ModDB.from_engine(e), profile.config(), "balanced",
                         defence_weights(survivable_hits(e, profile)))


def test_item_classes_and_defence_types():
    assert lf.item_class({"type": "Staff", "tags": ["warstaff", "weapon"]}) == "Quarterstaves"
    assert lf.item_class({"type": "Staff", "tags": ["staff"]}) == "Staves"
    assert lf.item_class({"type": "Talisman", "tags": []}) == "Talismans"
    assert lf._defence({"type": "Body Armour", "tags": ["armour", "str_dex_armour"]}) == ["BaseArmour > 0",
                                                                                          "BaseEvasion > 0"]
    assert lf._defence({"type": "Ring", "tags": ["ring"]}) == []


def test_rules_follow_the_build(rules):
    by = {r.slot: r for r in rules}
    swap = by["Weapon 1 Swap"]  # Furious Slam's talisman, in the second weapon set
    assert swap.item_class == "Talismans" and swap.base == "Fungal Talisman" and not swap.unique
    assert len(swap.affixes) >= 3 and swap.item_level <= lf.MAX_ILVL
    assert by["Weapon 1"].unique and not by["Weapon 1"].affixes  # Amor Mandragora: by base only
    assert by["Boots"].defence == ["BaseArmour > 0"]


def test_block_syntax(rules):
    block = lf.render(rules, "titan")
    assert block.startswith(lf.BEGIN) and block.rstrip().endswith(lf.END)
    for line in block.splitlines():
        if line.startswith("\t"):
            assert line.strip().split(" ")[0] in KEYWORDS, line
        elif line and not line.startswith("#"):
            assert line.startswith("Show # poe2lab:"), line
    assert 'BaseType == "Fungal Talisman"' in block and "HasExplicitMod >=3" in block
    assert 'Rarity Unique\n\tBaseType == ' in block


def test_merge_replaces_an_older_block_and_keeps_the_players_filter(rules):
    mine = "Show\n\tClass == \"Rings\"\nHide\n"
    once = lf.merge(lf.render(rules, "titan"), mine)
    twice = lf.merge(lf.render(rules, "titan"), once)
    assert twice.count(lf.BEGIN) == 1 and twice.endswith(mine)


def test_save_never_touches_the_source_filter(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from poe2lab.web import server
    monkeypatch.setattr(lf, "filters_dir", lambda: tmp_path)
    (tmp_path / "mine.filter").write_text("Show\n\tClass == \"Rings\"\n", encoding="utf-8")
    client = TestClient(server.app)
    h = {"X-Poe2lab": "1"}
    client.post("/api/load", json={"name": "titan"}, headers=h)
    assert client.get("/api/lootfilter").json()["localFilters"] == ["mine.filter"]
    r = client.post("/api/lootfilter/save", json={"source": "file", "file": "mine.filter"}, headers=h).json()
    out = Path(r["path"])
    assert out.name == "mine + poe2lab titan.filter" and lf.BEGIN in out.read_text(encoding="utf-8")
    assert (tmp_path / "mine.filter").read_text(encoding="utf-8") == "Show\n\tClass == \"Rings\"\n"
    same = client.post("/api/lootfilter/save", json={"source": "file", "file": "mine.filter", "name": "mine"}, headers=h)
    assert same.status_code == 400



def test_a_build_nothing_requires_an_attribute_for():
    """When nothing requires Strength PoB leaves ReqStr out of its output; that once crashed the filter and
    item comparison for such a build."""
    from poe2lab.analysis.slots import holds
    base = {"Str": 20, "Dex": 150, "ReqDex": 140, "Int": 90, "ReqInt": 80, "SpiritUnreserved": 0}
    without = base | {"Dex": 130}
    assert holds(base, without, check_mana=False) == ["требования Dex"]
