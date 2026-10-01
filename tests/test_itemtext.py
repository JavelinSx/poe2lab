"""An item copied from the Russian client - the advanced copy (Ctrl+Alt+C) or the plain one (Ctrl+C, "copy" at the
trade market) - becomes English text PoB can read."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poe2lab import gamedata, itemtext, journal
from poe2lab.data.moddb import ModDB
from poe2lab.engine import PobEngine
from poe2lab.web.server import app, session

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STAFF = (FIXTURES / "ru_quarterstaff.txt").read_text(encoding="utf-8")
H = {"X-Poe2lab": "1"}

pytestmark = pytest.mark.skipif(not (gamedata.RAW / "data/balance/mods.datc64").is_file(),
                                reason="needs the game's mod table")


@pytest.fixture(scope="module")
def db():
    e = PobEngine()
    e.load_code((FIXTURES / "titan.txt").read_text().strip())
    return ModDB.from_engine(e)


def test_a_russian_rare_reads_in_english_with_its_rolls(db):
    en = itemtext.to_english(STAFF, db, journal.Names(db))
    assert "Crescent Quarterstaff" in en and "Quality: 9" in en and "Item Level: 21" in en
    assert "46% increased Elemental Damage with Attacks" in en and "Adds 2 to 5 Physical Damage" in en
    assert "+30 to Accuracy Rating" in en and "10% increased Light Radius" in en
    assert itemtext.is_russian(STAFF) and not itemtext.is_russian(en)


def test_fill_takes_rolls_in_order_and_the_middle_when_missing():
    assert itemtext.fill("Adds (2-3) to (5-7) Physical Damage", ["2", "5"]) == "Adds 2 to 5 Physical Damage"
    assert itemtext.fill("+(21-40) to Accuracy Rating", []) == "+30 to Accuracy Rating"


def test_compare_takes_a_russian_item():
    with TestClient(app) as c:
        c.post("/api/load", json={"name": "titan"}, headers=H)
        r = c.post("/api/compare", json={"slot": "Weapon 1", "text": STAFF}, headers=H)
        assert r.status_code == 200 and "dps_pct" in r.json()  # PoB read it (it failed on Russian text before)
        broken = STAFF.replace("Боевой посох с полумесяцем", "Неведомая штука")
        r = c.post("/api/compare", json={"slot": "Weapon 1", "text": broken}, headers=H)
        assert r.status_code == 400 and "не смог прочитать предмет" in r.json()["detail"]
    session.engine = None


def test_a_plain_copy_from_the_market_reads_line_by_line(db):
    """Ctrl+C or "copy" at the trade market names no affix: each line goes by the stat templates, its numbers and
    the marks PoB reads kept; what PoB computes itself and the trade note left out."""
    text = (FIXTURES / "ru_market_quarterstaff.txt").read_text(encoding="utf-8")
    en = itemtext.to_english(text, db, journal.Names(db))
    lines = en.splitlines()
    assert lines[:3] == ["Rarity: Rare", "poe2lab item", "Guardian Quarterstaff"]
    assert "Quality: +20%" in lines and "Sockets: S S" in lines and "Item Level: 78" in lines
    assert "Bonded: 40% increased effect of Fully Broken Armour (rune)" in lines
    assert "+18% to Block chance (implicit)" in lines and "+137 to Accuracy Rating (desecrated)" in lines
    assert "Adds 94 to 161 Cold Damage" in lines and "+3 to Level of all Melee Skills" in lines
    assert not any(x in en for x in ("divine", "Requires", "Physical Damage: ", "Attacks per Second"))
    # the item's own mark "fractured item" is not a mod: left out (its fractured mod is marked on its line)
    fractured = text.replace("+3 к уровню всех камней умений ближнего боя", "+3 к уровню всех камней умений ближнего боя (fractured)")
    en_f = itemtext.to_english(fractured + "\n--------\nРасколотый предмет", db, journal.Names(db))
    assert "+3 to Level of all Melee Skills (fractured)" in en_f.splitlines()
    # a line no template knows is named, not dropped quietly
    with pytest.raises(itemtext.TranslationError, match="не перевёл"):
        itemtext.to_english(text.replace("+137 к меткости", "+137 к чему-то несуществующему"), db, journal.Names(db))


def test_a_weapon_tried_on_shows_each_skills_damage():
    """A weapon in the item window: the build's skills' damage now and with it (a skill the weapon cannot use: 0)."""
    text = (FIXTURES / "ru_market_quarterstaff.txt").read_text(encoding="utf-8")
    with TestClient(app) as c:
        c.post("/api/load", json={"name": "titan"}, headers=H)
        r = c.post("/api/gear/try", json={"slot": "Weapon 1", "text": text}, headers=H)
        assert r.status_code == 200
        skills = r.json()["skills"]
        assert skills and all(s["now"] >= 1 and s["with"] >= 0 for s in skills)
        assert len({s["name"] for s in skills}) == len(skills)
        # not a weapon: no skills list
        r = c.post("/api/gear/try", json={"slot": "Helmet", "text": c.get("/api/item/Helmet", headers=H).json()["text"]},
                   headers=H)
        assert r.status_code == 200 and "skills" not in r.json()
    session.engine = None
