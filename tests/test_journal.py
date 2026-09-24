"""Craft journal: item texts copied in game (Ctrl+Alt+C, Russian or English client) become draws of the hidden mod
weights; the weights are estimated from them and can be applied to crafting."""
import random
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poe2lab import crafting, gamedata, journal
from poe2lab.data.moddb import ModDB
from poe2lab.engine import PobEngine
from poe2lab.web.server import app, session

TITAN = (Path(__file__).resolve().parent / "fixtures" / "titan.txt").read_text().strip()
H = {"X-Poe2lab": "1"}
BASE = "Riveted Mitts"

pytestmark = pytest.mark.skipif(not (gamedata.RAW / "data/balance/mods.datc64").is_file(),
                                reason="needs the game's mod table (python -m poe2lab game-texts)")


@pytest.fixture(scope="module")
def db():
    e = PobEngine()
    e.load_code(TITAN)
    return ModDB.from_engine(e)


@pytest.fixture(scope="module")
def names(db):
    return journal.Names(db)


def ru_affix(mod_id):
    """The Russian affix name (masculine form) of a mod, as the Russian client prints it."""
    balance = gamedata.RAW / "data/balance"
    ids = [r["Id"] for r in gamedata.read_table(balance / "mods.datc64", ["Id"])]
    ru = list(gamedata.read_table(balance / "russian/mods.datc64", ["Name"]))
    return journal._variants(ru[ids.index(mod_id)]["Name"])[0]


def mod(db, mod_id):
    return next(m for m in db.mods if m.id == mod_id)


def ru_item(db, rarity, mods, name="", item_level=45, base_ru="Клёпаные рукавицы"):
    """A Russian Ctrl+Alt+C text: rarity, name lines, item level, then each mod's header and line."""
    rarity_ru = {"normal": "Обычный", "magic": "Волшебный", "rare": "Редкий"}[rarity]
    head = [base_ru] if rarity != "rare" else [name or "Гибельная хватка", base_ru]
    body = []
    tags = db.bases[BASE]["tags"]
    for mod_id in mods:
        m = mod(db, mod_id)
        side = "Префикс" if m.type == "Prefix" else "Суффикс"
        body += [f'{{ {side} "{ru_affix(mod_id)}" (Уровень: {journal._tier_of(db, m, tags)}) — Тег }}',
                 re.sub(r"\((\d+)-\d+\)", r"\1", m.lines[0])]
    return "\n".join(["Класс предмета: Перчатки", f"Редкость: {rarity_ru}", *head, "--------", "Броня: 30",
                      "--------", f"Уровень предмета: {item_level}", "--------", *body])


def test_reads_a_russian_advanced_copy(db, names):
    p = journal.parse(ru_item(db, "magic", ["IncreasedLife2", "Strength1"]), db, names)
    assert not p.problems and p.rarity == "magic" and p.base == BASE and p.item_level == 45
    assert [(m.mod.id, m.side) for m in p.mods] == [("IncreasedLife2", "Prefix"), ("Strength1", "Suffix")]


def test_reads_an_english_copy_and_asks_for_the_advanced_one(db, names):
    text = ("Item Class: Gloves\nRarity: Magic\nHealthy Riveted Mitts\n--------\nItem Level: 45\n--------\n"
            '{ Prefix Modifier "Healthy" (Tier: 12) — Life }\n+22(20-29) to maximum Life')
    p = journal.parse(text, db, names)
    assert not p.problems and [m.mod.id for m in p.mods] == ["IncreasedLife2"]
    plain = journal.parse("Item Class: Gloves\nRarity: Magic\nHealthy Riveted Mitts\n--------\nItem Level: 45\n"
                          "--------\n+22 to maximum Life", db, names)
    assert any("Ctrl+Alt+C" in x for x in plain.problems)
    assert journal.is_item_text(text) and not journal.is_item_text("hello")


def test_a_crafting_session_becomes_draws(db, names):
    life, stre, dex = "IncreasedLife2", "Strength1", "Dexterity1"
    life2 = next(m.id for m in db.mods if m.group == "IncreasedLife" and m.id != life
                 and m.weight_for(set(db.bases[BASE]["tags"])) > 0)
    armour = next(m.id for m in db.mods if m.type == "Prefix" and m.group != "IncreasedLife"
                  and m.weight_for(set(db.bases[BASE]["tags"])) > 0 and m.level <= 45)
    texts = [ru_item(db, "normal", []),
             ru_item(db, "magic", [life]),  # transmutation
             ru_item(db, "magic", [life]),  # the same copy again
             ru_item(db, "magic", [life, stre]),  # augmentation
             ru_item(db, "rare", [life, stre, dex]),  # regal
             ru_item(db, "rare", [life, stre, dex, armour]),  # exalt
             ru_item(db, "rare", [life, stre, armour, next(m.id for m in db.mods if m.group == "Intelligence")]),
             ru_item(db, "magic", [life2], base_ru="Закалённые рукавицы")]  # another base: a fresh item
    records = [{"id": str(i), "t": i, "text": t} for i, t in enumerate(texts)]
    rows, samples = journal.interpret(records, db, names)
    hows = [r["how"] for r in rows]
    # another base is another item: a fresh magic item, not a step of the one before
    assert hows == ["white", "fresh_magic", "repeat", "augment", "regal", "exalt", "chaos", "fresh_magic"]
    assert [r["draws"] for r in rows] == [0, 1, 0, 1, 1, 1, 1, 1]
    chaos = samples[-2]
    assert chaos.rarity == "rare" and len(chaos.given) == 3 and len(chaos.added) == 1


def test_a_batch_of_the_same_base(db, names):
    """Players transmute a stack of bases, then augment them all: each copy continues its own item, and two items
    that rolled the same mod (other values) are two items, not a repeat."""
    a1 = ru_item(db, "magic", ["IncreasedLife2"])
    b1 = ru_item(db, "magic", ["IncreasedLife2"]).replace("+20 to maximum", "+21 to maximum")
    a2 = ru_item(db, "magic", ["IncreasedLife2", "Strength1"])
    b2 = ru_item(db, "magic", ["IncreasedLife2", "Dexterity1"]).replace("+20 to maximum", "+21 to maximum")
    records = [{"id": str(i), "t": i, "text": t} for i, t in enumerate([a1, b1, a2, b2, a2])]
    rows, samples = journal.interpret(records, db, names)
    assert [r["how"] for r in rows] == ["fresh_magic", "fresh_magic", "augment", "augment", "repeat"]
    assert sum(len(x.added) for x in samples) == 4


def test_f2_is_one_advanced_copy_in_the_game_only():
    keys = [(i.ki.wScan, i.ki.dwFlags) for i in journal.copy_inputs()]
    # Ctrl, Alt, C pressed by scan code, then released in reverse order: exactly one Ctrl+Alt+C
    assert keys == [(0x1D, 8), (0x38, 8), (0x2E, 8), (0x2E, 10), (0x38, 10), (0x1D, 10)]
    assert journal.is_game_title("Path of Exile 2") and not journal.is_game_title("poe2lab — Chrome")


def test_estimate_moves_towards_what_rolls(db):
    """Transmutations where life always shows up: life's weight rises, the others fall."""
    tags = tuple(db.bases[BASE]["tags"])
    life = [m for m in db.rollable(tags, 45) if m.group == "IncreasedLife"]
    rng = random.Random(1)
    samples = [journal.Sample(tags, 45, "magic", [], [rng.choice(life)], "Gloves") for _ in range(40)]
    result = journal.estimate(db, samples)
    by_group = {f["group"]: f for f in result["families"]}
    assert by_group["IncreasedLife"]["factor"] > 3 and by_group["IncreasedLife"]["seen"] == 40
    others = [f for f in result["families"] if f["group"] != "IncreasedLife"]
    assert all(f["factor"] < 1 for f in others)
    assert result["classes"]["Gloves"] == {"records": 40, "draws": 40}
    assert result["weights"] and all(w > 0 for w in result["weights"].values())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(crafting, "WEIGHTS_FILE", tmp_path / "poe2lab" / "craft_weights.json")
    with TestClient(app) as c:
        yield c
    session.engine = None


def test_journal_endpoints(client, db):
    session.engine = None  # the journal needs no build open: it brings its own mod data
    assert client.get("/api/journal").json()["total"] == 0
    assert client.post("/api/journal/add", json={"text": "not an item"}, headers=H).status_code == 400
    for mods in (["IncreasedLife2"], ["IncreasedLife2", "Strength1"]):
        assert client.post("/api/journal/add", json={"text": ru_item(db, "magic", mods)}, headers=H).status_code == 200
    j = client.get("/api/journal").json()
    assert j["total"] == 2 and j["draws"] == 2 and j["classes"]["Gloves"]["draws"] == 2
    assert j["entries"][0]["how"] == "augment" and j["entries"][0]["base"] == BASE
    est = client.post("/api/journal/estimate", headers=H).json()
    assert est["draws"] == 2 and "weights" not in est
    assert client.post("/api/journal/apply", headers=H).json()["applied"] and crafting.WEIGHTS_FILE.is_file()
    assert client.get("/api/journal").json()["applied"]
    assert not client.delete("/api/journal/apply", headers=H).json()["applied"]
    assert client.delete(f"/api/journal/entry/{j['entries'][0]['id']}", headers=H).status_code == 200
    assert client.get("/api/journal").json()["total"] == 1
    assert client.get("/api/journal/export").status_code == 200
