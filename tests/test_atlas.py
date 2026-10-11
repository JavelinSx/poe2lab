"""The Atlas tree guide (poe2lab.atlas): the passive graph format, the nodes' texts, the route to the key nodes and the
page's endpoint - on small made-up data, no game install needed."""
import struct

import pytest
from fastapi.testclient import TestClient

from poe2lab import atlas, gamedata


def graph_bytes(roots, groups):
    out = struct.pack("<H", 259) + bytes(11) + struct.pack("<i", len(roots)) + b"".join(struct.pack("<q", r) for r in roots)
    out += struct.pack("<i", len(groups))
    for x, y, passives in groups:
        out += struct.pack("<ff", x, y) + bytes(9) + struct.pack("<i", len(passives))
        for pid, orbit, index, links in passives:
            out += struct.pack("<iiii", pid, orbit, index, len(links)) + b"".join(struct.pack("<ii", l, 0) for l in links)
    return out


def test_graph_is_read_whole():
    data = graph_bytes([1], [(10.0, -5.0, [(1, 0, 0, [2]), (2, 1, 3, [])]), (100.0, 0.0, [(3, 2, 6, [2])])])
    g = atlas.parse_graph(data)
    assert g["roots"] == [1]
    assert [p["id"] for gr in g["groups"] for p in gr["passives"]] == [1, 2, 3]
    assert g["groups"][0]["passives"][0]["links"] == [2] and g["groups"][1]["passives"][0]["links"] == [2]
    assert g["groups"][0]["x"] == 10.0 and g["groups"][0]["passives"][1]["orbit"] == 1
    with pytest.raises(gamedata.GameDataError):
        atlas.parse_graph(data + b"\0")  # a format it does not know is not read half-way


CSD = """description
	1 map_item_drop_rarity_+%
	2
		1|# "{0}% increased Rarity of Items found"
		#|-1 "{0}% reduced Rarity of Items found" negate 1
	lang "Russian"
	1
		# "{0}% увеличение редкости находимых предметов"
description
	1 map_boots_can_be_exceptional
	1
		# "Boots may be found as [ExceptionalItem|Exceptional Items]"
description
	2 map_a map_b
	1
		# # "{0:+d} to A and {1} seconds" milliseconds_to_seconds 2
"""


def test_node_texts_in_both_languages():
    descs = gamedata.parse_csd(CSD, "ru")
    assert atlas.describe([("map_item_drop_rarity_+%", 2)], descs, "en") == ["2% increased Rarity of Items found"]
    assert atlas.describe([("map_item_drop_rarity_+%", -3)], descs, "en") == ["3% reduced Rarity of Items found"]
    assert atlas.describe([("map_item_drop_rarity_+%", 2)], descs, "want") == ["2% увеличение редкости находимых предметов"]
    # no Russian block: the English text, the game's markup taken out
    assert atlas.describe([("map_boots_can_be_exceptional", 1)], descs, "want") == ["Boots may be found as Exceptional Items"]
    # two stats in one line, a handler on the second, and a sign
    assert atlas.describe([("map_a", 5), ("map_b", 2500)], descs, "en") == ["+5 to A and 2.5 seconds"]
    assert atlas.describe([("unknown_stat", 1)], descs, "en") == []


def node(i, stats=(), part="Main", root=False, req="", kind="small"):
    return {"id": i, "stats": list(stats), "part": part, "root": root, "req": req, "kind": kind}


def test_route_takes_the_closest_key_node_first_and_one_of_a_kind():
    # 1 (root) - 2 - 3 (fracturing) ; 1 - 4 - 5 - 6 (exceptional boots) ; 2 - 7 (rare tablets), 3 - 8 (rare tablets too)
    tree = {"nodes": [node(1, root=True), node(2), node(3, ["map_cleansed_monster_can_drop_fracturing_orb"]), node(4), node(5),
                      node(6, ["map_boots_can_be_exceptional"]), node(7, ["dummy_display_tablets_can_be_rare_and_have_+1_mod"]),
                      node(8, ["dummy_display_tablets_can_be_rare_and_have_+1_mod"]), node(9, ["map_item_drop_rarity_+%"]),
                      node(10, ["map_cleansed_monster_can_drop_fracturing_orb"], part="Breach")],
            "links": [[1, 2], [2, 3], [1, 4], [4, 5], [5, 6], [2, 7], [3, 8], [1, 9]]}
    r = atlas.route(tree)
    assert r["root"] == 1
    assert [s["node"] for s in r["steps"]] == [3, 7, 6]  # closest first; tablets once (7, so 8 is no longer wanted)
    assert [s["points"] for s in r["steps"]] == [2, 3, 6]  # the path's nodes counted once
    assert r["steps"][2]["path"] == [4, 5, 6]
    groups = {g["id"]: g for g in r["groups"]}
    assert groups["fracturing"]["nodes"] == [3]  # only the main tree's nodes
    assert groups["tablets"]["any"] and not groups["exceptional"]["any"]
    assert {g["id"]: g["nodes"] for g in r["useful"]} == {"rarity": [9]}


def test_endpoint(monkeypatch):
    from poe2lab.web import server
    monkeypatch.setattr(server.gamedata, "game_dir", lambda: None)
    with TestClient(server.app) as c:
        res = c.get("/api/atlas")
        assert res.status_code == 400 and "Path of Exile 2" in res.json()["detail"]
    monkeypatch.setattr(server.gamedata, "game_dir", lambda: "game")
    monkeypatch.setattr(server.atlas, "guide", lambda game: {"tree": {"nodes": []}, "route": {"steps": []}, "game": game})
    with TestClient(server.app) as c:
        assert c.get("/api/atlas").json()["game"] == "game"
