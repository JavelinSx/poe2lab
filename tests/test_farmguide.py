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
