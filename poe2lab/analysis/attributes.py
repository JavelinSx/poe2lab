"""Attribute requirements as a dependency network: who needs what, who provides it, and the cheapest fix.

Items and passive nodes provide attributes; items, gems and grouped support gems require them. Swapping one item
can drop an attribute below another source's requirement, so each provider is checked by taking it off."""
import math
from dataclasses import dataclass, field

ATTRS = ("Str", "Dex", "Int")
NODE_VALUE = 5  # a PoE2 attribute passive gives +5 to the chosen attribute
LOW_MARGIN = 10


@dataclass
class AttributeStatus:
    attr: str
    have: float
    need: float
    from_nodes: int  # attribute passives chosen as this attribute
    needed_by: list[str]  # sources requiring more than `have` (if short) or the largest requirement

    @property
    def margin(self) -> float:
        return self.have - self.need


@dataclass
class NodeSwap:
    """Re-choose attribute passives: `nodes` nodes from `donor` to `target`."""
    donor: str
    target: str
    nodes: int
    dps_pct: float
    life_pct: float
    all_met: bool  # every requirement satisfied after the swap


@dataclass
class ItemDependency:
    slot: str
    item: str
    provides: dict[str, float]  # attributes lost when the item is taken off
    breaks: list[str] = field(default_factory=list)  # other sources whose requirement is then unmet
    margin_after: dict[str, float] = field(default_factory=dict)


def status(stats: dict, sources: list[dict], counts: dict[str, int]) -> list[AttributeStatus]:
    out = []
    for a in ATTRS:
        have, need = stats.get(a, 0), stats.get(f"Req{a}", 0)
        mine = [s for s in sources if s["attr"] == a]
        if need > have:
            names = [s["name"] for s in mine if s["req"] > have]
        else:
            names = [s["name"] for s in mine if s["req"] == need]
        out.append(AttributeStatus(a, have, need, counts.get(a, 0), names))
    return out


def _requirements_met(out: dict) -> bool:
    return all(out.get(a, 0) >= out.get(f"Req{a}", 0) for a in ATTRS)


def node_swaps(engine, config: dict, statuses: list[AttributeStatus]) -> list[NodeSwap]:
    """For each short attribute, try moving the fewest attribute passives from every other attribute."""
    base = engine.what_if(config=config)
    by_attr = {s.attr: s for s in statuses}
    swaps = []
    for target in (s for s in statuses if s.margin < 0):
        nodes = math.ceil(-target.margin / NODE_VALUE)
        for donor in ATTRS:
            if donor == target.attr or by_attr[donor].from_nodes < nodes:
                continue
            amount = nodes * NODE_VALUE
            r = engine.what_if(config=config, mods=[f"-{amount} to {_full(donor)}", f"+{amount} to {_full(target.attr)}"])
            swaps.append(NodeSwap(
                donor, target.attr, nodes,
                dps_pct=(r["CombinedDPS"] - base["CombinedDPS"]) / base["CombinedDPS"] * 100,
                life_pct=(r["Life"] - base["Life"]) / base["Life"] * 100,
                all_met=_requirements_met(r),
            ))
    return sorted(swaps, key=lambda s: (not s.all_met, -(s.dps_pct + s.life_pct)))


def item_dependencies(engine, config: dict, sources: list[dict]) -> list[ItemDependency]:
    """Take each equipped item off and see which other requirements stop being met."""
    base = engine.what_if(config=config)
    deps = []
    for item in engine.equipped_items():
        r = engine.what_if(config=config, remove_slot=item["slot"])
        provides = {a: base[a] - r[a] for a in ATTRS if base[a] - r[a] > 0}
        if not provides:
            continue
        others = [s for s in sources if s["name"] != item["name"]]
        breaks = sorted({f"{s['name']} ({s['req']:g} {s['attr']})" for s in others
                         if s["attr"] in provides and s["req"] > r[s["attr"]]})
        margin_after = {a: r[a] - max((s["req"] for s in others if s["attr"] == a), default=0) for a in provides}
        deps.append(ItemDependency(item["slot"], item["name"], provides, breaks, margin_after))
    return deps


SUPPORT_COLOR = {"Str": "^xE05030", "Dex": "^x70FF70", "Int": "^x7070FF"}


@dataclass
class SupportAtRisk:
    """A support of the short colour: the game switches one of them off, PoB keeps all of them on."""
    group: int
    index: int
    name: str
    skill: str
    skill_dps_pct: float  # its own skill's DPS change when the support is off
    main_dps_pct: float  # main skill's DPS change


def supports_at_risk(engine, config: dict, attr: str) -> list[SupportAtRisk]:
    gems = engine.gems()
    skill_of = {g["group"]: g["name"] for g in gems if not g["support"] and g["index"] == 1}
    main_base = engine.what_if(config=config)
    out = []
    for g in gems:
        if not (g["support"] and g["enabled"] and g["color"] == SUPPORT_COLOR[attr]):
            continue
        pair = [(g["group"], g["index"])]
        own_base = engine.what_if(config=config, main_socket_group=g["group"])
        own_off = engine.what_if(config=config, main_socket_group=g["group"], disable_gems=pair)
        main_off = engine.what_if(config=config, disable_gems=pair)
        out.append(SupportAtRisk(
            g["group"], g["index"], g["name"], skill_of.get(g["group"], "?"),
            skill_dps_pct=_pct(own_off["CombinedDPS"], own_base["CombinedDPS"]),
            main_dps_pct=_pct(main_off["CombinedDPS"], main_base["CombinedDPS"]),
        ))
    return sorted(out, key=lambda s: (s.main_dps_pct, s.skill_dps_pct))


def _pct(new: float, old: float) -> float:
    return (new - old) / old * 100 if old else 0.0


def _full(attr: str) -> str:
    return {"Str": "Strength", "Dex": "Dexterity", "Int": "Intelligence"}[attr]
