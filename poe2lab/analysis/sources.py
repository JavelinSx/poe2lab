"""Where a mod can come from: a natural roll (tier and item level), an essence that guarantees it, or desecration."""
from ..data.moddb import Mod, ModDB


def essence_sources(db: ModDB, essences: list[dict], mod: Mod, item_type: str) -> list[tuple[str, str]]:
    """(essence name, the mod it guarantees) for essences giving a tier of this mod family on this item class."""
    by_id = {m.id: m for m in db.mods}
    out = []
    for e in sorted(essences, key=lambda e: e["tierLevel"]):
        given = by_id.get(e["mods"].get(item_type, ""))
        if given and given.group == mod.group and given.patterns == mod.patterns:
            out.append((e["name"], " / ".join(given.lines)))
    return out


def desecrated_sources(db: ModDB, mod: Mod) -> list[str]:
    return sorted({" / ".join(m.lines) for m in db.mods if m.set == "Desecrated" and m.patterns == mod.patterns})


def describe(db: ModDB, essences: list[dict], mod: Mod, item_type: str, prices=None) -> list[str]:
    """Human-readable sources; prices (a PriceBook) adds essence prices when available."""
    lines = [f"обычный ролл: {' / '.join(mod.lines)} (нужен уровень предмета {mod.level}+)"]
    for name, given in essence_sources(db, essences, mod, item_type):
        price = prices.get(name) if prices else None
        cost = f" — {prices.describe(price)}" if price else ""
        lines.append(f"эссенция {name}: {given}{cost}")
    lines += [f"desecration: {x}" for x in desecrated_sources(db, mod)]
    return lines
