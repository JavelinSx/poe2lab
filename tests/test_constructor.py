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


def test_a_stage_keeps_its_links():
    doc = author.set_block(None, "lv:act2:links", {"links": [["gem:Maul", "support:Rage I", "support:Rage I"], []]})
    assert doc["blocks"]["lv:act2:links"] == {"links": [["gem:Maul", "support:Rage I"]]}
    import pytest
    with pytest.raises(author.AuthorError):
        author.set_block(None, "lv:act2:links", {"links": [["unique:Astramentis"]]})


def test_the_levelling_stages_and_a_stage_worked_out():
    from poe2lab.engine import PobEngine
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text(encoding="utf-8").strip())
    info = constructor.leveling_info(e)
    act2 = next(s for s in info["stages"] if s["key"] == "act2")
    # the campaign's fixed rewards by the act's end: Beira's cold, the Sisters' lightning
    assert act2["level"] == 32 and act2["points"] == 31 and act2["questRes"] == {"cold": 10, "lightning": 10}
    assert info["gemLevels"]["Rage I"] == 1
    notables = [n for n in e.allocated_nodes() if n["type"] == "Notable" and not n["ascendancy"]][:2]
    r = constructor.check_stage(e, 32, [["gem:Maul", "support:Rage I"]], ["unique:Amor Mandragora"],
                                [f"passive:{n['id']}|{n['name']}" for n in notables])
    # the gems at what a level 32 character can use; the skill works with the talisman
    assert r["links"][0]["gems"][0]["level"] < 20 and r["links"][0]["dps"] > 0
    assert r["points"]["budget"] == 31 and r["points"]["used"] >= len(notables)
    # with a quarterstaff the bear's skill does nothing
    assert constructor.check_stage(e, 32, [["gem:Maul"]], ["base:Long Quarterstaff"], [])["links"][0]["dps"] == 0


def test_the_builds_start_level_and_a_try_at_it():
    import pytest
    doc = author.set_block(None, "start:build", {"level": 45, "list": ["unique:Constricting Command"]})
    assert doc["blocks"]["start:build"] == {"level": 45, "list": ["unique:Constricting Command"]}
    for bad in (0, 101, "45", True):
        with pytest.raises(author.AuthorError):
            author.set_block(None, "start:build", {"level": bad})
    from poe2lab.analysis import leveling
    from poe2lab.engine import PobEngine
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text(encoding="utf-8").strip())
    r = leveling.try_level(e, 45, None, False)
    assert r["level"] == 45 and r["ok"] and 0 < r["dps"] < 100
