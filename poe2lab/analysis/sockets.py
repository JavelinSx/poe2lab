"""Best rune / soul core for every socket of items that can still be modified."""
from dataclasses import dataclass, field
from types import SimpleNamespace

from .gradients import metric_changes

# Crafting augments that transform or destroy the item rather than add stats
NOT_STAT_AUGMENT = ("destroys", "ransform", "additional Crafted", "When socketed")
# Aldur's Legacy runes ("Legacy of ...") only work for Druids (per the player; PoB's data does not say so)
CLASS_ONLY = {"Legacy of": "Druid"}


@dataclass
class SocketOption:
    name: str
    lines: list[str]
    score: float
    changes: dict[str, float]


@dataclass
class SocketSlot:
    slot: str
    index: int
    current: str
    current_score: float  # what the current augment provides now
    best: list[SocketOption] = field(default_factory=list)


def _score(changes, mode, weights):
    from .report import score
    return score(SimpleNamespace(one=changes), mode, weights)


def _allowed(opt: dict, info: dict, others: list[str], char_level: int, char_class: str) -> bool:
    if any(opt["name"].startswith(prefix) and char_class != cls for prefix, cls in CLASS_ONLY.items()):
        return False
    if info["rarity"] == "UNIQUE" and not opt["unique"]:
        return False
    if opt["levelReq"] > char_level:
        return False
    if opt["limit"] == 1 and opt["name"] in others:
        return False
    return not any(x in l for x in NOT_STAT_AUGMENT for l in opt["lines"])


def plan_sockets(engine, config: dict, mode: str, weights: dict, top: int = 3) -> list[SocketSlot]:
    info_ = engine.info()
    char_level, char_class = info_["level"], info_["class"]
    base = engine.what_if(config=config)
    out = []
    for item in engine.equipped_item_details():
        if "Swap" in item["slot"] or item["corrupted"]:  # corrupted items cannot be modified at all
            continue
        info = engine.socket_info(item["slot"])
        for i in range(info["sockets"]):
            runes = list(info["runes"])
            empty = runes[:i] + ["None"] + runes[i + 1:]
            without = engine.what_if(config=config, replace_runes=(item["slot"], empty))
            current = {m: -v for m, v in metric_changes(without, base).items()}
            slot = SocketSlot(item["slot"], i + 1, runes[i], _score(current, mode, weights))
            others = runes[:i] + runes[i + 1:]
            options = []
            for opt in info["options"]:
                if opt["name"] == runes[i] or not _allowed(opt, info, others, char_level, char_class):
                    continue
                names = runes[:i] + [opt["name"]] + runes[i + 1:]
                changes = metric_changes(engine.what_if(config=config, replace_runes=(item["slot"], names)), base)
                options.append(SocketOption(opt["name"], opt["lines"], _score(changes, mode, weights), changes))
            slot.best = sorted((o for o in options if o.score > 0), key=lambda o: -o.score)[:top]
            out.append(slot)
    return out
