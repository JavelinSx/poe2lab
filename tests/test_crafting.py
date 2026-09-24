"""Crafting from a white base: the mod pool obeys the game's rules, strategies are played out and priced."""
import random
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from poe2lab import crafting
from poe2lab.crafting import Item, Pool, Target
from poe2lab.data.moddb import ModDB
from poe2lab.economy.ninja import Price
from poe2lab.web.server import app, session

H = {"X-Poe2lab": "1"}
TAGS = ["boots", "armour", "default"]


def mod(id_, type_, line, level, group, set_="Item"):
    return {"id": id_, "set": set_, "type": type_, "affix": id_, "lines": [line], "level": level, "group": group,
            "weightKey": ["boots"], "weightVal": [1000], "tags": [], "tradeHashes": []}


def db():
    mods = []
    for side, stats in (("Prefix", ["Life", "Armour", "Evasion", "Mana"]), ("Suffix", ["Fire", "Cold", "Lightning", "Speed"])):
        for stat in stats:
            for tier, level in enumerate((1, 20, 40, 60, 80)):
                mods.append(mod(f"{stat}{tier}", side, f"+({tier}-{tier + 5}) to {stat}", level, stat))
    mods.append(mod("DesecratedLife", "Prefix", "+(1-2) to Life", 1, "Life", "Desecrated"))
    return ModDB({"mods": mods, "bases": []})


def target(d, group, level=60):
    m = next(x for x in d.mods if x.group == group)
    return Target(group, m.patterns, m.type, level, m.lines[0])


def test_pick_keeps_sides_families_and_min_level():
    d = db()
    pool = Pool(d, TAGS, 82)
    rng = random.Random(1)
    for _ in range(200):
        item = Item("magic")
        item.mods.append(pool.pick(item, rng))
        second = pool.pick(item, rng)
        assert second.type != item.mods[0].type  # magic: one prefix and one suffix at most
    item = Item("rare")
    while (m := pool.pick(item, rng, min_level=50)) is not None:
        item.mods.append(m)
    assert len(item.mods) == 6 and len(item.families()) == 6
    assert all(m.level >= 50 for m in item.mods)
    assert pool.pick(Item("rare", list(item.mods)), rng, side="Prefix") is None  # no room left


def test_high_tiers_are_rarer():
    pool = Pool(db(), TAGS, 82)
    rng = random.Random(3)
    got = Counter(pool.pick(Item("rare"), rng).level for _ in range(6000))
    assert got[1] > 3 * got[80] > 0  # level 80 weighs 0.5 ** (79 / 25) ~ 1/9 of level 1


def test_item_level_limits_the_pool():
    pool = Pool(db(), TAGS, 30)
    assert max(m.level for m in pool.mods) == 20


def test_strategies_with_an_essence_and_bones():
    d = db()
    targets = [target(d, "Life"), target(d, "Fire")]
    life_top = next(m for m in d.mods if m.id == "Life4")
    found = crafting.strategies(Pool(d, TAGS, 82), targets, 2, "", ("Essence of the Body", life_top),
                                Pool(d, TAGS, 82, sets=("Desecrated",)), crafting.bone_for("Boots"))
    by_key = {s.key: s for s in found}
    assert set(by_key) == {"magic", "magic_omens", "essence", "essence_omens", "alchemy", "alchemy_whittle"}
    # the essence gives one target for sure: it beats plain exalting
    assert by_key["essence"].per_base > by_key["magic"].per_base > 0
    # side omens do not change the chance (the side fills with random mods either way), but a dud shows sooner:
    # fewer exalts wasted per finished item
    omens, plain = by_key["essence_omens"], by_key["essence"]
    assert abs(omens.per_base - plain.per_base) < 0.05
    assert omens.use["Exalted Orb"] < plain.use["Exalted Orb"]
    assert by_key["essence"].use["Essence of the Body"] == pytest.approx(by_key["essence"].bases)
    assert by_key["essence"].bases_p90 >= by_key["essence"].bases
    # every step says its text by key and names real items; bones finish every strategy
    for s in found:
        assert all(set(step) <= {"k", "n", "mod"} and step["n"] for step in s.steps)
        assert s.steps[-1]["n"][0] == "Gnawed Rib"


def test_price_in_divines():
    s = crafting.Strategy("x", [], use={"Exalted Orb": 10, "Omen": 1}, p90={"Exalted Orb": 30, "Omen": 3})
    prices = {"Exalted Orb": Price(0.01, False)}
    crafting.price([s], prices)
    assert s.cost == pytest.approx(0.1) and s.cost_p90 == pytest.approx(0.3) and not s.priced


def test_bones_by_item_class():
    assert crafting.bone_for("Ring") == "Gnawed Collarbone"
    assert crafting.bone_for("Helmet") == "Gnawed Rib"
    assert crafting.bone_for("Two Hand Mace") == "Gnawed Jawbone"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    session.engine = None


def test_craft_endpoint(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    r = client.get("/api/craft?slot=Boots&need=2&item_level=82").json()
    assert r["base"] and 1 <= len(r["targets"]) <= 4 and r["need"] == 2
    assert {s["key"] for s in r["strategies"]} >= {"magic", "alchemy"}
    assert any(s["per_base"] > 0 for s in r["strategies"])
    assert client.get("/api/craft?slot=Nowhere").status_code == 400
