"""An item copied from the Russian client (Ctrl+Alt+C) becomes English text PoB can read."""
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


def test_a_plain_copy_asks_for_the_advanced_one(db):
    plain = "\n".join(l for l in STAFF.split("\n") if not l.startswith("{"))
    with pytest.raises(itemtext.TranslationError, match="Ctrl\+Alt\+C"):
        itemtext.to_english(plain, db, journal.Names(db))


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
