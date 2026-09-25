"""A replacement from the trade site: what to ask for, the listings as items PoB reads, prices, the site's limits,
and the whole search with the site stood in for (no network in tests)."""
import pytest
from fastapi.testclient import TestClient

from poe2lab.economy import trade
from poe2lab.economy.ninja import Price, PriceBook

H = {"X-Poe2lab": "1"}


def listing(mods, base="Bound Cuffs", price=(1, "divine"), implicit=(), rarity="Rare", **extra):
    return {"id": "x", "listing": {"price": {"type": "~price", "amount": price[0], "currency": price[1]},
                                   "whisper": "@seller Hi, I would like to buy your item", "account": {"name": "seller"}},
            "item": {"rarity": rarity, "name": "Grim Grip", "typeLine": base, "baseType": base, "ilvl": 81,
                     "implicitMods": [{"description": m} for m in implicit],
                     "explicitMods": [{"description": m, "hash": "stat.explicit.stat_1"} for m in mods], **extra}}


def test_markup_and_item_text():
    assert trade.plain("+29% to [Resistances|Cold Resistance]") == "+29% to Cold Resistance"
    assert trade.plain("Has 3 [Charm] Slots") == "Has 3 Charm Slots"
    item = listing(["+57 to [Armour]", "+82 to maximum Life"], base="Double Belt", implicit=["Has 3 [Charm] Slots"],
                   properties=[{"name": "[Quality]", "values": [["+20%", 1]]}], corrupted=True,
                   runeMods=["+10% to [Resistances|Fire Resistance]"])["item"]
    text = trade.item_text(item)
    assert text.startswith("Rarity: Rare\npoe2lab item\nDouble Belt\n")  # a rare's own name means nothing to PoB
    assert "Quality: 20" in text and "Item Level: 81" in text
    assert "Has 3 Charm Slots (implicit)" in text and "+10% to Fire Resistance (rune)" in text
    assert "+57 to Armour\n+82 to maximum Life" in text and text.endswith("Corrupted")
    assert trade.requirements({"requirements": [{"name": "Level", "values": [["44", 0]]},
                                                {"name": "[Strength|Str]", "values": [["52", 0]]}]}) == {"Level": 44, "Str": 52}


def test_prices_in_exalted_and_divine():
    book = PriceBook("L", {"chaos": Price(0.1, 5.0)}, 500.0)
    assert trade.price({"price": {"amount": 2, "currency": "divine"}}, book) == {
        "amount": 2.0, "currency": "divine", "ex": 1000.0, "div": 2.0}
    assert trade.price({"price": {"amount": 250, "currency": "exalted"}}, book)["div"] == 0.5
    assert trade.price({"price": {"amount": 3, "currency": "chaos"}}, book)["ex"] == pytest.approx(150.0)
    unknown = trade.price({"price": {"amount": 1, "currency": "mirror"}}, book)
    assert unknown["ex"] is None and unknown["amount"] == 1.0  # shown as asked
    assert trade.price({}, book) is None


def test_the_limiter_keeps_one_request_in_reserve_and_obeys_the_site():
    lim = trade.Limiter([(5, 10)])
    for t in (0.0, 1.0, 2.0, 3.0):
        assert lim.delay(t) == 0
        lim.taken(t)
    assert lim.delay(4.0) == pytest.approx(6.1)  # the fifth would use the last one: wait for the first to age out
    assert lim.delay(10.5) == 0
    headers = {"X-Rate-Limit-Ip": "5:10:60,15:60:300", "X-Rate-Limit-Ip-State": "1:10:0,14:60:0"}
    lim = trade.Limiter([])
    lim.update(headers, 100.0)
    assert lim.rules == [(5, 10), (15, 60)] and lim.blocked_until == 160.0  # other tools used the minute up
    lim.update({"X-Rate-Limit-Ip": "5:10:60", "X-Rate-Limit-Ip-State": "6:10:60"}, 200.0)
    assert lim.blocked_until == 260.0  # restricted: the site names the time


def test_queries_ask_for_the_key_mods_then_an_item_made_for_the_build():
    mods = [{"id": f"explicit.stat_{i}", "min": 10 * i, "line": f"+{i} to X", "type": "Prefix", "score": 10 - i,
             "must": i == 1, "worn": i < 3} for i in range(1, 9)]
    key, ideal = trade.queries(mods, "armour.gloves", 70, {"str": 150, "dex": 40, "int": 20})
    assert [f["id"] for f in key["body"]["query"]["stats"][0]["filters"]] == [m["id"] for m in mods[:4]]
    assert key["body"]["query"]["stats"][0]["type"] == "and" and key["body"]["sort"] == {"price": "asc"}
    reqs = key["body"]["query"]["filters"]["req_filters"]["filters"]
    assert reqs == {"lvl": {"max": 70}, "str": {"max": 150}, "dex": {"max": 40}, "int": {"max": 20}}
    relaxed = key["relaxed"]["query"]["stats"]
    assert [f["id"] for f in relaxed[0]["filters"]] == ["explicit.stat_1"]  # what must stay stays required
    assert relaxed[1] == {"type": "count", "value": {"min": 2}, "filters": relaxed[1]["filters"]}
    and_group, count_group = ideal["body"]["query"]["stats"]
    assert [f["id"] for f in and_group["filters"]] == ["explicit.stat_1"]
    assert len(count_group["filters"]) == 7 and count_group["value"]["min"] == 4  # 5 of the best 8 in all
    assert trade.category("Staff", {"warstaff"}) == "weapon.warstaff" and trade.category("Gloves", ()) == "armour.gloves"


@pytest.fixture(scope="module")
def client():
    from poe2lab.web.server import app, session
    with TestClient(app) as c:
        yield c
    session.engine = None


def test_a_search_puts_the_finds_on_the_build(client, monkeypatch):
    from poe2lab.web.server import session
    client.post("/api/load", json={"name": "titan"}, headers=H)
    known = [{"entries": [{"id": f"explicit.stat_{h}"} for m in session.db().mods for h in m.trade_hashes]}]
    monkeypatch.setattr(trade, "trade_data", lambda lang, kind: known)
    monkeypatch.setattr(session, "prices", lambda: PriceBook("Test League", {}, 500.0))
    asked = []

    def search(league, body):
        asked.append((league, body))
        return {"id": f"q{len(asked)}", "total": 2, "result": ["a", "b"]}

    # the worn gloves' own mods and more on top: surely better; a bare one: surely worse
    worn = client.get("/api/item/Gloves").json()["text"].splitlines()
    count = next(int(l.split(":")[1]) for l in worn if l.startswith("Implicits:"))
    mods = [l for l in worn[worn.index(f"Implicits: {count}") + 1 + count:] if l and not l.startswith("{")]
    good = listing(mods + ["+150 to maximum Life", "+40% to Chaos Resistance"], price=(1, "divine"))
    poor = listing(["+5 to maximum Life"], price=(10, "exalted"))
    monkeypatch.setattr(trade, "search", search)
    monkeypatch.setattr(trade, "fetch", lambda query_id, ids: [good, poor])
    r = client.post("/api/trade/search", json={"slot": "Gloves", "mode": "balanced", "threshold": 5}, headers=H).json()
    assert r["league"] == "Test League" and [s["kind"] for s in r["searches"]] == ["key", "ideal"]
    assert all(league == "Test League" for league, _ in asked)
    key = r["searches"][0]
    assert key["url"].endswith("/q1") and len(key["mods"]) == 4
    best, worst = key["items"]
    assert best["better"] and best["score"] > 5 and best["price"]["ex"] == 500.0 and best["whisper"]
    assert not worst["better"] and worst["score"] < best["score"]
    assert "+150 to maximum Life" in best["explicit"]


def test_a_site_error_is_shown_not_raised(client, monkeypatch):
    from poe2lab.web.server import session
    client.post("/api/load", json={"name": "titan"}, headers=H)
    known = [{"entries": [{"id": f"explicit.stat_{h}"} for m in session.db().mods for h in m.trade_hashes]}]
    monkeypatch.setattr(trade, "trade_data", lambda lang, kind: known)
    monkeypatch.setattr(session, "prices", lambda: None)

    def busy(league, body):
        raise trade.TradeError("торговая площадка просит паузу: попробуй через 60 с")
    monkeypatch.setattr(trade, "search", busy)
    r = client.post("/api/trade/search", json={"slot": "Gloves"}, headers=H).json()
    assert all("паузу" in s["error"] and not s["items"] for s in r["searches"])
    assert client.post("/api/trade/search", json={"slot": "Flask 1"}, headers=H).status_code == 400
