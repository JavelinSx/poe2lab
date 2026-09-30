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
    for lab in items.values():
        assert set(lab) == {"creates", "uses"} and set(lab["creates"]) | set(lab["uses"]) <= keys
    assert data["meta"]["model"].startswith("jev")


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
