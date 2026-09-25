"""Loot filter block for a build: what it marks, its syntax, and merging on top of the player's filter."""
from pathlib import Path

import pytest

from poe2lab import lootfilter as lf
from poe2lab.analysis.report import defence_weights
from poe2lab.analysis.threats import MapProfile, survivable_hits
from poe2lab.data.moddb import ModDB
from poe2lab.engine import PobEngine

TITAN = (Path(__file__).resolve().parent / "fixtures" / "titan.txt").read_text()
KEYWORDS = {"AreaLevel", "Identified", "Rarity", "Class", "BaseType", "ItemLevel", "HasExplicitMod", "BaseArmour", "BaseEvasion",
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
    # levelling: the same families at the tiers the campaign drops, uniques' slots included
    assert by["Helmet"].unique and by["Helmet"].leveling
    assert set(by["Boots"].leveling) - set(by["Boots"].affixes)  # lower tiers the endgame list leaves out


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
    leveling = [b for b in block.split("\n\n") if "прокачка" in b]
    assert leveling and all(f"AreaLevel < {lf.LEVELING_AREA}" in b for b in leveling)
    assert sum('Class == "Rings"' in b and "HasExplicitMod >=3" in b for b in leveling) == 1  # both rings, one rule


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


def test_a_filter_chosen_in_the_dialog(tmp_path, monkeypatch):
    """The player picks their filter in a Windows dialog (anywhere); the result still goes to the game's folder."""
    from fastapi.testclient import TestClient
    from poe2lab.web import server
    game, elsewhere = tmp_path / "game", tmp_path / "downloads"
    game.mkdir()
    elsewhere.mkdir()
    mine = elsewhere / "NeverSink.filter"
    mine.write_text("Show\n\tClass == \"Rings\"\n", encoding="utf-8")
    monkeypatch.setattr(lf, "filters_dir", lambda: game)
    client = TestClient(server.app)
    h = {"X-Poe2lab": "1"}
    client.post("/api/load", json={"name": "titan"}, headers=h)
    monkeypatch.setattr(lf, "pick_filter", lambda: None)
    assert client.post("/api/lootfilter/pick", headers=h).json() == {"cancelled": True}
    monkeypatch.setattr(lf, "pick_filter", lambda: mine)
    picked = client.post("/api/lootfilter/pick", headers=h).json()
    assert picked["name"] == "NeverSink.filter"
    r = client.post("/api/lootfilter/save", json={"source": "file", "file": picked["path"]}, headers=h).json()
    assert Path(r["path"]).parent == game and r["name"] == "NeverSink + poe2lab titan"
    assert mine.read_text(encoding="utf-8") == "Show\n\tClass == \"Rings\"\n"
    # a path that was not chosen in the dialog is only looked up by name in the game's folder
    other = client.post("/api/lootfilter/save", json={"source": "file", "file": str(tmp_path / "x" / "secret.filter")},
                        headers=h)
    assert other.status_code == 400


def test_online_filters_from_the_games_copy(tmp_path, monkeypatch):
    """A subscribed online filter lives in OnlineFilters as an extensionless copy named by an id."""
    from fastapi.testclient import TestClient
    from poe2lab.web import server
    online = tmp_path / "OnlineFilters"
    online.mkdir()
    copy = online / "MNqaRoC0"
    copy.write_text("#Online Item Filter\n#name:endgamus\n#lastUpdate:2026-09-22T22:53:49Z\nShow\n\tClass == \"Rings\"\n",
                    encoding="utf-8")
    (online / "junk").write_text("not a filter", encoding="utf-8")
    monkeypatch.setattr(lf, "filters_dir", lambda: tmp_path)
    assert lf.online_filters()[0] | {"path": None} == {"path": None, "name": "endgamus", "updated": "2026-09-22"}
    assert lf.looks_like_filter(copy) and not lf.looks_like_filter(online / "junk")
    client = TestClient(server.app)
    h = {"X-Poe2lab": "1"}
    client.post("/api/load", json={"name": "titan"}, headers=h)
    assert [f["name"] for f in client.get("/api/lootfilter").json()["onlineFilters"]] == ["endgamus"]
    r = client.post("/api/lootfilter/save", json={"source": "file", "file": str(copy)}, headers=h).json()
    assert r["name"] == "endgamus + poe2lab titan" and Path(r["path"]).parent == tmp_path
    monkeypatch.setattr(lf, "pick_filter", lambda: online / "junk")
    assert client.post("/api/lootfilter/pick", headers=h).status_code == 400
    monkeypatch.setattr(lf, "pick_filter", lambda: copy)
    assert client.post("/api/lootfilter/pick", headers=h).json()["name"] == "endgamus"


def test_market_block_by_price():
    """What poe.ninja prices at the thresholds: stackable items by name, levelled ones by base from the level where
    they and every level above are worth it, uniques by base (every unique of the base worth it; or, softer, one
    worth the top)."""
    market = {"items": {"Divine Orb": {"div": 1.0}, "Chaos Orb": {"div": 0.13}, "Exalted Orb": {"div": 0.002},
                        "Uncut Skill Gem (Level 18)": {"div": 0.05}, "Uncut Skill Gem (Level 19)": {"div": 0.5},
                        "Uncut Skill Gem (Level 20)": {"div": 2.0}},
              "uniques": [{"name": "A", "base": "Silk Robe", "div": 5.0}, {"name": "B", "base": "Silk Robe", "div": 3.0},
                          {"name": "C", "base": "Fire Quiver", "div": 0.001}, {"name": "D", "base": "Fire Quiver", "div": 2.0},
                          {"name": "E", "base": "Wide Belt", "div": 0.3}]}
    blocks, summary = lf.market_blocks(market, top=1.0, low=0.1)
    assert [n for n, _ in summary["top"]] == ["Divine Orb"] and [n for n, _ in summary["low"]] == ["Chaos Orb"]
    assert summary["levelled"]["top"] == [{"base": "Uncut Skill Gem", "level": 20, "div": 2.0}]
    assert summary["levelled"]["low"] == [{"base": "Uncut Skill Gem", "level": 19, "div": 0.5}]
    assert [u["base"] for u in summary["uniques"]["top"]] == ["Silk Robe"]
    assert [u["base"] for u in summary["uniques"]["low"]] == ["Wide Belt"]
    assert [u["base"] for u in summary["maybe"]] == ["Fire Quiver"]
    text = "\n".join(blocks)
    # the most valuable first: a filter stops at the first block that matches
    assert text.index('BaseType == "Divine Orb"') < text.index('BaseType == "Chaos Orb"')
    assert text.index("ItemLevel >= 20") < text.index("ItemLevel >= 19")
    assert "Exalted Orb" not in text
    whole = lf.render([], "titan", blocks)
    assert whole.startswith(lf.BEGIN) and whole.rstrip().endswith(lf.END) and 'BaseType == "Divine Orb"' in whole


def test_market_block_keeps_only_names_the_game_knows():
    """A BaseType the game does not know makes it refuse the whole filter: such names stay out."""
    market = {"items": {"Divine Orb": {"div": 1.0}, "Thaumaturgic Flux (Level 18)": {"div": 3.0}, "Made Up Orb": {"div": 5.0}},
              "uniques": [{"name": "A", "base": "Silk Robe", "div": 5.0}, {"name": "B", "base": "Nonexistent Robe", "div": 5.0}]}
    blocks, summary = lf.market_blocks(market, top=1.0, low=0.1, valid={"Divine Orb", "Silk Robe"})
    text = "\n".join(blocks)
    assert '"Divine Orb"' in text and '"Silk Robe"' in text
    assert "Made Up Orb" not in text and "Thaumaturgic" not in text and "Nonexistent" not in text
