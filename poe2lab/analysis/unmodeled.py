"""What PoB does not count but what moves the build's numbers a lot - and the corrections the player made for it.

PoB ignores the skill stats it has no calculation for and the item lines it cannot parse (poe2lab.knowledge lists
them). Most are game text PoB reads in another form: "Detonations from supported Skills deal 35% more Damage" is
"35% more Damage" for that skill, "Buff grants 13% more Armour, Evasion and Energy Shield per Stage" is that line
times the stages. Each line rewritten so PoB parses it is priced by PoB - on the skill it belongs to - so the
overview can list what matters, with what counting it would change; the rest is listed as not priced.
A correction is such a line added to the build (poe2lab.profile): each one is priced by taking it out."""
import re

from .gradients import metric_changes

# a rewrite PoB reads: the game's phrasing -> PoB's
REWRITES = [
    (re.compile(r"^(?:Buff grants |Grants )?(\d+(?:\.\d+)?)% of damage Gained as (\w+) damage$", re.I),
     r"Gain \1% of Damage as Extra \2 Damage"),
    (re.compile(r"^(?:Buff grants )?(\d+(?:\.\d+)?) (\w+) regenerated per second$", re.I), r"Regenerate \1 \2 per second"),
]
# who the line speaks of, which PoB's own lines leave out
FRAMES = re.compile(r"^(?:Buff grants |Grants |Supported Skills (?:have |deal |grant )?|Skill (?:has |deals )?|"
                    r"You and Allies in your Presence (?:have |gain )?)", re.I)
# who gets it and the rest: "Detonations from supported Skills deal 35% more Damage" -> "35% more Damage"; only these
# verbs: "Break 70% more Armour" is the enemy's armour, "Sacrifices 759 Life" is not life gained
SUBJECT = re.compile(r"^(?P<who>.+?)\s+(?:also\s+)?(?:deals?|ha(?:ve|s)|gains?|grants?)\s+(?P<rest>[+-]?\d.*)$", re.I)
# a line about the player (a buff, an infusion, "you"): counted on the skill the damage is; else on its own skill
PLAYER = re.compile(r"\b(?:buff|infusion|you|your|allies)\b", re.I)
# a line under a condition ("When you Freeze..., for each 2 Rage you have...") is not a lasting bonus
CONDITION = re.compile(r"\b(?:when|while|if|for each|per)\b|,", re.I)
PER_STAGE = re.compile(r"\s+per Stage$", re.I)
STAGES = re.compile(r"(?:maximum|up to|max\.?) (\d+) Stages?|(\d+) Stages? maximum", re.I)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
GROUP = re.compile(r"\((?:группа|group) (\d+)\)$")
# a change this big in damage or effective life is what the overview lists
BIG = 5.0
# the numbers a correction or a line is shown by: damage, effective life, recovery (regeneration does not move eHP)
SHOWN = ("dps", "ehp", "recovery")


def candidates(text: str) -> list[str]:
    """The line as it is, then the ways PoB may read it: known rewrites, without who it speaks of, from its number on."""
    text = " ".join(text.split())
    out = [text]
    for pattern, repl in REWRITES:
        if pattern.match(text):
            out.append(pattern.sub(repl, text))
    stripped = FRAMES.sub("", text)
    if stripped != text and stripped:
        out.append(stripped[0].upper() + stripped[1:])
        for pattern, repl in REWRITES:
            if pattern.match(stripped):
                out.append(pattern.sub(repl, stripped))
    m = SUBJECT.match(text)
    if m and not CONDITION.search(m.group("who")):
        out.append(m.group("rest"))
    return list(dict.fromkeys(out))


def _times(line: str, n: int) -> str:
    """The line's numbers n times ("13% more Armour" x 4 -> "52% more Armour")."""
    def mul(m):
        v = float(m.group(0)) * n
        return str(int(v)) if v == int(v) else f"{v:g}"
    return _NUMBER.sub(mul, line)


def pob_line(text: str, can_parse, siblings: tuple[str, ...] = ()) -> dict | None:
    """A line PoB reads for a game line it ignores: {"line", "stages"} (a per-stage line counted at the stages the
    skill's other lines name, else at one stage), or None."""
    per_stage = bool(PER_STAGE.search(" ".join(text.split())))
    base = PER_STAGE.sub("", " ".join(text.split())) if per_stage else text
    stages = 1
    if per_stage:
        m = next((STAGES.search(s) for s in siblings if STAGES.search(s)), None)
        stages = int(m.group(1) or m.group(2)) if m else 1
    for c in candidates(base):
        if can_parse(c):
            return {"line": _times(c, stages) if stages > 1 else c, "stages": stages if per_stage else None}
    return None


def _group_of(where: str) -> int | None:
    m = GROUP.search(where)
    return int(m.group(1)) if m else None


def _shown(changes: dict) -> dict:
    return {k: round(changes.get(k, 0.0), 1) for k in SHOWN}


def _same(line: str) -> str:
    return " ".join(line.split()).lower()


def covered_by(corrections) -> set[str]:
    """What the player's corrections count already: the lines they came from and the PoB lines they are."""
    return {c.source for c in corrections} | {_same(c.mod) for c in corrections}


def estimates(engine, gaps: list, config: dict, damage_group: int | None, covered: set[str]) -> dict:
    """Each line PoB ignores that likely matters, priced: {"big": [...], "small": [...], "unpriced": [...]}.
    `covered`: what the corrections count already (covered_by).
    A skill's line is counted on its own skill (a support's "deal 35% more Damage" is not the whole build's);
    a line of another skill than the one the damage is counted on moves only defences in the list."""
    base = engine.what_if(config=config, main_socket_group=damage_group)
    bases = {damage_group: base}
    siblings: dict[str, list[str]] = {}
    for g in gaps:
        siblings.setdefault(g.where, []).append(g.text)
    big, small, unpriced = [], [], []
    for g in gaps:
        if not g.likely_impact:
            continue
        source = f"{g.where}: {g.text}"
        if source in covered:
            continue
        row = {"source": g.source, "where": g.where, "text": g.text, "text_local": g.text_local, "key": source}
        found = pob_line(g.text, engine.can_parse_mod, tuple(siblings.get(g.where, ())))
        if not found:
            unpriced.append(row)
            continue
        if _same(found["line"]) in covered:  # the player counted this line already (written down otherwise)
            continue
        group = _group_of(g.where) if g.source == "skill" else None
        who = SUBJECT.match(" ".join(g.text.split()))
        player = (g.source == "item" or bool(who and PLAYER.search(who.group("who")))
                  or bool(FRAMES.match(g.text)) and not g.text.lower().startswith("supported"))
        own = not player and group is not None and group != damage_group
        at = group if own else damage_group
        if at not in bases:
            bases[at] = engine.what_if(config=config, main_socket_group=at)
        changes = _shown(metric_changes(engine.what_if(config=config, mods=[found["line"]], main_socket_group=at), bases[at]))
        row |= {"line": found["line"], "stages": found["stages"], "changes": changes, "otherSkill": own}
        # another skill's damage is not the build's: there only what it does to defences counts
        weight = max(abs(changes["ehp"]), abs(changes["recovery"])) if own else max(abs(v) for v in changes.values())
        (big if weight >= BIG else small).append(row | {"weight": weight})
    big.sort(key=lambda r: -r["weight"])
    small.sort(key=lambda r: -r["weight"])
    return {"big": big, "small": small, "unpriced": unpriced}


def corrections_effect(engine, block: str, lines: list[str], config: dict, damage_group: int | None) -> list[dict]:
    """Each correction's own effect: the build with it against the build without it (the others kept)."""
    out = []
    if not lines:
        return out
    full = engine.what_if(config=config, main_socket_group=damage_group)
    try:
        for i in range(len(lines)):
            engine.set_custom_mods(block, lines[:i] + lines[i + 1:])
            out.append(_shown(metric_changes(full, engine.what_if(config=config, main_socket_group=damage_group))))
    finally:
        engine.set_custom_mods(block, lines)
    return out
