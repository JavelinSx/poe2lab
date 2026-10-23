"""The farming strategies (poe2lab.farmguide): every text in both languages, every button points at something the
interface has - a waystone or tablet search preset (atlas.js), an atlas branch or master."""
import re
from pathlib import Path

from poe2lab import farmguide

JS = (Path(__file__).resolve().parents[1] / "poe2lab" / "web" / "static" / "atlas.js").read_text(encoding="utf-8")


def _presets(name: str) -> set[str]:
    block = JS[JS.index(f"const {name} = ["):]
    block = block[:block.index("]];") + 3]
    return set(re.findall(r'^\s*\["(\w+)"', block, re.M))


def test_texts_in_both_languages():
    for s in farmguide.STRATEGIES:
        for key in ("name", "goal", "why", "where", "steps", "tips", "profit"):
            assert set(s[key]) == {"ru", "en"}, (s["id"], key)
        assert len(s["steps"]["ru"]) == len(s["steps"]["en"]) and len(s["tips"]["ru"]) == len(s["tips"]["en"]), s["id"]
        for x in s["setup"]:
            assert set(x["text"]) == {"ru", "en"}, s["id"]


def test_links_point_at_presets():
    maps, tablets = _presets("EG_PRESETS"), _presets("EG_TPRESETS")
    for s in farmguide.STRATEGIES:
        for x in s["setup"]:
            link = x.get("link") or {}
            if "maps" in link:
                assert link["maps"] in maps, (s["id"], link)
            if "tablets" in link:
                assert link["tablets"] in tablets, (s["id"], link)
            if "master" in link:
                assert link["master"] in ("Hilda", "Doryani", "Jado"), (s["id"], link)


def test_strategies_in_a_language():
    ru, en = farmguide.strategies("ru"), farmguide.strategies("en")
    assert [s["id"] for s in ru] == [s["id"] for s in en]
    assert ru[0]["name"] != en[0]["name"] and isinstance(ru[0]["steps"], list)


def test_every_strategy_has_an_income():
    assert set(farmguide.INCOME) == {s["id"] for s in farmguide.STRATEGIES}
    for spec in farmguide.INCOME.values():
        s = spec.get("session") or {}
        for text, _ in s.get("other", []) + s.get("costs_other", []):
            assert set(text) == {"ru", "en"}
        assert set(s.get("costs_unknown", {"ru": 1, "en": 1})) == {"ru", "en"}
    for text, _ in farmguide.WAYSTONES.values():
        assert set(text) == {"ru", "en"}


def test_income_sums_at_the_prices_given():
    prices = {"Divine Orb": 1.0, "Chaos Orb": 0.1}
    out = farmguide.income(prices.get, "en")
    fr = out["fractures"]["session"]
    # 103 divines + 260 chaos at 0.1 + the waystones the author priced; nothing else has a price here
    assert fr["income"] == round(103 + 26 + 25, 1)
    assert "Fracturing Orb" in out["fractures"]["missing"]
    assert fr["cost"] == round(50 * 0.1 + 90, 1) and fr["perHour"] == round(fr["net"] / 5, 1)
    # a wombgift is worth 7 chaos by the author's word: today's chaos price makes it
    br = out["breach_t1"]["session"]
    assert br["drops"][0]["via"] == {"name": "Chaos Orb", "qty": 7} and br["income"] == round(500 * 0.7, 1)
    assert br["perMap"] == round(br["net"] / 80, 2) and br["perHour"] is None
    assert out["craft_waystones"]["recipes"][0]["div"] == round(1 * 0.1, 3)
