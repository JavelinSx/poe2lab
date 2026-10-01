"""The mechanics of gems and uniques as Jev read them (data/mechanics_labels.json, scripts/label_mechanics.py) and how
the analysis uses them: labels for what the texts say, the game's rules by damage type on top."""
import json

import pytest

from poe2lab.analysis import skills
from poe2lab.analysis.skills import LABELS_FILE, MECHANICS, mechanics_of
from poe2lab.profile import open_build

pytestmark = pytest.mark.skipif(not LABELS_FILE.exists(), reason="no labels file")


@pytest.fixture(scope="module")
def catalog():
    engine, _ = open_build("titan")
    return {g["name"]: g for g in engine.gem_texts()}, {u["name"] for u in engine.unique_catalog()}


def test_every_gem_and_unique_is_labelled(catalog):
    gems, uniques = catalog
    data = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    items = data["items"]
    # after a PoB update a new gem falls back to the regex: relabel (scripts/label_mechanics.py --all)
    assert {f"gem:{n}" for n in gems} <= set(items), "gems without labels: relabel"
    assert {f"unique:{n}" for n in uniques} <= set(items), "uniques without labels: relabel"
    keys = {m.key for m in MECHANICS}
    for k, lab in items.items():
        if not k.startswith(("gem:", "unique:")):  # tree nodes and what PoB does not count have their own tests
            continue
        # each label keeps the fingerprint of the text it answered: a run after a patch asks only about changes
        assert set(lab) == {"creates", "uses", "text"} and set(lab["creates"]) | set(lab["uses"]) <= keys
    assert data["meta"]["model"].startswith("jev")


def test_tree_notables_are_labelled():
    """The current tree's notables (a build on an older tree keeps the keywords for nodes the tree no longer has)."""
    from poe2lab.analysis.tree import PACKAGE_MECHANICS, node_mechanics
    from poe2lab.engine import PobEngine
    engine = PobEngine()
    names = {n["name"] for n in engine.tree_graph()["nodes"] if n["type"] in ("Notable", "Keystone") and not n["asc"]}
    items = json.loads(LABELS_FILE.read_text(encoding="utf-8"))["items"]
    assert {f"node:{n}" for n in names} <= set(items), "notables without labels: relabel with --tree"
    keys = {k for k, _ in PACKAGE_MECHANICS}
    assert all(set(items[f"node:{n}"]["has"]) <= keys for n in names)
    skills._labels = None
    nodes = {n["name"]: n for n in engine.tree_graph()["nodes"]}
    # your own Stun Threshold is not stunning enemies; less Poison on you is not poisoning
    assert "stun" not in node_mechanics(nodes["Self Mortification"])
    assert "poison" not in node_mechanics(nodes["The Ancient Serpent"])
    assert "crit" in node_mechanics(nodes["Critical Exploit"])


def gem(catalog, name):
    g = catalog[0][name]
    return {"name": name, "support": g["support"], "description": g["description"], "stats": g["stats"],
            "types": g["types"], "tags": g["tags"]}


def test_what_the_regex_got_wrong(catalog):
    skills._labels = None  # read the file afresh
    # Freezing Mark activates on Frozen enemies; Frost Bomb leaves a Cold Infusion; Infernal Cry spends Endurance
    assert "freeze" in mechanics_of(gem(catalog, "Freezing Mark"))["uses"]
    assert "infusion" in mechanics_of(gem(catalog, "Frost Bomb"))["creates"]
    assert "endurance" in mechanics_of(gem(catalog, "Infernal Cry"))["uses"]
    # a shockwave is not Shapeshifting
    assert "shapeshift" not in mechanics_of(gem(catalog, "Shockwave Totem"))["uses"]
    # Glacial Cascade consumes Freeze and never freezes itself (the stat id keeps the cold rule off)
    gc = mechanics_of(gem(catalog, "Glacial Cascade"))
    assert "freeze" in gc["uses"] and "freeze" not in gc["creates"]
    # the game's rule by damage type is kept: a cold attack builds Freeze whatever its text says
    assert "freeze" in mechanics_of(gem(catalog, "Ice Strike"))["creates"]


def test_what_pob_does_not_count_is_sorted_by_what_it_changes():
    """Stats PoB has no calculation for and unique lines it cannot read: Jev's reading of what each changes."""
    from poe2lab.knowledge import _impact, gap_key
    engine, _ = open_build("titan")
    items = json.loads(LABELS_FILE.read_text(encoding="utf-8"))["items"]
    stats = {s["stat"] for s in engine.unmapped_stats()}
    assert {f"stat:{s}" for s in stats} <= set(items), "unmapped stats without labels: relabel with --gaps"
    for k, lab in items.items():
        if k.startswith(("stat:", "line:")):
            assert set(lab["impact"]) <= {"damage", "defence", "resource", "none"}
    # a rolled item and the unique's own line meet on one key
    assert gap_key("(20-40)% increased Damage") == gap_key("32% increased Damage") == "#% increased Damage"
    skills._labels = None
    # a stat for where the character faces changes nothing; one key without a label keeps the keyword guess
    assert _impact("stat:action_do_not_face_target", True) is False
    assert _impact("stat:no_such_stat", True) is True
