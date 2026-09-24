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


def test_tiers_roll_alike():
    """Measured by the craft journal: the top tier rolls as often as the lowest."""
    pool = Pool(db(), TAGS, 82)
    rng = random.Random(3)
    got = Counter(pool.pick(Item("rare"), rng).level for _ in range(6000))
    assert 0.8 < got[80] / got[1] < 1.25


def test_weapon_tiers_fall_with_level():
    """Measured by the craft journal: on weapons a tier weighs half as much every 50 levels."""
    pool = Pool(db(), TAGS, 82, item_type="Two Hand Mace")
    by_level = {m.level: pool.weight[m.id] for m in pool.mods}
    assert by_level[80] / by_level[1] == pytest.approx(0.5 ** (79 / 50))
    assert crafting.is_weapon("Wand") and not crafting.is_weapon("Focus") and not crafting.is_weapon("Ring")


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
    assert set(by_key) == {"magic", "magic_greater", "essence", "essence_greater", "alchemy", "alchemy_whittle"}
    # the essence gives one target for sure: it beats plain exalting
    assert by_key["essence"].per_base > by_key["magic"].per_base > 0
    # Omen of Greater Exaltation: two mods for one exalt - once per item, so fewer exalts for the same chance
    greater, plain = by_key["essence_greater"], by_key["essence"]
    assert greater.use["Omen of Greater Exaltation"] <= greater.bases + 1e-9
    assert greater.use["Exalted Orb"] < plain.use["Exalted Orb"]
    assert abs(greater.per_base - plain.per_base) < 0.05
    assert by_key["essence"].use["Essence of the Body"] == pytest.approx(by_key["essence"].bases)
    assert by_key["essence"].bases_p90 >= by_key["essence"].bases
    # every step says its text by key and names real items; bones finish every strategy
    for s in found:
        assert all(set(step) <= {"k", "n", "mod"} and step["n"] for step in s.steps)
        assert s.steps[-1]["n"] == ["Gnawed Rib", "Omen of Abyssal Echoes"]


def test_changing_a_mod_on_a_worn_item():
    d = db()
    pool, dese = Pool(d, TAGS, 82), Pool(d, TAGS, 82, sets=("Desecrated",))
    life = next(m for m in d.mods if m.id == "Life4")
    have = {("Armour", next(m for m in d.mods if m.group == "Armour").patterns)}
    add = crafting.modify_routes(d, pool, dese, [], "Boots", TAGS, 82, life, have, 1, 4, False, "Gnawed Rib")
    swap = crafting.modify_routes(d, pool, dese, [], "Boots", TAGS, 82, life, have, 3, 6, True, "Gnawed Rib")
    exalt = next(r for r in add["routes"] if r["k"] == "exalt_side")
    annul = next(r for r in swap["routes"] if r["k"] == "annul_exalt")
    # with the prefix omen, one exalt hits life among the three free prefix families - its top 4 tiers of 5
    assert exalt["chance"] == pytest.approx(1 / 3 * 4 / 5) and exalt["risk"] == "slot"
    # a swap first has to annul the right one of three prefixes
    assert annul["chance"] == pytest.approx(exalt["chance"] / 3) and annul["risk"] == "mod"
    assert {r["k"] for r in add["routes"]} == {"exalt_side", "desecrate"}  # desecrated life exists
    # a swap is always a worse bet than filling a free slot
    assert swap["chance"] < add["chance"] and add["verdict"] in ("worth", "risky")


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


def test_craft_guide_prices(client):
    r = client.get("/api/craft/guide").json()
    assert set(r) == {"prices", "league", "exaltedPerDivine"}
    assert set(r["prices"]) <= set(crafting.GUIDE_ITEMS)


def test_craft_endpoint(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    r = client.get("/api/craft?slot=Boots&need=2&item_level=82").json()
    assert r["base"] and 1 <= len(r["targets"]) <= 6 and r["need"] == 2
    assert {s["key"] for s in r["strategies"]} >= {"magic", "alchemy"}
    assert any(s["per_base"] > 0 for s in r["strategies"])
    # looser targets ("any" tier of the wanted mods) are easier to hit than the top tiers
    top = client.get("/api/craft?slot=Boots&need=2&quality=top").json()
    loose = client.get("/api/craft?slot=Boots&need=2&quality=any").json()
    best = lambda x: max(s["per_base"] for s in x["strategies"])
    assert best(loose) > best(top)
    assert client.get("/api/craft?slot=Nowhere").status_code == 400
