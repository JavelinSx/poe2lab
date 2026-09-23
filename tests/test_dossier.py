"""The one-file dossier holds every section and serialises to JSON."""
import json
from pathlib import Path

from poe2lab.analysis.threats import MapProfile
from poe2lab.dossier import build_dossier
from poe2lab.economy.ninja import PriceBook
from poe2lab.engine import PobEngine

TITAN = (Path(__file__).resolve().parent / "fixtures" / "titan.txt").read_text()


def test_dossier_sections_and_prices():
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(5)
    prices = PriceBook.from_overviews("Test", {"Runes": {
        "core": {"rates": {"exalted": 500.0}},
        "lines": [{"id": "perfect-rebirth-rune", "primaryValue": 0.08, "volumePrimaryValue": 5.0}],
    }})
    d = json.loads(json.dumps(build_dossier(e, MapProfile(), prices=prices, craft_steps=2), ensure_ascii=False))
    assert {"report", "slots", "craftPath", "sockets", "prices", "notes"} <= set(d)
    assert len(d["craftPath"]) == 2 and d["craftPath"][0]["sources"]
    boots = [s for s in d["sockets"] if s["slot"] == "Boots"][0]  # gloves and body armour are corrupted, so skipped
    assert not [s for s in d["sockets"] if s["slot"] in ("Gloves", "Body Armour")]
    rune = [o for o in boots["best"] if o["name"] == "Perfect Rebirth Rune"][0]
    assert rune["price"] == "40 ex" and rune["scorePerDivine"] > 0
