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
