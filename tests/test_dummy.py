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
