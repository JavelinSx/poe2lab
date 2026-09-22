"""Price book logic without network access."""
from poe2lab.economy.ninja import PriceBook, slug

OVERVIEW = {
    "core": {"rates": {"exalted": 500.0, "chaos": 8.0}},
    "lines": [
        {"id": "soul-core-of-tacati", "primaryValue": 0.08, "volumePrimaryValue": 12.0},
        {"id": "perfect-iron-rune", "primaryValue": 1.5, "volumePrimaryValue": 0.4},
        {"id": "greater-essence-of-battle", "primaryValue": 0.0005, "volumePrimaryValue": 0.01},
    ],
}


def test_slug_matches_poe_ninja_ids():
    assert slug("Saqawal's Rune of the Sky") == "saqawals-rune-of-the-sky"
    assert slug("Atziri's Soul Core of Vitality") == "atziris-soul-core-of-vitality"
    assert slug("Greater Essence of Ruin") == "greater-essence-of-ruin"


def test_price_lookup_and_formatting():
    book = PriceBook.from_overviews("Test", {"SoulCores": OVERVIEW})
    tacati = book.get("Soul Core of Tacati")
    assert book.describe(tacati) == "40 ex"
    iron = book.get("Perfect Iron Rune")
    assert iron.thin and book.describe(iron) == "1.50 div (мало сделок)"
    assert book.describe(book.get("Greater Essence of Battle")).startswith("<1 ex")
    assert book.get("No Such Rune") is None


def test_value_per_divine_ignores_free_items():
    book = PriceBook.from_overviews("Test", {"SoulCores": OVERVIEW})
    assert book.per_divine(8.0, book.get("Soul Core of Tacati")) == 100
    assert book.per_divine(8.0, book.get("Greater Essence of Battle")) is None
