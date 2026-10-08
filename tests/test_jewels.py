"""What a jewel does on the tree beyond its lines (poe2lab.analysis.jewels) and the jewel taken out for real
(PobEngine.without_jewel): a timeless jewel's swapped keystone and From Nothing's nodes go with it, and the tree comes
back exactly."""
from conftest import FIXTURES

from poe2lab.analysis import jewels


def node(id_, type_, name, now=None, lines=(), conquered=False, attribute=False):
    return {"id": id_, "type": type_, "name": name, "now": now or name, "lines": list(lines),
            "conquered": conquered, "attribute": attribute}


def test_a_timeless_jewel_swaps_keystones_and_hides_its_notables():
    item = {"explicit": [{"line": "Remembrancing 3876 songworthy deeds by the line of Vorana"},
                         {"line": "Passives in radius are Conquered by the Kalguur"}]}
    effect = {"radius": "Very Large", "conqueror": {"kind": "kalguur", "seed": 3876}, "nodes": [
        node(1, "Keystone", "Elemental Equilibrium", "Black Scythe Training", ["1% increased Energy Shield per 2 Strength"], True),
        node(2, "Notable", "Turn the Clock Forward", conquered=True),
        node(3, "Normal", "Attribute", "Strength", conquered=True, attribute=True)]}
    d = jewels.describe(item, effect)
    assert d["kind"] == "timeless" and d["conqueror"] == {"kind": "kalguur", "seed": 3876, "name": "Vorana"}
    # what PoB swaps is named with its new lines; the notables it cannot tell are named as unknown
    assert d["replaced"] == [{"name": "Elemental Equilibrium", "now": "Black Scythe Training", "type": "Keystone",
                              "lines": ["1% increased Energy Shield per 2 Strength"]}]
    assert d["unknown"] == ["Turn the Clock Forward"] and d["small"] == 1


def test_a_radius_jewel_sums_what_it_gives():
    item = {"explicit": [{"line": "Small Passive Skills in Radius also grant 1% increased Charm Effect Duration"},
                         {"line": "Notable Passive Skills in Radius also grant 3% increased Cooldown Recovery Rate"},
                         {"line": "18% increased Effect of Notable Passive Skills in Radius"}]}
    effect = {"radius": "Large", "radiusMods": True, "nodes": [
        node(1, "Normal", "Spell Damage"), node(2, "Normal", "Spell Damage"),
        node(3, "Normal", "Attribute", "Dexterity", attribute=True),  # PoB's rule: an attribute is not a small one
        node(4, "Notable", "Abasement"), node(5, "Notable", "Shimmering Mirage"), node(6, "Notable", "Turn the Clock Forward")]}
    d = jewels.describe(item, effect)
    assert [(g["kind"], g["count"], g["total"]) for g in d["grants"]] == [
        ("small", 2, "2% increased Charm Effect Duration"), ("notable", 3, "9% increased Cooldown Recovery Rate"),
        ("notable", 3, None)]


def test_a_basic_jewel_needs_no_words():
    assert jewels.describe({"explicit": [{"line": "15% increased Spell Damage"}]},
                           {"radius": False, "nodes": []}) is None


def test_jewels_on_a_build_and_taken_out():
    from poe2lab.engine import PobEngine
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text(encoding="utf-8").strip())
    effects = e.jewel_effects()
    items = {s["slot"]: s for s in e.jewel_sockets() if s["item"]}
    nothing = items["Jewel 54127"]
    d = jewels.describe(nothing["item"], effects[nothing["node"]])
    assert d["kind"] == "fromNothing" and d["keystone"] == "Resolute Technique"
    assert {"name": "Unbending", "type": "notable"} in d["reached"]
    lost = items["Jewel 2491"]
    d = jewels.describe(lost["item"], effects[lost["node"]])
    assert d["kind"] == "radiusMods" and all(g["count"] > 0 for g in d["grants"])

    tree = sorted(n["id"] for n in e.allocated_nodes())
    before = e.what_if()
    with e.without_jewel("Jewel 54127"):
        # the nodes taken through From Nothing go with it, and what they gave
        assert len(e.allocated_nodes()) < len(tree)
        assert e.what_if()["Life"] < before["Life"]
    assert sorted(n["id"] for n in e.allocated_nodes()) == tree
    assert e.what_if()["Life"] == before["Life"] and e.what_if()["CombinedDPS"] == before["CombinedDPS"]
