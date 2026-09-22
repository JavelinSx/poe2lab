"""Everything the tool knows about a build in one JSON document: report, per-slot plans, crafting path, sockets
and prices. Meant for an LLM (or a UI) to read instead of parsing several console reports."""
from dataclasses import asdict

from .analysis.report import build_report, defence_weights
from .analysis.slots import craft_path, plan_all
from .analysis.sockets import plan_sockets
from .analysis.sources import describe
from .analysis.threats import MapProfile, survivable_hits
from .data.moddb import ModDB


def build_dossier(engine, profile: MapProfile, mode: str = "balanced", prices=None, craft_steps: int = 6) -> dict:
    report = build_report(engine, profile, mode=mode)
    weights = defence_weights(survivable_hits(engine, profile))
    config = profile.config()
    db = ModDB.from_engine(engine)
    essences = engine.export_essences()
    by_id = {m.id: m for m in db.mods}

    path = []
    for step in craft_path(engine, db, config, mode, weights, steps=craft_steps):
        entry = asdict(step)
        mod = by_id.get(step.mod_id)
        entry["sources"] = describe(db, essences, mod, step.item_type, prices) if mod else []
        path.append(entry)

    sockets = []
    for s in plan_sockets(engine, config, mode, weights):
        entry = asdict(s)
        for opt in entry["best"]:
            price = prices.get(opt["name"]) if prices else None
            opt["price"] = prices.describe(price) if price else None
            opt["scorePerDivine"] = prices.per_divine(opt["score"], price) if price else None
        sockets.append(entry)

    return {
        "report": report,
        "slots": [asdict(p) | {"uncertain": p.uncertain} for p in plan_all(engine, db, config, mode, weights)],
        "craftPath": path,
        "sockets": sockets,
        "prices": {"league": prices.league, "exaltedPerDivine": prices.exalted_per_divine} if prices else None,
        "notes": [
            "Scores use the report's goal weights; a mod's score is the % gain in the weighted metrics.",
            "Crafting path is a target affix set, not a crafting procedure: PoE2 game data has no real spawn weights.",
            "Monster hit values are the largest monster base hit survived (PoB cannot model real PoE2 monster skills).",
            "Load-bearing affixes (spirit, attributes, resistance caps, mana) and utility affixes are never suggested for removal.",
        ],
    }
