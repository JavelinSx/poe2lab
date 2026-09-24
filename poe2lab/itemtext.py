"""An item copied from the Russian client, in English for PoB: PoB reads item text in English only.

The advanced copy (Ctrl+Alt+C) names each mod's affix: poe2lab.journal finds the exact mod by it, and the mod's
English lines get the rolled numbers of the Russian ones - "46(34-47)% увеличение урона от стихий от умений атак"
fills "(34-47)% increased Elemental Damage with Attacks" with 46. The base comes by its Russian name, a unique by
its name from PoB's own uniques (its rolls filled the same way, line by line)."""
import re

from . import gamedata, journal
from .data.moddb import ModDB

_ROLLED = re.compile(r"(-?\d+(?:\.\d+)?)\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")  # 46(34-47): rolled 46
_RANGE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")  # (34-47) in a template
RARITY = {"normal": "Normal", "magic": "Magic", "rare": "Rare", "unique": "Unique"}


class TranslationError(ValueError):
    pass


def is_russian(text: str) -> bool:
    return text.lstrip().startswith("Класс предмета:") or "Редкость:" in text


def fill(template: str, rolled: list[str]) -> str:
    """The template's ranges replaced by the rolled numbers in order (the middle when none is left)."""
    def one(m):
        if rolled:
            return rolled.pop(0)
        lo, hi = float(m.group(1)), float(m.group(2))
        mid = (lo + hi) / 2
        return f"{mid:g}" if "." in m.group(0) else str(round(mid))
    return _RANGE.sub(one, template)


def rolled_numbers(lines: list[str]) -> list[str]:
    return [m.group(1) for line in lines for m in _ROLLED.finditer(line)]


def _unique(p: journal.Parsed, uniques: list[dict]) -> list[str]:
    """A unique's English lines from PoB's catalogue, its name found by the Russian name, rolls filled in order."""
    ru_to_en = {v.lower(): k for k, v in gamedata.load_names("ru").items()}
    wanted = {ru_to_en.get(n.lower(), n) for n in p.names}
    found = next((u for u in uniques if u["name"] in wanted and u["base"] == p.base), None) \
        or next((u for u in uniques if u["name"] in wanted), None)
    if not found:
        raise TranslationError("не нашёл этот уникальный предмет в данных PoB: " + " / ".join(p.names))
    return [found["name"]], found["lines"]


def to_english(text: str, db: ModDB, names: journal.Names, uniques: list[dict] = ()) -> str:
    """The item as the English client would copy it, for PoB."""
    p = journal.parse(text, db, names)
    problems = [x for x in p.problems if "Ctrl+Alt+C" not in x]
    if problems:
        raise TranslationError("; ".join(problems))
    base = db.bases[p.base]
    lines = ["Rarity: " + RARITY.get(p.rarity, "Rare")]
    if p.rarity == "unique":
        name, mod_lines = _unique(p, uniques)
        all_rolled = rolled_numbers([l for m in p.mods for l in m.lines] or p.names)  # unique lines have no affix
        mod_lines = [fill(l, all_rolled) for l in mod_lines]
        lines += name
    else:
        if p.rarity in ("magic", "rare") and not p.advanced:
            raise TranslationError("для сравнения нужна расширенная копия: наведи на вещь в игре и нажми "
                                   "Ctrl+Alt+C — с ней видны названия модов")
        if p.rarity == "rare":
            lines.append("poe2lab item")  # a rare's random name means nothing to PoB
        mod_lines = []
        for m in p.mods:
            rolled = rolled_numbers(m.lines)
            mod_lines += [fill(t, rolled) for t in m.mod.lines]
    lines += [p.base, "--------"]
    if p.quality:
        lines += [f"Quality: {p.quality}", "--------"]  # PoB reads a bare number
    lines += [f"Item Level: {p.item_level}", "--------"]
    implicit = [l for l in (base.get("implicit") or "").split("\n") if l.strip()]
    if implicit and p.rarity != "unique":
        rolled = rolled_numbers(p.implicits)
        lines += [fill(t, rolled) + " (implicit)" for t in implicit] + ["--------"]
    lines += mod_lines
    if p.corrupted:
        lines += ["--------", "Corrupted"]
    return "\n".join(lines)
