import math
"""The dummy (poe2lab.analysis.dummy): which dummy a skill hits by its area or its projectiles' way, the mirrors'
copies, how often a skill is used."""
from poe2lab.analysis import dummy
from poe2lab.analysis.dummy import Dummy

AREA = {"projectile": False, "radius": 2.0, "radius2": 0, "projectiles": 1, "pierce": 0, "returns": False}
BOLT = {"projectile": True, "radius": 0, "radius2": 0, "projectiles": 1, "pierce": 0, "returns": False}
LINE = [Dummy("a", 4, 0), Dummy("b", 6, 0), Dummy("c", 6, 5)]


def test_an_area_hits_the_dummies_within_its_radius():
    hits = dummy.hits_per_use(AREA, {"x": 5, "y": 0}, LINE, [])
    assert hits == {"a": 1, "b": 1, "c": 0}


def test_a_projectile_stops_at_the_first_dummy_unless_it_pierces_and_comes_back_when_it_returns():
    assert dummy.hits_per_use(BOLT, {"x": 10, "y": 0}, LINE, []) == {"a": 1, "b": 0, "c": 0}
    pierce = dummy.hits_per_use(BOLT | {"pierce": 100, "returns": True}, {"x": 10, "y": 0}, LINE, [])
    assert pierce == {"a": 2, "b": 2, "c": 0}


def test_a_mirror_on_the_way_copies_the_projectile_all_around():
    # the dummy off the line is reached only by a copy from the mirror next to it
    hits = dummy.hits_per_use(BOLT | {"pierce": 100}, {"x": 10, "y": 0}, LINE, [(6, 0.3)])
    assert hits["c"] == 0  # no copy flies exactly at it (7 copies 51 degrees apart, the first along the way)
    hits = dummy.hits_per_use(BOLT | {"pierce": 100}, {"x": 10, "y": 0}, [Dummy("d", 9, 0)], [(6, 0.0)])
    assert hits["d"] == 2  # the projectile and its copy that flies on


def test_how_often_a_skill_is_used():
    s = {"speed": 2.0, "cooldown": 0.0}
    assert dummy.uses_per_second(s, {"mode": "spam", "share": 50}) == 1.0
    assert dummy.uses_per_second(s | {"cooldown": 4.0}, {"mode": "spam", "share": 100}) == 0.25
    assert dummy.uses_per_second(s, {"mode": "interval", "interval": 4}) == 0.25
    assert dummy.uses_per_second(s, {"mode": "rate", "rate": 3}) == 3.0
    assert dummy.uses_per_second(s, {"mode": "sustain"}) == 2.0


BOLT_SIM = BOLT | {"id": "fb", "pierce": 100, "returns": True, "speedMod": 1.0, "projectiles": 1,
                   "speed": 1.0, "cooldown": 1.0}
MIRROR = {"cooldown": 0.5, "duration": 8.0}


def test_flown_projectiles_pierce_return_and_hit_harder_after_a_pierce():
    seen = []
    run = dummy.simulate([(BOLT_SIM, {"mode": "cooldown", "x": 10, "y": 0, "speed": 20})], [Dummy("a", 4, 0), Dummy("b", 6, 0)],
                         [], None, lambda s, d, pierced: seen.append(pierced) or 1.0)
    st = run["stats"]["fb"]
    assert st["casts"] == 10 and st["shattered"] == 0
    assert 0 in seen and 1 in seen  # the first dummy unpierced, the next ones after a pierce
    assert run["damage"]["fb"]["a"] >= 19  # there and back, ten casts


def test_mirrors_copy_projectiles_and_the_copies_shatter_more_mirrors():
    args = ([(BOLT_SIM, {"mode": "cooldown", "x": 10, "y": 0, "speed": 20})], [Dummy("a", 9, 0)])
    plain = dummy.simulate(*args, [], MIRROR, lambda s, d, p: 1.0)
    chain = dummy.simulate(*args, [(3, 0), (3 + 6 * 0.62, 6 * 0.78), (0, 3), (-3, 0)], MIRROR, lambda s, d, p: 1.0)
    st = chain["stats"]["fb"]
    assert st["shattered"] > st["casts"]  # a copy found another mirror
    assert chain["damage"]["fb"]["a"] > plain["damage"]["fb"]["a"]


def test_what_pob_leaves_out_is_read_by_when_it_holds_in_the_flight():
    parses = lambda line: not line.startswith("Projectiles")  # noqa: E731  (PoB reads the rest without who it is about)
    got = dummy.flight_line("Projectiles deal 50% increased Damage with Hits for each time they have Pierced", parses)
    assert got == {"when": "perPierce", "line": "50% increased Damage with Hits", "kind": None}
    assert dummy.flight_line("20% more Projectile Damage after Piercing an Enemy", parses)["when"] == "afterPierce"
    assert dummy.flight_line("Attack Projectiles Return if they Pierced at least 3 times", parses) == {
        "when": "returns", "kind": "Attack", "after": 3}
    assert dummy.flight_line("Projectiles from Supported Skills Return to you", parses)["after"] == 0
    assert dummy.flight_line("Limit 4 Mirrors of Refraction", parses) is None


def test_each_skill_gets_its_own_gems_lines_and_its_weapon_sets_gear_the_quiver_grown_by_the_bow():
    from poe2lab.knowledge import Gap
    gaps = [Gap("item", "Drillneck (Weapon 2 Swap)", "x", "Projectiles have 38% increased Critical Hit chance for each "
                "time they have Pierced", True),
            Gap("item", "Drillneck (Weapon 2 Swap)", "y", "Attack Projectiles Return if they Pierced at least 3 times", True),
            Gap("skill", "Frostbolt (группа 3)", "s", "20% more Projectile Damage after Piercing an Enemy", True),
            Gap("skill", "Spell Cascade (группа 6)", "c", "Supported Skills Cascade to either side", True)]
    items = {"Weapon 1 Swap": {"type": "Bow", "explicit": [{"line": "292% increased bonuses gained from Equipped Quiver"}]},
             "Weapon 2 Swap": {"type": "Quiver"}}
    args = (gaps, {"index": 3}, "Frostbolt", [], items)
    on_two = dummy.beyond_pob(*args, 2, {"Spell", "Projectile"}, lambda line: True)
    assert [f["line"] for f in on_two["flight"]] == ["Projectiles have 149% increased Critical Hit chance",
                                                     "20% more Projectile Damage"]
    assert on_two["returnAfter"] == 0  # attacks' return, Frostbolt is a spell
    assert [f["line"] for f in dummy.beyond_pob(*args, 1, {"Spell", "Projectile"}, lambda line: True)["flight"]] == [
        "20% more Projectile Damage"]
    shot = dummy.beyond_pob(gaps, {"index": 11}, "Bow Shot", [], items, 2, {"Attack", "Projectile"}, lambda line: True)
    assert shot["returnAfter"] == 3 and not shot["notCounted"]


def test_a_mirror_lets_out_its_count_in_place_of_the_projectile_each_a_pierce_on(monkeypatch):
    monkeypatch.setattr(dummy, "SIM_WARMUP", 0.0)
    monkeypatch.setattr(dummy, "SIM_TIME", 1.0)
    seen = []
    bolt = BOLT_SIM | {"returns": False, "pierce": 100, "duration": 0}
    run = dummy.simulate([(bolt, {"mode": "cooldown", "x": 10, "y": 0, "speed": 20, "range": 12})], [Dummy("a", 6, 0)],
                         [(3, 0)], {"cooldown": 100.0, "duration": 100.0, "copies": 5, "limit": 1},
                         lambda s, d, pierced: seen.append(pierced) or 1.0)
    st = run["stats"]["fb"]
    assert st["shattered"] == 1 and st["copies"] == 5
    assert seen == [1]  # the original is gone; the copy on its way reaches the dummy a pierce on


def test_a_big_boss_is_hit_by_projectiles_passing_beside_it():
    line = dummy.Dummy("b", 9, 1.8, "pinnacle", 2.5)
    small = dummy.Dummy("b", 9, 1.8, "normal", 0.6)
    assert dummy.hits_per_use(BOLT, {"x": 10, "y": 0}, [line], [])["b"] == 1
    assert dummy.hits_per_use(BOLT, {"x": 10, "y": 0}, [small], [])["b"] == 0


def test_a_wall_along_its_fissures_and_cascades_and_pillars_around_you():
    wall = {"wall": 2.1, "alongFissure": True, "fissures": 1, "cascades": 1}
    spots = dummy.crystal_spots(wall, 10, 0)
    assert len(spots) == 3 * 2 * 4  # cascades either side, two fissures, a crystal every 0.7 m of 2.1 m
    assert min(x for x, _ in spots) >= dummy.WALL_FROM - 0.01  # from the character outwards
    across = dummy.crystal_spots({"wall": 2.1}, 10, 0)
    assert {x for x, _ in across} == {10.0} and len(across) == 4
    pillars = dummy.crystal_spots({"pillars": 9, "spread": 4.0}, 10, 0)
    assert len(pillars) == 9 and all(math.hypot(x, y) <= 4.0 + 1e-6 for x, y in pillars)


def test_a_projectile_through_crystals_pierces_them_and_breaks_them_into_explosions(monkeypatch):
    monkeypatch.setattr(dummy, "SIM_WARMUP", 0.0)
    monkeypatch.setattr(dummy, "SIM_TIME", 1.0)
    seen = []
    bolt = BOLT_SIM | {"returns": False, "pierce": 100, "duration": 0}
    wall = {"id": "fw", "projectile": False, "speed": 0, "cooldown": 100.0,
            "crystal": {"wall": 1.4, "alongFissure": True, "life": 1.0, "explosionRadius": 1.0, "duration": 10.0}}
    run = dummy.simulate([(bolt, {"mode": "cooldown", "x": 10, "y": 0, "speed": 20, "range": 12})], [Dummy("a", 6, 0)],
                         [], None, lambda s, d, pierced: seen.append((d.id, pierced)) or 2.0,
                         [(wall, {"mode": "cooldown", "x": 10, "y": 0})], lambda s, d: 5.0)
    assert ("a", 3) in seen  # three crystals on the way: three pierces before the dummy
    assert run["crystalStats"]["fw"]["broken"] == 3 and run["explosions"]["fw"]["a"] == 0  # 1 m: too far from it
