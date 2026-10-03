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


def db(desecrated=True):
    mods = []
    for side, stats in (("Prefix", ["Life", "Armour", "Evasion", "Mana"]), ("Suffix", ["Fire", "Cold", "Lightning", "Speed"])):
        for stat in stats:
            for tier, level in enumerate((1, 20, 40, 60, 80)):
                mods.append(mod(f"{stat}{tier}", side, f"+({tier}-{tier + 5}) to {stat}", level, stat))
    if desecrated:
        mods.append(mod("DesecratedLife", "Prefix", "+(1-2) to Life", 1, "Life", "Desecrated"))
        mods.append(mod("DesecratedMana", "Prefix", "+(1-2) to Mana", 1, "Mana", "Desecrated"))
        mods.append(mod("DesecratedSpeed", "Suffix", "+(1-2) to Speed", 1, "Speed", "Desecrated"))
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
    """Measured by the craft journal: on weapons a tier weighs half as much every 60 levels."""
    pool = Pool(db(), TAGS, 82, item_type="Two Hand Mace")
    by_level = {m.level: pool.weight[m.id] for m in pool.mods}
    assert by_level[80] / by_level[1] == pytest.approx(0.5 ** (79 / 60))
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
    assert set(by_key) == {"magic", "magic_greater", "essence", "essence_greater", "alchemy", "alchemy_whittle",
                           "fracture", "fracture_light"}
    # the essence gives one target for sure: it beats plain exalting
    assert by_key["essence"].per_base > by_key["magic"].per_base > 0
    # Omen of Greater Exaltation: two mods for one exalt - once per item, so fewer exalts for the same chance
    greater, plain = by_key["essence_greater"], by_key["essence"]
    assert greater.use["Omen of Greater Exaltation"] <= greater.bases + 1e-9
    assert greater.use["Exalted Orb"] < plain.use["Exalted Orb"]
    assert abs(greater.per_base - plain.per_base) < 0.05
    assert by_key["essence"].use["Essence of the Body"] == pytest.approx(by_key["essence"].bases)
    assert by_key["essence"].bases_p90 >= by_key["essence"].bases
    # every step says its text by key and names real items; bones finish every strategy (the fracture ones use the
    # bone on their way)
    for s in found:
        assert all(set(step) <= {"k", "n", "mod"} and step["n"] for step in s.steps)
        if not s.key.startswith("fracture"):
            assert s.steps[-1]["n"] == ["Gnawed Rib", "Omen of Abyssal Echoes"]


def test_fracturing_the_main_mod(monkeypatch):
    """The common craft: the main mod on a magic item, a regal and a bone for four mods; the Fracturing Orb does not
    touch the unrevealed one, so it locks the main mod 1 time in 3 - three fractures per success, not four."""
    monkeypatch.setattr(crafting, "ENOUGH_SUCCESSES", 600)
    monkeypatch.setattr(crafting, "MAX_ATTEMPTS", 60000)
    d = db()
    pool, dese = Pool(d, TAGS, 82), Pool(d, TAGS, 82, sets=("Desecrated",))
    only_main = {s.key: s for s in crafting.strategies(pool, [target(d, "Life")], 1, "", None, dese, "Gnawed Rib")}
    plain, light = only_main["fracture"], only_main["fracture_light"]
    assert plain.use["Fracturing Orb"] == pytest.approx(3, abs=0.2)
    # every base with the main mod gets a regal; the ones the bone could desecrate (a family free for it) get fractured
    assert plain.use["Regal Orb"] >= plain.use["Gnawed Rib"] == pytest.approx(plain.use["Fracturing Orb"])
    assert "Omen of Abyssal Echoes" not in plain.use  # the goal is met before the reveal: no reroll needed
    assert light.use["Omen of Light"] == pytest.approx(1)  # one per finished item, taken right after the fracture
    # three targets: the fractured main mod stays, annulments and exalts bring the other two
    three = [target(d, "Life"), target(d, "Fire"), target(d, "Armour")]
    monkeypatch.setattr(crafting, "ENOUGH_SUCCESSES", 40)
    found = {s.key: s for s in crafting.strategies(pool, three, 3, "", None, dese, "Gnawed Rib")}
    for key in ("fracture", "fracture_light"):
        s = found[key]
        assert s.per_base > 0 and s.use["Orb of Annulment"] > 0 and s.use["Exalted Orb"] > 0
        assert s.steps[0]["mod"] == three[0].label  # the main mod is the most wanted target
    assert found["fracture"].steps[-1] == {"k": "reveal", "n": ["Omen of Abyssal Echoes"]}
    # the main mod required: the others count only the items that have it, the fracture ways always have it
    # (two of the three wanted: without the rule an item may have the other two)
    any_two = {s.key: s for s in crafting.strategies(pool, three, 2, "", None, dese, "Gnawed Rib")}
    must = {s.key: s for s in crafting.strategies(pool, three, 2, "", None, dese, "Gnawed Rib", must_main=True)}
    assert must["magic"].per_base < any_two["magic"].per_base
    assert must["fracture"].per_base == pytest.approx(any_two["fracture"].per_base, rel=0.35)
    # no desecrated mods for the bone: no fracture way
    bare = Pool(db(desecrated=False), TAGS, 82, sets=("Desecrated",))
    assert not {"fracture", "fracture_light"} & {s.key for s in crafting.strategies(pool, three, 3, "", None, bare, "Gnawed Rib")}


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
    s = crafting.Strategy("x", [], use={"Exalted Orb": 10, "Omen": 1}, p90={"Exalted Orb": 30, "Omen": 3}, bases=4)
    prices = {"Exalted Orb": Price(0.01, False)}
    crafting.price([s], prices)
    assert s.cost == pytest.approx(0.1) and s.cost_p90 == pytest.approx(0.3) and not s.priced
    assert s.cost_per_base == pytest.approx(0.025)  # what one base of the batch eats


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
    # the main mod chosen among the base's mods; the desecration worth most (boots: no lords' omens)
    choice = next(c for c in r["choices"] if c["id"] != r["choices"][0]["id"] and c["side"])
    chosen = client.get(f"/api/craft?slot=Boots&need=2&main_mod={choice['id']}").json()
    assert chosen["mainMod"] == choice["id"] and not chosen["mainMissing"]
    assert chosen["targets"][0]["label"] == choice["label"]
    d = r["desecration"]
    assert d["lordOmens"] is False and all(o["lord"] in crafting.LORD_OMEN for o in d["options"])
    if d["best"]:
        assert d["ways"] and not any(n in crafting.LORD_OMEN.values() for w in d["ways"] for n in w["n"])


def test_targets_of_given_mods():
    """The mods of an item made for the build as craft targets: a family once, three a side at most, each at its
    top tiers for the item level."""
    from poe2lab.data.moddb import ModDB

    def mod(mid, side, group, level, line):
        return {"id": mid, "set": "Item", "type": side, "affix": "", "lines": [line], "level": level, "group": group,
                "weightKey": ["default"], "weightVal": [1], "tags": [], "tradeHashes": []}
    rows = [mod(f"P{g}{t}", "Prefix", f"P{g}", 80 - 10 * t, f"+{50 - 10 * t} to P{g}") for g in range(4) for t in range(3)]
    rows += [mod("S0", "Suffix", "S", 60, "+5% to S")]
    db = ModDB({"mods": rows, "bases": []})
    by_id = {m.id: m for m in db.mods}
    wanted = [by_id["P00"], by_id["P01"], by_id["P11"], by_id["P20"], by_id["P30"], by_id["S0"]]
    targets = crafting.targets_of(db, wanted, ["default"], 75, top_tiers=2)
    assert [(t.group, t.side) for t in targets] == [("P0", "Prefix"), ("P1", "Prefix"), ("P2", "Prefix"), ("S", "Suffix")]
    # item level 75: tier 80 cannot roll; the top two below it, the second the least
    assert targets[0].label == "+40 to P0" and targets[0].min_level == 60


def lords_db():
    """A weapon's desecrated pool: each lord two prefixes and two suffixes (as on quarterstaves)."""
    mods = []
    for lord in ("Ulaman", "Amanamu", "Kurgal"):
        for side in ("Prefix", "Suffix"):
            for k in (1, 2):
                mods.append(mod(f"AbyssMod{lord}{side}{k}", side, f"+(1-2) to {lord} {side} {k}", 65, f"{lord}{side}{k}",
                                "Desecrated"))
    return ModDB({"mods": mods, "bases": []})


def test_desecration_with_the_lords_omens(monkeypatch):
    """The bone alone offers 3 of 6 mods on the drawn side; the side omen fixes the side; the lord's omen makes one
    option a mod of his (one of his two on that side); echoes reroll once - each of them adds to the chance."""
    monkeypatch.setattr(crafting, "DESECRATE_TRIALS", 6000)
    d = lords_db()
    pool = Pool(d, TAGS, 82, sets=("Desecrated",))
    wanted = next(m for m in d.mods if m.id == "AbyssModKurgalPrefix1")
    assert crafting.lord_of(wanted) == "Kurgal"
    ways = {tuple(w["n"][1:]): w["chance"] for w in crafting.desecration_ways(pool, wanted, "Two Hand Mace", "Gnawed Jawbone")}
    side, lord, echo = "Omen of Sinistral Necromancy", "Omen of the Blackblooded", "Omen of Abyssal Echoes"
    assert ways[()] == pytest.approx(0.5 * 0.5, abs=0.03)  # the prefix side half the time, then 3 of 6 options
    assert ways[(side,)] == pytest.approx(0.5, abs=0.03)
    # his option is the wanted one half the time, else the other two of the five left may be: 1/2 + 1/2 * 2/5
    assert ways[(side, lord)] == pytest.approx(0.7, abs=0.03)
    assert ways[(side, lord, echo)] > ways[(side, lord)] > ways[(side,)] > ways[()]
    # armour: no lords' omens
    armour = crafting.desecration_ways(pool, wanted, "Boots", "Gnawed Rib")
    assert len(armour) == 4 and not any(lord in w["n"] for w in armour)
    # the cheapest way on average, a miss taken off with Omen of Light and an annulment
    prices = {n: Price(p, False) for n, p in (("Gnawed Jawbone", 0.01), (side, 0.01), (lord, 0.01), (echo, 0.1),
                                              ("Omen of Light", 7.0), ("Orb of Annulment", 0.5))}
    rows = crafting.desecration_ways(pool, wanted, "Two Hand Mace", "Gnawed Jawbone")
    best = crafting.price_desecration(rows, prices)
    assert rows[best]["n"] == ["Gnawed Jawbone", side, lord, echo]  # a miss costs 7.5 div: the likeliest wins
    assert all(w["expected"] >= rows[best]["expected"] for w in rows)


def test_a_line_means_the_bases_own_mod():
    """"+4 to Level of all Melee Skills" is a mod of several item classes: the one that rolls on the base is meant,
    so a worn affix is not dropped from the craft targets; the player's main mod leads them."""
    rows = [mod("RingSkills", "Suffix", "+(3-4) to Skills", 20, "RingSkills"),
            mod("BootsSkills", "Suffix", "+(3-4) to Skills", 20, "BootsSkills"),
            mod("BootsLife", "Prefix", "+(1-9) to Life", 20, "Life")]
    rows[0]["weightKey"] = ["ring"]
    d = ModDB({"mods": rows, "bases": []})
    assert crafting.lines_index(d, TAGS)[("+(3-4) to Skills",)].id == "BootsSkills"
    plan = type("Plan", (), {"affixes": [type("A", (), {"template": ["+(3-4) to Skills"], "score": 5.0})()],
                             "candidates": [type("C", (), {"mod_id": "BootsLife", "score": 9.0})()]})()
    assert [t.group for t in crafting.pick_targets(d, plan, TAGS, 82)] == ["Life", "BootsSkills"]
    skills = next(m for m in d.mods if m.id == "BootsSkills")
    assert [t.group for t in crafting.pick_targets(d, plan, TAGS, 82, first=skills)] == ["BootsSkills", "Life"]
