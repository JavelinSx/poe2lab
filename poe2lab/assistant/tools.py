"""Tools the assistant can call. Every number it reports must come from here, i.e. from the PoB engine."""
import json
from dataclasses import asdict

from ..analysis.gradients import compute, metric_changes
from ..analysis.items import compare
from ..analysis.report import build_report, defence_weights
from ..analysis.slots import plan_slot
from ..analysis.stats import mod_line
from ..analysis.threats import MapProfile, survivable_hits
from ..analysis.tree import analyse as analyse_tree
from ..data.moddb import ModDB
from ..engine import PobError

SPECS = [
    {"type": "function", "function": {
        "name": "build_report",
        "description": "Full analysis of the build: problems (broken in game / main weaknesses), survivable monster "
                       "hit per damage type, recovery, damage core (Rage etc.), what PoB does not model, "
                       "damage range for enemy debuffs, best mods for the goal and an upgrade path.",
        "parameters": {"type": "object", "properties": {
            "goal": {"type": "string", "enum": ["damage", "balanced", "defence"]}}}}},
    {"type": "function", "function": {
        "name": "evaluate_mods",
        "description": "Exact effect of adding mod lines to the character (PoB wording, e.g. "
                       "'20% increased Attack Speed', '+30% to Chaos Resistance') and/or enemy mods. "
                       "Use it to check any 'what if' instead of estimating.",
        "parameters": {"type": "object", "properties": {
            "mods": {"type": "array", "items": {"type": "string"}},
            "enemy_mods": {"type": "array", "items": {"type": "string"}}}, "required": ["mods"]}}},
    {"type": "function", "function": {
        "name": "compare_item",
        "description": "Compare a candidate item with the equipped one in a slot. item_text is the item as copied "
                       "from the game (Ctrl+C) or in PoB format.",
        "parameters": {"type": "object", "properties": {
            "slot": {"type": "string", "description": "Weapon 1, Helmet, Body Armour, Gloves, Boots, Amulet, "
                                                      "Ring 1, Ring 2, Belt"},
            "item_text": {"type": "string"}}, "required": ["slot", "item_text"]}}},
    {"type": "function", "function": {
        "name": "slot_plan",
        "description": "For one equipped item: value of each affix, load-bearing/utility affixes, best mods that "
                       "can roll on its base and what to craft or look for.",
        "parameters": {"type": "object", "properties": {"slot": {"type": "string"}}, "required": ["slot"]}}},
    {"type": "function", "function": {
        "name": "stat_values",
        "description": "Value of one typical affix of each common stat for damage, survivable hits and recovery.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "tree_options",
        "description": "Passive tree: notables/keystones within reach priced by their whole path (value per point), "
                       "allocated branches worth less than the best option (respec candidates), and nodes whose "
                       "effect PoB does not see.",
        "parameters": {"type": "object", "properties": {
            "goal": {"type": "string", "enum": ["damage", "balanced", "defence"]},
            "points": {"type": "integer", "description": "reach in passive points, 3-10 (default 6)"}}}}},
    {"type": "function", "function": {
        "name": "propose_profile_change",
        "description": "Suggest recording a fact about real play in the build profile, e.g. a correction for a "
                       "mechanic PoB does not model. Does not change anything: the user confirms it in the UI.",
        "parameters": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["correction", "note", "rage", "mana_sustained"]},
            "value": {"type": "string", "description": "for correction: a mod line in PoB wording"},
            "uptime": {"type": "number"}, "reason": {"type": "string"}}, "required": ["kind", "value", "reason"]}}},
]


class Toolbox:
    def __init__(self, engine, profile: MapProfile, db: ModDB | None = None):
        self.engine = engine
        self.profile = profile
        self._db = db
        self.proposals: list[dict] = []

    @property
    def db(self) -> ModDB:
        if self._db is None:
            self._db = ModDB.from_engine(self.engine)
        return self._db

    def _tree_options(self, goal: str = "balanced", points: int = 6):
        r = analyse_tree(self.engine, self.profile, mode=goal, max_points=max(1, min(int(points), 10)), top=8)
        keep = ("name", "type", "points", "via", "stats", "changes", "perPoint", "lossPerPoint")
        slim = lambda rows: [{k: row[k] for k in keep if k in row} for row in rows]
        return {"growth": slim(r["growth"]), "respec": slim(r["respec"][:6]),
                "pobCannotSee": [b["name"] for b in r["unseen"]], "attributeNodes": len(r["attributes"])}

    def call(self, name: str, arguments: str | dict) -> str:
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
            result = getattr(self, f"_{name}")(**args)
        except (AttributeError, TypeError) as err:
            result = {"error": f"bad tool call {name}: {err}"}
        except (PobError, ValueError) as err:
            result = {"error": str(err)}
        return json.dumps(result, ensure_ascii=False, default=_round)

    def _build_report(self, goal: str = "balanced"):
        r = build_report(self.engine, self.profile, mode=goal, steps=5, top=8)
        return {k: r[k] for k in ("build", "baseline", "gates", "notModelled", "core", "damageRange", "ranking",
                                  "path")} | {"conditions": r["conditions"][:10]}

    def _evaluate_mods(self, mods: list[str], enemy_mods: list[str] | None = None):
        config = self.profile.config()
        base = self.engine.what_if(config=config)
        out = self.engine.what_if(config=config, mods=mods, enemy_mods=enemy_mods or [])
        return {"percentChange": metric_changes(out, base),
                "after": {k: out.get(k) for k in ("CombinedDPS", "Life", "TotalEHP", "Speed", "HitChance",
                                                  "PhysicalMaximumHitTaken", "ChaosMaximumHitTaken")}}

    def _compare_item(self, slot: str, item_text: str):
        return asdict(compare(self.engine, self.profile.config(), slot, item_text))

    def _slot_plan(self, slot: str):
        item = next((i for i in self.engine.equipped_item_details() if i["slot"] == slot), None)
        if item is None:
            return {"error": f"no item in slot {slot}"}
        weights = defence_weights(survivable_hits(self.engine, self.profile))
        plan = plan_slot(self.engine, self.db, self.profile.config(), item, "balanced", weights,
                         check_mana=not self.profile.mana_sustained)
        return asdict(plan) | {"uncertain": plan.uncertain}

    def _stat_values(self):
        _, grads = compute(self.engine, config=self.profile.config())
        return [{"mod": mod_line(g.stat), "percentChange": g.one} for g in grads
                if any(abs(v) >= 0.5 for v in g.one.values())]

    def _propose_profile_change(self, kind: str, value: str, reason: str, uptime: float = 1.0):
        if kind == "correction" and not self.engine.can_parse_mod(value):
            return {"error": f"PoB cannot parse '{value}'; use PoB mod wording"}
        proposal = {"kind": kind, "value": value, "uptime": uptime, "reason": reason}
        self.proposals.append(proposal)
        return {"status": "proposed, waiting for the user to confirm", "proposal": proposal}


def _round(x):
    return x if not isinstance(x, float) else round(x, 2)
