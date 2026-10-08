"""The author's constructor: the character laid out by section, each element with the id its notes are kept under,
and a note's two kinds (shown at once under the author's label, shown over the element)."""
from conftest import FIXTURES

from poe2lab import author, constructor


def test_a_note_has_a_tip_and_a_label():
    doc = author.set_block(None, "gem:Maul", {"text": "Главный скилл", "tip": "Бей по боссу", "label": "  Важно  "})
    assert doc["blocks"]["gem:Maul"] == {"text": "Главный скилл", "tip": "Бей по боссу", "label": "Важно"}


def test_the_character_laid_out():
    from poe2lab.engine import PobEngine
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text(encoding="utf-8").strip())
    d = constructor.layout(e)
    assert d["character"]["ascendancy"] == "Titan"
    main = next(g for g in d["skills"] if g["main"])
    assert main["id"] == "sk:" + "+".join(main["actives"]) and all(x["id"] == f"gem:{x['name']}" for x in main["gems"])
    assert [g["slot"] for g in d["gear"]][:2] == ["Weapon 1", "Weapon 1 Swap"]
    assert all(f["slot"].startswith(("Flask", "Charm")) for f in d["flasks"]) and d["flasks"]
    assert d["tree"]["keystones"] and all(n["id"] == f"node:{n['node']}" for n in d["tree"]["notables"])
    assert {j["effect"]["kind"] for j in d["jewels"] if j["effect"]} >= {"fromNothing", "radiusMods"}
    assert d["quests"] and all(q["id"].startswith("qst:") for q in d["quests"])


def test_the_min_stage_has_its_own_gear_and_shares_the_gems():
    from poe2lab.engine import PobEngine
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text(encoding="utf-8").strip())
    d = constructor.layout(e, stage="min")
    assert d["stage"] == "min"
    assert all(g["id"].endswith("@min") for g in d["gear"] + d["flasks"] + d["jewels"])
    assert all(not x["id"].endswith("@min") for g in d["skills"] for x in g["gems"])
    assert all(not n["id"].endswith("@min") for n in d["tree"]["notables"])
