"""An item copied from the Russian client, in English for PoB: PoB reads item text in English only.

The advanced copy (Ctrl+Alt+C) names each mod's affix: poe2lab.journal finds the exact mod by it, and the mod's
English lines get the rolled numbers of the Russian ones - "46(34-47)% увеличение урона от стихий от умений атак"
fills "(34-47)% increased Elemental Damage with Attacks" with 46. The base comes by its Russian name, a unique by
its name from PoB's own uniques (its rolls filled the same way, line by line).

The plain copy (Ctrl+C) names no affix: each of its lines is translated by the stat templates (the trade site's in
both languages, then the game's own descriptions), its numbers kept; the marks PoB reads stay - "(rune)",
"(implicit)", "(desecrated)", a rune's "Связаны:" as "Bonded:". What PoB computes itself (damage, crit, speed,
requirements) and a trade note are left out."""
import re
from functools import lru_cache

from . import gamedata, i18n, journal
from .data.moddb import ModDB

_ROLLED = re.compile(r"(-?\d+(?:\.\d+)?)\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")  # 46(34-47): rolled 46
_RANGE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")  # (34-47) in a template
RARITY = {"normal": "Normal", "magic": "Magic", "rare": "Rare", "unique": "Unique"}


class TranslationError(ValueError):
    pass


# the plain copy's marks PoB reads at a line's end, and the ones it does not need (a property's kind)
_MARK = re.compile(r"\s*\((rune|implicit|desecrated|crafted|fractured|enchant|mutated|augmented|physical|cold|fire|"
                   r"lightning|chaos|unmet)\)\s*$", re.I)
POB_MARKS = {"rune", "implicit", "desecrated", "crafted", "fractured", "enchant", "mutated"}
BONDED = re.compile(r"^(Связаны|Bonded):\s*", re.I)
# what goes into the English text from the item's properties; every other property PoB computes itself
PROPERTIES = {"качество": "Quality", "гнезда": "Sockets", "уровень предмета": "Item Level"}
SKIPPED = re.compile(r"^(примечание|note):", re.I)
CORRUPTED_RU = {"порча", "осквернено", "corrupted"}


@lru_cache(maxsize=1)
def _reverse_stats() -> dict[str, str]:
    """Russian template key -> English template: the trade site's pairs first (their English keeps the case and
    the signs the game prints), then the game's own descriptions (English keys, lower case)."""
    out = {}
    try:
        for pair in i18n.stat_templates("ru"):
            out.setdefault(i18n.stat_key(pair["ru"]), pair["en"])
    except OSError:
        pass
    for en_key, ru in gamedata.load_templates("ru").items():
        out.setdefault(i18n.stat_key(ru), en_key)
    return out


def translate_mod(line: str) -> str | None:
    """One Russian mod line in English with its numbers and marks; None if no template matches."""
    mark = _MARK.search(line)
    core = _MARK.sub("", line)
    bonded = BONDED.match(core)
    core = BONDED.sub("", core)
    parts = []
    for part in core.split(" / "):
        template = _reverse_stats().get(i18n.stat_key(part))
        text = i18n.fill(template, part) if template else ""
        if not text:
            return None
        parts.append(i18n.pob_line(text) if "#" in text else text)
    out = ("Bonded: " if bonded else "") + " / ".join(parts)
    if mark and mark.group(1).lower() in POB_MARKS:
        out += f" ({mark.group(1).lower()})"
    return out


def plain_to_english(text: str, p: "journal.Parsed", uniques: list[dict] = ()) -> tuple[str, list[str]]:
    """A plain copy (no affix names) in English for PoB, and the lines no template matched (left out)."""
    lines = [l.strip() for l in text.replace("\r\n", "\n").split("\n")]
    out = ["Rarity: " + RARITY.get(p.rarity, "Rare")]
    if p.rarity == "unique":
        ru_to_en = {v.lower(): k for k, v in gamedata.load_names("ru").items()}
        name = next((ru_to_en.get(n.lower()) for n in p.names if ru_to_en.get(n.lower())), None)
        found = next((u for u in uniques if u["name"] == name), None)
        if not found:
            raise TranslationError("не нашёл этот уникальный предмет в данных PoB: " + " / ".join(p.names))
        out.append(found["name"])
    elif p.rarity == "rare":
        out.append("poe2lab item")  # a rare's random name means nothing to PoB
    out += [p.base, "--------"]
    unknown, after_level, section = [], False, []
    for line in lines[1:]:
        if line.startswith("--------"):
            if section:
                out += section + ["--------"]
            section = []
            continue
        if not line or ":" in line and line.split(":")[0].lower() in ("класс предмета", "item class", "редкость", "rarity"):
            continue
        label = line.split(":")[0].strip().lower() if ":" in line else ""
        if label in PROPERTIES:
            value = _MARK.sub("", line.split(":", 1)[1]).strip()
            section.append(f"{PROPERTIES[label]}: {value}")
            if label == "уровень предмета":
                after_level = True
            continue
        if not after_level or SKIPPED.match(line):
            continue  # the name lines and what PoB computes (damage, crit, speed, requirements); a trade note
        if line.lower() in CORRUPTED_RU:
            section.append("Corrupted")
            continue
        en = translate_mod(line)
        if en is None:
            unknown.append(line)
        else:
            section.append(en)
    if section:
        out += section
    while out and out[-1] == "--------":
        out.pop()
    return "\n".join(out), unknown


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
    """The item as the English client would copy it, for PoB: by the affixes of an advanced copy, else line by line
    (a plain copy); a line no template matches is an error naming it."""
    p = journal.parse(text, db, names)
    problems = [x for x in p.problems if "Ctrl+Alt+C" not in x]
    if problems:
        raise TranslationError("; ".join(problems))
    if not p.advanced and p.rarity in ("magic", "rare", "unique"):
        english, unknown = plain_to_english(text, p, uniques)
        if unknown:
            raise TranslationError("не перевёл строки: " + "; ".join(unknown[:4]))
        return english
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
