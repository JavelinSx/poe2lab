"""The one-file dossier holds every section and serialises to JSON."""
import json
from pathlib import Path

from poe2lab.analysis.threats import MapProfile
from poe2lab.dossier import build_dossier
from poe2lab.economy.ninja import PriceBook
from poe2lab.engine import PobEngine

TITAN = (Path(__file__).resolve().parents[1] / "builds" / "titan.txt").read_text()


def test_dossier_sections_and_prices():
    e = PobEngine()
    e.load_code(TITAN)
    e.set_main_skill(4)
    prices = PriceBook.from_overviews("Test", {"SoulCores": {
        "core": {"rates": {"exalted": 500.0}},
        "lines": [{"id": "soul-core-of-tacati", "primaryValue": 0.08, "volumePrimaryValue": 5.0}],
    }})
    d = json.loads(json.dumps(build_dossier(e, MapProfile(), prices=prices, craft_steps=2), ensure_ascii=False))
    assert {"report", "slots", "craftPath", "sockets", "prices", "notes"} <= set(d)
    assert len(d["craftPath"]) == 2 and d["craftPath"][0]["sources"]
    gloves = [s for s in d["sockets"] if s["slot"] == "Gloves"][0]  # boots are corrupted, so skipped
    tacati = [o for o in gloves["best"] if o["name"] == "Soul Core of Tacati"][0]
    assert tacati["price"] == "40 ex" and tacati["scorePerDivine"] > 0
