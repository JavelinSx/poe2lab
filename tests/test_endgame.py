"""Tablets and waystones (poe2lab.endgame): the tiers' lines made one, and what a modifier is for or how dangerous it is,
found from its stats - small made-up data, no game install needed."""
from poe2lab import endgame


def test_tiers_lines_become_ranges():
    assert endgame.ranged(["5% increased Damage"], ["24% increased Damage"]) == ["5–24% increased Damage"]
    assert endgame.ranged(["Adds 2 to 4", "10% more Waystones"], ["Adds 6 to 9", "10% more Waystones"]) == \
        ["Adds 2–6 to 4–9", "10% more Waystones"]
    assert endgame.ranged(["a"], ["b", "c"]) == ["b", "c"]  # lines that do not match: the highest tier as it is


def test_goals_and_danger_from_stats():
    tag = endgame._tags
    assert tag(["map_map_item_drop_chance_+%_final_from_map", "map_item_drop_rarity_+%_final_from_map"], endgame.GOALS) == \
        ["waystones", "rarity"]
    assert tag(["map_breach_monster_splinter_quantity_+%"], endgame.GOALS) == ["mechanic"]
    assert tag(["map_additional_player_maximum_resistances_%"], endgame.DANGER)[0] == "deadly"
    assert tag(["map_monsters_damage_+%"], endgame.DANGER)[0] == "hard"
    assert tag(["map_monsters_accuracy_rating_+%"], endgame.DANGER)[0] == "mild"


def test_farm_ranks_options_by_traded_volume(monkeypatch):
    from poe2lab.economy import ninja

    def fake_get(path, league, type):
        if type == "Ritual":
            return {"core": {"rates": {"exalted": 400.0}},
                    "items": [{"id": "omen-a", "name": "Omen A"}, {"id": "omen-b", "name": "Omen B"}],
                    "lines": [{"id": "omen-a", "primaryValue": 2.0, "volumePrimaryValue": 50.0},
                              {"id": "omen-b", "primaryValue": 0.1, "volumePrimaryValue": 0.5}]}
        if type == "Currency":
            return {"items": [{"id": "divine", "name": "Divine Orb"}, {"id": "mirror", "name": "Mirror"},
                              {"id": "orb", "name": "Orb"}],
                    "lines": [{"id": "divine", "primaryValue": 1.0, "volumePrimaryValue": 9999.0},
                              {"id": "mirror", "primaryValue": 5000.0, "volumePrimaryValue": 5000.0},
                              {"id": "orb", "primaryValue": 0.5, "volumePrimaryValue": 25.0}]}
        raise OSError("no data")

    monkeypatch.setattr(ninja, "_get", fake_get)
    r = endgame.farm("Test")
    assert r["league"] == "Test" and r["exaltedPerDivine"] == 400.0
    by = {o["id"]: o for o in r["options"]}
    assert r["options"][0]["id"] == "ritual" and by["ritual"]["score"] == 1.0
    assert [d["name"] for d in by["ritual"]["drops"]] == ["Omen A"]  # too little volume for Omen B
    assert by["currency"]["volume"] == 25.0  # the base unit and the jackpot are left out
    assert "score" not in by["leveling"] and r["options"][-1]["id"] == "leveling"
