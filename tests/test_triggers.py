"""How often triggered skills go off (poe2lab.analysis.triggers): PoB-PoE2 has no Energy, poe2lab estimates it."""
import pytest

from poe2lab.analysis import triggers as tr
from poe2lab.analysis.threats import MapProfile
from poe2lab.profile import open_build


def test_crit_energy_against_a_boss_and_a_pack():
    """Cast on Critical with a 1 s spell (100 Energy a trigger), 1 Energy per monster power per crit, Energy x2.5:
    a boss (power 20) fills it in two crits; a crit dealing 16 times the Ailment Threshold fills it at once if
    all of that counts. A pack: 3 normal monsters (power 1) under an area hit."""
    row = {"group": 1, "name": "Strike", "dps": 1e6, "speed": 5.0, "hitChance": 100, "crit": 100, "hit": 16e4,
           "threshold": 1e4}
    types = {(1, "Strike"): {"Attack", "Melee", "Area"}}
    feeders = {"crit": row}
    boss = [tr._rate({"crit": 100}, feeders, types, 2.5, 100, capped, "boss") for capped in (True, False)]
    assert boss[0] == pytest.approx(5 * 20 * 2.5 / 100) and boss[1] == pytest.approx(5)  # once per crit at most
    pack = [tr._rate({"crit": 100}, feeders, types, 2.5, 100, capped, "pack") for capped in (True, False)]
    assert pack[0] == pytest.approx(15 * 1 * 2.5 / 100) and pack[1] == pytest.approx(15 * 16 * 2.5 / 100)
    # a skill the player does not use - triggered, or socketed in a meta gem - feeds nothing
    assert tr._feeder([row], {(1, "Strike"): {"Attack", "Triggered"}}, "crit", set()) is None
    assert tr._feeder([row], types, "crit", {(1, "Strike")}) is None
    assert tr._feeder([row], types, "hit", set()) is row and tr._feeder([row], {(1, "Strike"): {"Spell"}}, "hit", set()) is None


def test_energy_modifiers_from_passives():
    inc, more = tr._energy_modifiers(["Meta Skills gain 35% more Energy", "20% increased Energy Shield",
                                       "Meta Skills gain 10% increased Energy"])
    assert more == pytest.approx(1.35) and inc == 10


def test_a_storm_hits_for_its_duration():
    assert tr._per_trigger({"hitSpeed": 4, "duration": 5}, 100) == 2000
    assert tr._per_trigger({"hitSpeed": 0, "duration": 5}, 100) == 100


def test_the_meta_gems_of_a_build():
    engine, bp = open_build("elemental-storm")
    view = {x["gem"]: x for x in tr.trigger_view(engine, MapProfile(rage=bp.rage).config())}
    coea = view["Cast on Elemental Ailment"]
    assert coea["kind"] == "energy" and coea["cost"] > 0
    # the spells it triggers do not feed it; the player's own skills do
    assert {f["event"] for f in coea["fed"]} <= {"ignite", "shock", "freeze"}
    assert not {f["skill"] for f in coea["fed"]} & {"Firestorm", "Living Bomb", "Orb of Storms"}
    fire = coea["skills"][0]
    assert fire["name"] == "Firestorm" and all(lo <= hi for lo, hi in fire["rate"].values())
    assert fire["dps"]["boss"][0] < fire["pobDps"]  # PoB prices it as if cast by hand
    # Spellslinger gains Energy by the cast time of spells: not counted, said so
    assert view["Spellslinger"]["unknown"] == ["cast_time"]
    # the ascendancy's storm on spell crits: as often as its cooldown lets, its hits for the storm's duration
    storm = view["Elemental Storm"]
    s = storm["skills"][0]
    assert storm["kind"] == "crit" and s["rate"]["boss"][0] <= 1 / s["cooldown"] + 1e-9 and s["perTrigger"] > s["hit"] > 0
