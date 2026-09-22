"""What a build does that PoB does not calculate, found from the game data itself.

PoB silently ignores skill stats that have no calculation mapping and item lines it cannot parse. Listing them
(with the game's own descriptions) lets a player or an AI assistant see the real mechanics - e.g. that a buff grants
Rage regeneration so Rage stays at maximum - without having to ask."""
import re
from dataclasses import dataclass, field

# Stats that only affect visuals, timing of animations or targeting - never damage, defence or resources.
_NOISE = re.compile(
    r"display|visual|head_movement|animation|_delay_ms|angle|spacing|pushiness|knockback|is_area_damage|"
    r"base_deal_no_damage|show_average|prevention_duration|step_distance|use_time_|additional_base_attack_time|"
    r"minimum_channel_time|_ignore_first_|quality_display|can_create_|leap_slam_always"
)
# Item lines about when a charm/flask triggers or what it recovers when used - PoB handles those elsewhere.
_ITEM_NOISE = re.compile(r"^Used when |when used$|Recovery to|Charges|^Recover \d+ ", re.I)
# Words hinting that an ignored stat affects numbers the player cares about.
_IMPACT = re.compile(r"damage|speed|rage|glory|crit|life|mana|resist|armour|evasion|energy_shield|gain|regen|"
                     r"prowess|charge|duration|cooldown|leech|penetrat|more|less|final", re.I)


@dataclass
class Gap:
    source: str  # "skill" or "item"
    where: str  # skill name / item name and slot
    what: str  # stat id or item line
    text: str  # readable game text when available
    likely_impact: bool  # looks like it changes damage/defence/resources
    text_local: str = ""  # the same text in the player's language (official, from the game files) when available


@dataclass
class Mechanics:
    gaps: list[Gap] = field(default_factory=list)
    skills: list[dict] = field(default_factory=list)  # name, group, description, readable lines
    uniques: list[dict] = field(default_factory=list)  # slot, name, lines


def collect(engine, statdesc_dir=None) -> Mechanics:
    """`statdesc_dir`: stat descriptions in the player's language (poe2lab.gamedata); adds `linesLocal` to skills and
    `text_local` to gaps."""
    raw = engine.mechanics_raw(statdesc_dir)
    m = Mechanics()
    for s in raw["skills"]:
        lines = [l for st in s["statSets"] for l in st["lines"]]
        local = [l for st in s["statSets"] for l in st.get("linesLocal", [])]
        m.skills.append({"group": s["group"], "name": s["name"], "support": s["support"],
                         "description": s["description"], "lines": list(dict.fromkeys(lines)),
                         "linesLocal": list(dict.fromkeys(local))})
        for st in s["statSets"]:
            for u in st["unmapped"]:
                if _NOISE.search(u["stat"]) or not u["value"]:
                    continue
                text = " / ".join(u["text"]) or f"{u['stat']} = {u['value']:g}"
                m.gaps.append(Gap("skill", f"{s['name']} (группа {s['group']})", u["stat"], text,
                                  bool(_IMPACT.search(u["stat"])), " / ".join(u.get("textLocal", []))))
    for it in raw["items"]:
        for line in _join_wrapped(it["unparsed"]):
            if _ITEM_NOISE.search(line):
                continue
            m.gaps.append(Gap("item", f"{it['name']} ({it['slot']})", line, line, bool(_IMPACT.search(line))))
        if it["uniqueText"]:
            m.uniques.append({"slot": it["slot"], "name": it["name"], "lines": it["uniqueText"]})
    m.gaps = _dedupe(m.gaps)
    return m


# PoB keeps a wrapped item line as two: "... of a random Element per" + "Rune Socketed in Equipped Items".
_DANGLING = re.compile(r"\b(per|for|of|to|and|with|in|the|a|an|by|from|while|if|when|as|on|among)$", re.I)


def _join_wrapped(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if out and _DANGLING.search(out[-1]):
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return out


def _dedupe(gaps: list[Gap]) -> list[Gap]:
    seen, out = set(), []
    for g in gaps:
        key = (g.where.split(" (")[0], g.what)
        if key not in seen:
            seen.add(key)
            out.append(g)
    return sorted(out, key=lambda g: (not g.likely_impact, g.source, g.where))
