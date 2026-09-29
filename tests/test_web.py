"""Web API: open a build, read analyses, compare an item, reject a bad profile, AI settings, local-only guard."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poe2lab import itemcraft
from poe2lab.web.server import app, session

H = {"X-Poe2lab": "1"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    session.engine = None


@pytest.fixture
def settings_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("POE2LAB_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    return tmp_path


def test_status_and_build_list(client):
    s = client.get("/api/status").json()
    assert "llm" in s
    names = {b["name"] for b in client.get("/api/builds").json()}
    assert {"titan", "monk"} <= names


def test_page_versions_its_scripts(client):
    html = client.get("/").text
    assert "/static/app.js?v=" in html and "/static/i18n.js?v=" in html


def test_load_report_and_compare(client):
    b = client.post("/api/load", json={"name": "titan"}, headers=H).json()
    assert b["mainSkill"] == "Furious Slam" and b["info"]["ascendancy"] == "Titan"
    r = client.get("/api/report?mode=balanced").json()
    assert r["damageRange"]["high"] > r["damageRange"]["low"] > 0
    assert any(g["title"] == "Слабость к физическим ударам" for g in r["gates"])
    text = client.get("/api/item/Weapon 1 Swap").json()["text"]
    same = client.post("/api/compare", json={"slot": "Weapon 1 Swap", "text": text}, headers=H).json()
    assert abs(same["dps_pct"]) < 1e-6
    # the candidate comes back as the page shows items: the same lines as the equipped one
    worn = next(i for i in b["items"] if i["slot"] == "Weapon 1 Swap")
    assert same["item"]["explicit"] == worn["explicit"] and same["item"]["baseName"] == worn["baseName"]


def test_levelling_by_the_build_s_target(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    assert client.get("/api/skills?view=leveling&of=target").status_code == 400  # no target yet
    session.bp.target = "monk"  # as if the profile named the guide
    r = client.get("/api/skills?view=leveling&of=target").json()
    assert r["of"] == "monk" and r["plans"] and r["timeline"]
    assert any(p["skill"] != "Furious Slam" for p in r["plans"])  # the guide's skills, not the titan's


def test_reference_gear_for_the_inventory_view(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    g = client.get("/api/versus/gear?ref=monk").json()
    assert g["name"] == "monk" and g["class"] == "Monk" and g["level"] > 0
    helmet = next(i for i in g["items"] if i["slot"] == "Helmet")
    assert helmet["rarity"] and helmet["baseName"] and helmet["explicit"]
    assert all({"implicit", "runes", "enchant", "quality"} <= set(i) for i in g["items"])


def test_mechanics_lists_pob_gaps(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    gaps = client.get("/api/mechanics").json()["gaps"]
    assert any("Druidic Prowess" in g["what"] for g in gaps)


def test_bad_profile_is_rejected_without_writing(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    r = client.put("/api/profile", json={"corrections": [{"mod": "not a mod", "uptime": 1}]}, headers=H)
    assert r.status_code == 400 and "не понимает" in r.json()["detail"]


def test_state_changes_need_the_header_and_a_local_host(client):
    assert client.post("/api/load", json={"name": "titan"}).status_code == 403
    assert client.put("/api/llm", json={"provider": "deepseek"}).status_code == 403
    assert client.get("/api/status", headers={"host": "evil.example"}).status_code == 403


def test_llm_settings_store_key_privately(client, settings_dir):
    r = client.put("/api/llm", json={"provider": "deepseek", "api_key": "sk-test-1234567890"}, headers=H).json()
    ds = next(p for p in r["providers"] if p["id"] == "deepseek")
    assert ds["keyHint"] == "…7890" and "sk-test" not in json.dumps(r)
    assert r["active"]["configured"] and r["active"]["model"] == "deepseek-flash"
    stored = json.loads((settings_dir / "poe2lab" / "llm.json").read_text(encoding="utf-8"))
    assert stored["keys"]["deepseek"] == "sk-test-1234567890"
    # empty key keeps the stored one; clear removes it
    client.put("/api/llm", json={"provider": "deepseek", "model": "deepseek-v4-pro"}, headers=H)
    assert json.loads((settings_dir / "poe2lab" / "llm.json").read_text())["keys"]["deepseek"] == "sk-test-1234567890"
    r = client.put("/api/llm", json={"provider": "deepseek", "clear_key": True}, headers=H).json()
    assert not r["active"]["configured"]


def test_llm_settings_validation(client, settings_dir):
    assert client.put("/api/llm", json={"provider": "nope"}, headers=H).status_code == 400
    assert client.put("/api/llm", json={"provider": "custom", "base_url": "ftp://x"}, headers=H).status_code == 400
    ok = client.put("/api/llm", json={"provider": "ollama", "model": "llama3"}, headers=H).json()
    assert ok["active"]["configured"] and ok["active"]["provider"] == "ollama"  # no key needed


def test_chat_without_configuration_explains(client, settings_dir):
    r = client.post("/api/chat", json={"message": "привет"}, headers=H)
    assert r.status_code == 400 and "Ассистент" in r.json()["detail"]


def test_mod_search_finds_parseable_mods_in_both_languages(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    ru = client.get("/api/mods/search", params={"q": "скорость умений"}).json()["results"]
    assert ru[0]["en"] == "#% increased Skill Speed" and ru[0]["line"] == "1% increased Skill Speed"
    en = client.get("/api/mods/search", params={"q": "maximum life"}).json()["results"]
    assert any(r["line"] == "+1 to maximum Life" for r in en)


def test_stale_build_requests_are_refused(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    assert client.get("/api/mechanics", params={"build": "monk"}).status_code == 409
    assert client.get("/api/mechanics", params={"build": "titan"}).status_code == 200


def test_unknown_build_is_a_clean_error(client):
    r = client.post("/api/load", json={"name": "no such build"}, headers=H)
    assert r.status_code == 400


def test_tree_art_is_sent_packed_for_the_browser_to_unpack(client):
    """PoB's tree textures go out as they are, zstd-packed: the browser unpacks them (Content-Encoding)."""
    from poe2lab.web.server import TREE_DATA
    version = sorted(p.name for p in TREE_DATA.iterdir() if (p / "tree.lua").is_file())[-1]
    file = next(p.name for p in (TREE_DATA / version).glob("background_*.dds.zst"))
    url = f"/api/tree/art/{version}/{file}"
    assert client.get(url, headers={"Accept-Encoding": "gzip"}).status_code == 406  # the page then draws without art
    with client.stream("GET", url, headers={"Accept-Encoding": "gzip, deflate, br, zstd"}) as res:
        assert res.status_code == 200 and res.headers["content-encoding"] == "zstd"
        assert b"".join(res.iter_raw())[:4] == bytes.fromhex("28b52ffd")  # a zstd frame, not re-packed
    assert client.get(f"/api/tree/art/{version}/tree.lua").status_code == 404
    assert client.get(f"/api/tree/art/..%2F..%2Fsrc/{file}").status_code == 404


def test_the_league_is_the_player_s_choice(client, settings_dir, monkeypatch):
    from poe2lab.economy.ninja import PriceBook
    from poe2lab.economy import ninja
    client.post("/api/load", json={"name": "titan"}, headers=H)
    monkeypatch.setattr(session, "prices", lambda: PriceBook(ninja.chosen_league() or "Now", {}, 500.0))
    r = client.put("/api/leagues", json={"league": "Standard"}, headers=H).json()
    assert r["chosen"] == "Standard" and r["current"] == "Standard"
    assert json.loads((settings_dir / "poe2lab" / "market.json").read_text(encoding="utf-8"))["league"] == "Standard"
    r = client.put("/api/leagues", json={"league": None}, headers=H).json()
    assert r["chosen"] is None and r["current"] == "Now"  # back to poe.ninja's current league


def test_a_profile_the_build_cannot_open_with_is_not_kept(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    before = client.get("/api/build").json()["profileRaw"]
    bad = dict(before, corrections=[{"mod": "+10 to Strength", "source": "t", "bogus": 1}])
    r = client.put("/api/profile", json=bad, headers=H)
    assert r.status_code == 400 and "профиль не сохранён" in r.json()["detail"]
    assert client.get("/api/build").json()["profileRaw"] == before
    b = client.get("/api/build").json()
    assert b["info"]["mainActiveSkill"] >= 1


def test_jewels_in_the_tree_s_sockets(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    client.post("/api/tree/reset", headers=H)
    sockets = client.get("/api/jewels").json()["sockets"]
    filled = [s for s in sockets if s["item"]]
    assert len(filled) >= 2 and all(s["near"] and "dps" in s["without"] for s in filled)
    first, second = filled[:2]
    cat = client.get("/api/jewels/catalog").json()
    assert {"Ruby", "Emerald", "Sapphire"} <= {b["name"] for b in cat["bases"]}
    assert "Diamond" not in {b["name"] for b in cat["bases"]}  # uniques only
    ruby = next(b for b in cat["bases"] if b["name"] == "Ruby")
    prefixes = [m for m in ruby["mods"] if m["type"] == "Prefix" and m["set"] == "Jewel"]
    # a jewel made on a base: previewed against the one in the socket, with the game's limits
    craft = {"node": first["node"], "base": "Ruby", "rarity": "rare",
             "mods": [{"id": prefixes[0]["id"], "roll": 1}, {"id": prefixes[1]["id"], "roll": 0}]}
    p = client.post("/api/jewels/preview", json=craft, headers=H).json()
    assert p["item"]["type"] == "Jewel" and len(p["item"]["explicit"]) >= 2 and "dps" in p["change"]
    too_many = craft | {"rarity": "magic"}
    r = client.post("/api/jewels/preview", json=too_many, headers=H)
    assert r.status_code == 400 and "префиксов не больше 1" in r.json()["detail"]
    weapon = client.get("/api/item/Weapon 1").json()["text"]
    r = client.post("/api/jewels/preview", json={"node": first["node"], "text": weapon}, headers=H)
    assert r.status_code == 400 and "не самоцвет" in r.json()["detail"]
    # a unique into one socket, the other taken out: edits of the plan
    adorned = next(u for u in cat["uniques"] if u["name"] == "The Adorned")
    plan = client.post("/api/jewels/set", json={"node": first["node"], "unique": adorned["name"], "roll": 1}, headers=H).json()
    assert plan["log"][-1] == {"action": "jewel", "target": first["near"], "added": "The Adorned, Diamond",
                               "removed": first["item"]["name"]}
    r = client.post("/api/jewels/preview", json={"node": second["node"], "unique": "The Adorned"}, headers=H)
    assert r.status_code == 400 and "не больше 1" in r.json()["detail"]  # Limited to: 1
    client.post("/api/jewels/remove", json={"node": second["node"]}, headers=H)
    now = {s["node"]: s["item"] for s in client.get("/api/jewels").json()["sockets"]}
    assert now[first["node"]]["name"] == "The Adorned, Diamond" and not now[second["node"]]
    # reset: the build's own jewels are back
    client.post("/api/tree/reset", headers=H)
    back = {s["node"]: s["item"] and s["item"]["name"] for s in client.get("/api/jewels").json()["sockets"]}
    assert back == {s["node"]: s["item"] and s["item"]["name"] for s in sockets}


def test_a_jewel_copied_from_the_russian_client(client):
    """The advanced copy names each affix: a jewel's are found among the jewel mods."""
    import re
    from poe2lab import gamedata, journal
    client.post("/api/load", json={"name": "titan"}, headers=H)
    node = client.get("/api/jewels").json()["sockets"][0]["node"]
    ruby = next(b for b in client.get("/api/jewels/catalog").json()["bases"] if b["name"] == "Ruby")
    m = next(m for m in ruby["mods"] if m["set"] == "Jewel" and len(m["lines"]) == 1 and "(" in m["lines"][0])
    balance = gamedata.RAW / "data/balance"
    ids = [r["Id"] for r in gamedata.read_table(balance / "mods.datc64", ["Id"])]
    affix = journal._variants(list(gamedata.read_table(balance / "russian/mods.datc64", ["Name"]))[ids.index(m["id"])]["Name"])[0]
    line = re.sub(r"\((\d+)-\d+\)", r"\1", m["lines"][0])  # rolled at the low end: "4(4-6)%" in the copy
    copied = re.sub(r"\((\d+)-(\d+)\)", r"\1(\1-\2)", m["lines"][0])
    side = "Префикс" if m["type"] == "Prefix" else "Суффикс"
    text = "\n".join(["Класс предмета: Самоцветы", "Редкость: Волшебный", "Рубин", "--------", "Уровень предмета: 80",
                      "--------", f'{{ {side} "{affix}" (Уровень: 1) — Тег }}', copied])
    r = client.post("/api/jewels/preview", json={"node": node, "text": text}, headers=H)
    assert r.status_code == 200, r.json()
    assert r.json()["item"]["baseName"] == "Ruby" and r.json()["item"]["explicit"][0]["line"] == line


def test_gems_in_any_skill(client):
    """Supports into a skill by the game's rules, a skill gem swapped, a new skill, gems taken out; reset puts back."""
    client.post("/api/load", json={"name": "titan"}, headers=H)
    client.post("/api/tree/reset", headers=H)
    shape = lambda: [[x["name"] for x in g["gems"]] for g in client.get("/api/skills?view=build").json()["groups"]]  # noqa: E731
    start = shape()
    groups = client.get("/api/skills?view=build").json()["groups"]
    # the main skill has its five supports: one more is refused, and a support of a family it has is named
    main = next(g for g in groups if g["main"])
    assert sum(x["support"] for x in main["gems"]) == 5
    opts = client.get(f"/api/gems/options?group={main['index']}&kind=support").json()
    assert opts["skill"] == main["actives"][0]["name"] and opts["gems"]
    has = {x["family"]: x["name"] for x in main["gems"] if x["support"]}
    assert all(x["blocked"] == ({"code": "family", "gem": has[x["family"]]} if x["family"] in has else {"code": "full"})
               for x in opts["gems"])
    r = client.post("/api/gems/preview", json={"group": main["index"], "gem": opts["gems"][-1]["id"]}, headers=H)
    assert r.status_code == 400 and "не больше 5" in r.json()["detail"]
    # a skill with room: a support in, then another tier of it is refused
    room = next(g for g in groups if g["actives"] and g["gems"][0]["index"] == 1 and not g["gems"][0]["support"]
                and sum(x["support"] for x in g["gems"]) < 4)
    opts = client.get(f"/api/gems/options?group={room['index']}&kind=support").json()["gems"]
    families = [x["family"] for x in opts]
    pick = next(x for x in opts if not x["blocked"] and families.count(x["family"]) > 1)
    body = {"group": room["index"], "gem": pick["id"]}
    p = client.post("/api/gems/preview", json=body, headers=H).json()
    assert "dps" in p["change"] and p["own"]["before"] >= 0 and p["dropped"] == []
    r = client.post("/api/gems/set", json=body, headers=H).json()
    assert r["plan"]["log"][-1] == {"action": "gem", "target": room["actives"][0]["name"], "added": pick["name"],
                                    "level": None, "quality": 0, "removed": None, "dropped": []}
    after = client.get(f"/api/gems/options?group={room['index']}&kind=support").json()["gems"]
    twin = next(x for x in after if x["family"] == pick["family"] and x["id"] != pick["id"])
    assert twin["blocked"] == {"code": "family", "gem": pick["name"]}
    r = client.post("/api/gems/preview", json={"group": room["index"], "gem": twin["id"]}, headers=H)
    assert r.status_code == 400 and "того же вида" in r.json()["detail"]
    # ... but in its place it goes in
    at = next(x["index"] for x in client.get("/api/skills?view=build").json()["groups"][room["index"] - 1]["gems"]
              if x["name"] == pick["name"])
    assert client.post("/api/gems/preview", json=body | {"gem": twin["id"], "index": at}, headers=H).status_code == 200
    # a new skill: a skill gem at the highest level the character can use; one above it is refused
    skills = client.get("/api/gems/options?kind=skill").json()
    gem = next(x for x in skills["gems"] if x["usable"] >= 1)
    r = client.post("/api/gems/preview", json={"gem": gem["id"], "level": gem["usable"] + 1}, headers=H)
    # past the character's level, or (a character of 90 and more) past the gem's cap
    assert r.status_code == 400 and ("уровня персонажа" in r.json()["detail"] or "от 1 до" in r.json()["detail"])
    r = client.post("/api/gems/set", json={"gem": gem["id"], "quality": 20}, headers=H).json()
    added = client.get("/api/skills?view=build").json()["groups"]
    assert len(added) == len(groups) + 1 and r["plan"]["log"][-1]["level"] == gem["usable"]
    # the new skill taken out with its gem: gone again
    client.post("/api/gems/remove", json={"group": r["group"], "index": 1}, headers=H)
    assert len(client.get("/api/skills?view=build").json()["groups"]) == len(groups)
    assert client.post("/api/gems/remove", json={"group": main["index"], "index": 99}, headers=H).status_code == 400
    client.post("/api/tree/reset", headers=H)
    assert shape() == start


def test_gear_quality_sockets_and_runes(client):
    """An item's quality, rune sockets and runes by the game's rules; applied as an edit of the plan, reset puts back."""
    client.post("/api/load", json={"name": "titan"}, headers=H)
    client.post("/api/tree/reset", headers=H)
    items = client.get("/api/build").json()["items"]
    slot = next(i["slot"] for i in items if not i["corrupted"] and
                (g := client.get(f"/api/gear/item?slot={i['slot']}").json())["hasQuality"] and g["sockets"] < g["socketLimit"])
    info = client.get(f"/api/gear/item?slot={slot}").json()
    assert info["maxQuality"] == 30 and info["options"] and all("refused" in o for o in info["options"])
    free = next(o["name"] for o in info["options"] if not o["refused"] and o["limit"] != 1)
    edit = {"slot": slot, "quality": 30, "sockets": info["sockets"] + 1, "runes": info["runes"] + [free]}
    p = client.post("/api/gear/preview", json=edit, headers=H).json()
    assert "dps" in p["change"] and p["item"]["quality"] == 30
    # the game's rules
    bad = [({"quality": 31}, "от 0 до 30"), ({"sockets": info["socketLimit"] + 1}, "не больше"),
           ({"sockets": info["sockets"] - 1}, "не убрать")]
    if info["runes"] and info["runes"][0] != "None":
        bad.append(({"runes": ["None"] + info["runes"][1:]}, "не вынуть"))
    for change, text in bad:
        r = client.post("/api/gear/preview", json={"slot": slot} | change, headers=H)
        assert r.status_code == 400 and text in r.json()["detail"], (change, r.json())
    # a low quality stays low: PoB's "a pasted item counts as 20%" is not applied to the build's own item
    low = client.post("/api/gear/preview", json={"slot": slot, "quality": 0}, headers=H).json()
    assert low["item"]["quality"] == 0
    r = client.post("/api/gear/set", json=edit, headers=H).json()
    assert (r["quality"], r["sockets"], r["runes"][-1]) == (30, info["sockets"] + 1, free)
    assert r["plan"]["log"][-1]["action"] == "item" and r["plan"]["log"][-1]["added"] == [free]
    client.post("/api/tree/reset", headers=H)
    back = client.get(f"/api/gear/item?slot={slot}").json()
    assert (back["quality"], back["sockets"], back["runes"]) == (info["quality"], info["sockets"], info["runes"])


def test_a_catalyst_on_jewellery(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    client.post("/api/tree/reset", headers=H)
    jewellery = [client.get(f"/api/gear/item?slot={s}").json() for s in ("Ring 1", "Ring 2", "Amulet")]
    assert all(j["takesCatalyst"] and len(j["catalysts"]) == 13 and j["maxCatalystQuality"] >= 20 for j in jewellery)
    for j in (j for j in jewellery if j["corrupted"]):  # a corrupted one takes no catalyst
        r = client.post("/api/gear/preview", json={"slot": j["slot"], "catalyst": "Flesh", "catalyst_quality": 20}, headers=H)
        assert r.status_code == 400 and "с порчей" in r.json()["detail"]
    ring = next(j for j in jewellery if not j["corrupted"])
    slot, shown = ring["slot"], [l["line"] for l in ring["item"]["explicit"]]
    # a catalyst raises its kind of mods: one of the thirteen changes this item's lines
    raised = None
    for c in ring["catalysts"]:
        p = client.post("/api/gear/preview", json={"slot": slot, "catalyst": c["name"], "catalyst_quality": 20}, headers=H).json()
        if [l["line"] for l in p["item"]["explicit"]] != shown:
            raised = c["name"]
            break
    assert raised
    r = client.post("/api/gear/preview", json={"slot": slot, "catalyst": raised,
                                              "catalyst_quality": ring["maxCatalystQuality"] + 1}, headers=H)
    assert r.status_code == 400 and "качество катализатора" in r.json()["detail"]
    armour = next(i["slot"] for i in client.get("/api/build").json()["items"]
                  if not i["corrupted"] and i["type"] not in ("Ring", "Amulet"))
    r = client.post("/api/gear/preview", json={"slot": armour, "catalyst": "Flesh", "catalyst_quality": 20}, headers=H)
    assert r.status_code == 400 and "кольцам и амулетам" in r.json()["detail"]
    r = client.post("/api/gear/set", json={"slot": slot, "catalyst": raised, "catalyst_quality": 20}, headers=H).json()
    assert (r["catalyst"], r["catalystQuality"]) == (raised, 20) and r["plan"]["log"][-1]["catalyst"] == [raised, 20]
    client.post("/api/tree/reset", headers=H)
    back = client.get(f"/api/gear/item?slot={slot}").json()
    assert back["catalyst"] == ring["catalyst"] and [l["line"] for l in back["item"]["explicit"]] == shown


def test_an_item_of_one_s_own_for_a_slot(client):
    """Made on a base the slot takes by the game's rules, a unique, or pasted: tried on, then worn as a plan edit."""
    client.post("/api/load", json={"name": "titan"}, headers=H)
    client.post("/api/tree/reset", headers=H)
    was = {i["slot"]: i["name"] for i in client.get("/api/build").json()["items"]}
    c = client.get("/api/gear/create?slot=Gloves").json()
    assert c["bases"] and {b["type"] for b in c["bases"]} == {"Gloves"} and c["uniques"] and c["limits"]["rare"] == [3, 3]
    base = next(b for b in c["bases"] if b["level"] >= 60)
    fams = client.get(f"/api/gear/mods?slot=Gloves&base={base['name']}&item_level=82").json()["families"]
    pre = [f for f in fams if f["type"] == "Prefix" and f["set"] == "Item"]
    suf = [f for f in fams if f["type"] == "Suffix" and f["set"] == "Item"]
    assert all(f["tiers"][0]["tier"] == 1 and f["tiers"][0]["level"] >= f["tiers"][-1]["level"] for f in fams)
    mods = [{"id": f["tiers"][0]["id"], "roll": 1} for f in pre[:3] + suf[:3]]
    body = {"slot": "Gloves", "base": base["name"], "rarity": "rare", "item_level": 82, "quality": 20, "mods": mods}
    r = client.post("/api/gear/try", json=body, headers=H).json()
    assert r["item"]["baseName"] == base["name"] and len(r["item"]["explicit"]) >= 6 and "dps_pct" in r and "Quality: 20" in r["text"]
    # the game's rules
    high = next(f for f in pre if f["tiers"][0]["level"] > 1)
    for change, text in [({"mods": mods + [{"id": pre[3]["tiers"][0]["id"]}]}, "префиксов не больше 3"),
                         ({"rarity": "magic"}, "не больше 1"),
                         ({"mods": [{"id": high["tiers"][0]["id"]}], "item_level": 1}, "уровня предмета"),
                         ({"base": "Iron Ring"}, "не встаёт"),
                         ({"mods": [{"id": "nope"}]}, "не выпадает")]:
        r = client.post("/api/gear/try", json=body | change, headers=H)
        assert r.status_code == 400 and text in r.json()["detail"], (change, r.json())
    u = c["uniques"][0]
    assert client.post("/api/gear/try", json={"slot": "Gloves", "unique": u["name"], "base": u["base"]}, headers=H).status_code == 200
    r = client.post("/api/gear/equip", json=body, headers=H).json()
    assert r["plan"]["log"][-1] == {"action": "item", "target": "Gloves", "item": f"{itemcraft.RARE_TITLE}, {base['name']}",
                                    "worn": was["Gloves"]}
    client.post("/api/tree/reset", headers=H)
    assert {i["slot"]: i["name"] for i in client.get("/api/build").json()["items"]} == was


def test_a_prompt_for_any_chat_ai(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    q = "Почему я умираю от хаоса и что поменять в шмоте?"
    small = client.post("/api/chat/prompt", json={"question": q}, headers=H).json()
    full = client.post("/api/chat/prompt", json={"question": q, "size": "full"}, headers=H).json()
    assert small["topics"] == ["defence", "gear"] and small["reports"] == ["build_report", "stat_values"]
    text = small["prompt"]
    assert text.startswith("=== Мой вопрос ===\n" + q) and text.rstrip().endswith(q)  # the question first and last
    assert "Furious Slam" in text and "build_report" in text and "Надетые предметы" in text
    assert small["chars"] < full["chars"] and small["chars"] == len(text)
    assert client.post("/api/chat/prompt", json={"question": " "}, headers=H).status_code == 400


def test_a_mechanic_package_taken_at_once(client):
    client.post("/api/load", json={"name": "titan"}, headers=H)
    client.post("/api/tree/reset", headers=H)
    packs = client.get("/api/tree/packages").json()
    assert packs["packages"] and all(len(p["notables"]) >= 2 for p in packs["packages"])
    assert "levels" in packs["resources"]
    pk = packs["packages"][0]
    before = client.get("/api/tree/graph").json()["budget"]
    body = {"ids": [n["id"] for n in pk["notables"]], "mechanic": pk["mechanic"]}
    r = client.post("/api/tree/package", json=body, headers=H).json()
    graph = client.get("/api/tree/graph").json()
    taken = {n["id"] for n in graph["nodes"] if n["alloc"]}
    if r["kept"]:
        # one edit of the plan, within what the level gives (or no worse than the tree was)
        entry = r["plan"]["log"][-1]
        assert entry["target"] == "package:" + pk["mechanic"] and entry["action"] in ("add", "swap")
        assert {n["id"] for n in pk["notables"]} <= taken
        assert graph["budget"]["used"] <= max(before["total"], before["used"])
    else:  # not worth it: nothing changed, the answer says what it would have done
        assert not r["plan"] or not r["plan"]["log"]
        assert graph["budget"]["used"] == before["used"] and "dps" in r["changes"]
    assert client.post("/api/tree/package", json={"ids": [], "mechanic": "crit"}, headers=H).status_code == 422
    client.post("/api/tree/reset", headers=H)


def test_the_player_s_character_inside_a_build(tmp_path, monkeypatch):
    """A guide with the player's own character: every tab works on the character (its level, its gear), the build
    as recorded is the reference to compare with; edits are saved into the character, the guide stays."""
    from poe2lab import library, pobfiles, profile
    from poe2lab.web import server
    for module in (library, pobfiles, profile, server):
        if hasattr(module, "PROJECT_BUILDS"):
            monkeypatch.setattr(module, "PROJECT_BUILDS", tmp_path)
    monkeypatch.setattr(library, "TRASH", tmp_path / ".trash")
    fixtures = Path(__file__).resolve().parent / "fixtures"
    guide = (fixtures / "titan.txt").read_text(encoding="utf-8").strip()
    mine = (fixtures / "monk.txt").read_text(encoding="utf-8").strip()
    with TestClient(server.app) as c:
        c.post("/api/builds", json={"name": "Гайд", "code": guide}, headers=H)
        b = c.post("/api/load", json={"name": "Гайд"}, headers=H).json()
        assert b["main"] is None and b["guide"] is None
        assert c.post("/api/character", json={"code": "не код"}, headers=H).status_code == 400
        b = c.post("/api/character", json={"code": mine}, headers=H).json()
        info = library.describe_code(mine)
        assert b["main"]["level"] == info["level"] and b["guide"]["ascendancy"] == "Titan"
        assert b["info"]["level"] == info["level"] and b["info"]["class"] == info["class"]  # the tabs see the character
        assert [e["hasMain"] for e in c.get("/api/builds").json() if e["name"] == "Гайд"] == [True]
        assert all(not e["name"].endswith(".main") for e in c.get("/api/builds").json())
        # the build as recorded is the reference: its gear and numbers against the character's
        ref = c.get("/api/versus/gear?ref=@build").json()
        assert ref["ascendancy"] == "Titan" and ref["items"]
        assert c.get("/api/versus?ref=@build").json()["rows"]
        skills = c.get("/api/versus/skills").json()  # the build's gems next to the character's
        assert skills["ref"] and skills["mine"] and skills["refSkill"]
        tree = c.get("/api/versus/tree").json()  # a Titan's passives against a Monk's: little in common
        assert tree["missing"] and tree["extra"] and tree["refPoints"]["used"] > 0
        assert not {n["id"] for n in tree["missing"]} & {n["id"] for n in tree["extra"]}
        # each node with its lines from its own tree (the Titan's ascendancy too); a socket with the jewel in it
        assert all(n["stats"] for n in tree["missing"] if n["type"] in ("Notable", "Keystone"))
        assert any(n["ascendancy"] == "Titan" and n["stats"] for n in tree["missing"])
        assert any(n["jewel"] and n["jewel"]["lines"] for n in tree["missing"] if n["type"] == "Socket")
        # the plan's edits saved go into the character; the guide's file does not change
        node = c.get("/api/tree?mode=balanced&points=6").json()["growth"][0]
        c.post("/api/tree/add", json={"id": node["id"], "name": node["name"]}, headers=H)
        guide_file = (tmp_path / "Гайд.txt").read_text(encoding="utf-8")
        c.post("/api/builds/commit", headers=H)
        assert (tmp_path / "Гайд.txt").read_text(encoding="utf-8") == guide_file
        assert library.main_path("Гайд").read_text(encoding="utf-8").strip() != mine
        # taken off: the build is a build of its own again
        b = c.delete("/api/character", headers=H).json()
        assert b["main"] is None and b["info"]["ascendancy"] == "Titan"
        c.post("/api/character", json={"code": mine}, headers=H)
        c.delete("/api/builds/Гайд", headers=H)
        assert not library.main_path("Гайд").exists() and any((tmp_path / ".trash").glob("*Гайд.main.txt"))
    server.session.engine = None
