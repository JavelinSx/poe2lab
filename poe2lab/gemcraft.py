"""Gems socketed the way the game socketes them: the rules a skill's gems follow, as PoB knows them.

A skill gem has a level from 1 to its cap, 20. Each gem level asks for a character level, and a gem above the
character's cannot be used. Its quality goes up to 20, a Gemcutter's Prism's cap.

A support gem's tier is its level: Pin I and Pin II are separate gems. It has no quality. It goes only into a skill
it can support, by the skill types it requires. A skill takes at most five: Jeweller's Orbs give a skill gem up to
five support sockets. Two supports of one family never share a skill. The same support may go into several skills,
except a lineage support, which goes into one (PoB's MaxLineageCount).

A skill gem holds its supports, so taking it out takes them too.

Why a gem is refused is given as a code with the gem it clashes with, so the page can word it."""

MAX_SUPPORTS = 5
MAX_QUALITY = 20


class GemError(ValueError):
    """A gem the game would not let in; the message is the player's (Russian)."""


def usable_level(gem: dict, character_level: int) -> int:
    """The highest level of the gem a character of this level can use (0: not even the first)."""
    return max((i + 1 for i, req in enumerate(gem["reqs"]) if req <= character_level), default=0)


def blocked(gem: dict, groups: list[dict], group: int, index: int | None, fits: set[str],
            character_level: int) -> dict | None:
    """Why the game would not let this support gem into socket group `group` (in place of the gem at `index`, or
    as one more): {"code": ..., "gem": the gem it clashes with}, or None. Codes: fit, family, full, lineage, level."""
    g = next((x for x in groups if x["index"] == group), None)
    if g is None or gem["id"] not in fits:
        return {"code": "fit"}
    others = [x for x in g["gems"] if x["index"] != index]
    same = next((x for x in others if x["support"] and x["family"] == gem["family"]), None)
    if same:
        return {"code": "family", "gem": same["name"]}
    if sum(1 for x in others if x["support"]) >= MAX_SUPPORTS:
        return {"code": "full"}
    if gem["lineage"]:
        for x in groups:
            if any(y["name"] == gem["name"] and not (x["index"] == group and y["index"] == index) for y in x["gems"]):
                return {"code": "lineage", "gem": x["actives"][0]["name"] if x["actives"] else gem["name"]}
    if usable_level(gem, character_level) < 1:
        return {"code": "level", "level": gem["reqs"][0]}
    return None


REASONS = {
    "fit": lambda b: "этот камень поддержки не подходит к этому скиллу",
    "family": lambda b: f"в скилле уже есть камень того же вида: {b['gem']}",
    "full": lambda b: f"у камня умения не больше {MAX_SUPPORTS} гнёзд поддержки",
    "lineage": lambda b: f"камень родословной ставят только в один скилл, он уже в «{b['gem']}»",
    "level": lambda b: f"нужен {b['level']} уровень персонажа",
}


def check(gem: dict, groups: list[dict], group: int, index: int | None, fits: set[str], character_level: int,
          level: int | None, quality: int) -> tuple[int | None, int]:
    """The level and quality the gem goes in at, if the game allows it there; raises GemError otherwise. Group 0 is
    a new skill; a support's level is its tier's (None), a skill gem's defaults to the highest the character can use."""
    target = next((x for x in groups if x["index"] == group), None)
    if group and target is None:
        raise GemError(f"нет скилла №{group}")
    at = next((x for x in target["gems"] if x["index"] == index), None) if target and index else None
    if index and at is None:
        raise GemError(f"в скилле №{group} нет камня №{index}")
    if gem["support"]:
        if not group:
            raise GemError("камень поддержки ставят в скилл, а не отдельно")
        if at is not None and not at["support"]:
            raise GemError("камень умения меняют на камень умения, а не на поддержку")
        why = blocked(gem, groups, group, index, fits, character_level)
        if why:
            raise GemError(REASONS[why["code"]](why))
        return None, 0
    if group and at is None:
        raise GemError("камень умения ставят вместо другого или отдельным скиллом")
    if at is not None and at["support"]:
        raise GemError("поддержку меняют на поддержку, а не на камень умения")
    top = usable_level(gem, character_level)
    if top < 1:
        raise GemError(f"нужен {gem['reqs'][0]} уровень персонажа")
    level = top if level is None else int(level)
    if not 1 <= level <= gem["maxLevel"]:
        raise GemError(f"уровень камня — от 1 до {gem['maxLevel']}")
    if level > top:
        raise GemError(f"камень {level} уровня требует {gem['reqs'][level - 1]} уровня персонажа")
    if not 0 <= int(quality) <= MAX_QUALITY:
        raise GemError(f"качество камня — от 0 до {MAX_QUALITY}%")
    return level, int(quality)
