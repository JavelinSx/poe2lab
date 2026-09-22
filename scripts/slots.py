"""Per-slot plan: value of every affix you wear, best mods that can roll on each base, and what to craft or look for.

Example: python scripts/slots.py builds/titan.txt --group 4 --mode balanced
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poe2lab.analysis.report import MODES, defence_weights
from poe2lab.analysis.slots import craft_path, plan_all
from poe2lab.analysis.sockets import plan_sockets
from poe2lab.analysis.sources import describe
from poe2lab.analysis.threats import MapProfile, survivable_hits
from poe2lab.data.moddb import ModDB
from poe2lab.economy.ninja import PriceBook
from poe2lab.engine import PobEngine

MODE_NAMES = {"damage": "урон", "balanced": "баланс", "defence": "защита"}


def effect(ch: dict) -> str:
    parts = [(ch["dps"], "DPS"), (ch["phys_hit"], "физ"), (ch["fire_hit"], "огонь"), (ch["cold_hit"], "холод"),
             (ch["lightning_hit"], "молн"), (ch["chaos_hit"], "хаос"), (ch["recovery"], "лечение")]
    return ", ".join(f"{n} {v:+.1f}%" for v, n in parts if abs(v) >= 0.3) or "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path)
    ap.add_argument("--group", type=int)
    ap.add_argument("--skill", type=int, default=1)
    ap.add_argument("--mode", default="balanced", choices=list(MODES))
    ap.add_argument("--rage", type=int)
    ap.add_argument("--top", type=int, default=4)
    ap.add_argument("--slot", help="only this slot")
    ap.add_argument("--path", type=int, default=6, help="steps of the cross-slot crafting path (0 = skip)")
    ap.add_argument("--sockets", action=argparse.BooleanOptionalAction, default=True, help="socket (rune) plan")
    ap.add_argument("--league", help="poe.ninja league for prices (default: current challenge league)")
    ap.add_argument("--prices", action=argparse.BooleanOptionalAction, default=True, help="fetch poe.ninja prices")
    args = ap.parse_args()

    code = args.build.resolve().read_text()
    engine = PobEngine()
    engine.load_code(code)
    if args.group:
        engine.set_main_skill(args.group, args.skill)
    profile = MapProfile(rage=args.rage)
    weights = defence_weights(survivable_hits(engine, profile))
    db = ModDB.from_engine(engine)
    prices = None
    if args.prices:
        try:
            prices = PriceBook.load(args.league)
            print(f"Цены: poe.ninja, лига {prices.league} (1 div = {prices.exalted_per_divine:.0f} ex)")
        except OSError as err:
            print(f"Цены недоступны ({err}); продолжаю без них")

    t = time.perf_counter()
    plans = plan_all(engine, db, profile.config(), args.mode, weights, args.top)
    print(f"План по слотам, цель — {MODE_NAMES[args.mode]} (очки = та же оценка, что в отчёте; {time.perf_counter() - t:.1f} с)")
    for p in plans:
        if args.slot and p.slot != args.slot:
            continue
        state = "испорчен" if p.corrupted else "можно крафтить"
        print(f"\n== {p.slot}: {p.item} ({p.base}, ур. {p.item_level}, {state}) — "
              f"префиксы {p.count('Prefix')}/{p.limit}, суффиксы {p.count('Suffix')}/{p.limit}"
              f"{'  (счёт приблизительный)' if p.uncertain else ''}")
        for a in p.affixes:
            note = "  ≈ сумма нескольких модов" if a.merged else ""
            if a.holds:
                note += f"  НЕСУЩИЙ: без него сломается {', '.join(a.holds)}"
            if a.utility:
                note += "  утилити: PoB не оценивает, решай сам"
            print(f"   {a.type[:3]} T{a.tier}/{a.tiers} {' / '.join(a.lines):52} {a.score:+6.1f}  ({effect(a.changes)}){note}")
        for u in p.unknown:
            print(f"   ??? {u}  (не удалось определить мод)")
        print("   Лучшее, что может выпасть на эту базу (топ-ролл лучшего тира для этого уровня):")
        for kind in ("Prefix", "Suffix"):
            for c in [c for c in p.candidates if c.type == kind][: args.top]:
                print(f"     {kind[:3]} {' / '.join(c.lines):52} {c.score:+6.1f}  ({effect(c.changes)})")
        for act in p.actions:
            print(f"   → {act}")

    if args.path and not args.slot:
        t = time.perf_counter()
        path = craft_path(engine, db, profile.config(), args.mode, weights, steps=args.path)
        print(f"\nПУТЬ КРАФТА ПО ВСЕМ СЛОТАМ (только предметы, которые можно крафтить; после каждого шага всё пересчитано, "
              f"{time.perf_counter() - t:.1f} с)")
        print("  Это целевой набор аффиксов, без учёта того, как его получить крафтом (случайность, омены, цена — следующий этап);")
        print("  шаги, которые снимают кап резиста или ломают spirit/атрибуты/ману, отброшены.")
        by_id = {m.id: m for m in db.mods}
        essences = engine.export_essences()
        for i, s in enumerate(path, 1):
            how = f"заменить «{' / '.join(s.removed)}» на" if s.removed else "докрафтить"
            note = "  (проверь, что слот свободен)" if s.uncertain and not s.removed else ""
            print(f"  {i}. {s.slot}: {how} «{' / '.join(s.added)}»  {s.score:+.1f}  ({effect(s.changes)}){note}")
            if s.mod_id in by_id:
                for src in describe(db, essences, by_id[s.mod_id], s.item_type, prices):
                    print(f"       откуда: {src}")
        if path:
            print(f"  Итого против текущего: {effect(path[-1].total)}")
        else:
            print("  нечего улучшать крафтом")

    if args.sockets and not args.slot:
        t = time.perf_counter()
        sockets = plan_sockets(engine, profile.config(), args.mode, weights)
        print(f"\nСОКЕТЫ: лучшая руна / соул-кор для каждого сокета ({time.perf_counter() - t:.1f} с).")
        print("  Для испорченных предметов — только вставки, которые туда разрешены. Цифра у варианта — выгода замены")
        print("  относительно текущей вставки; каждый сокет оценён отдельно (два хаос-кора подряд не сложатся так же).")
        for s in sockets:
            print(f"  {s.slot}, сокет {s.index}: сейчас {s.current} (даёт {s.current_score:+.1f})")
            for o in s.best:
                price = prices.get(o.name) if prices else None
                if price:
                    per = prices.per_divine(o.score, price)
                    note = f"  цена {prices.describe(price)}" + (f", {per:.0f} очков/div" if per else "")
                elif o.name.startswith("Legacy of"):
                    note = "  [руна из уникального предмета, цены нет]"
                else:
                    note = "  цены нет" if prices else ""
                print(f"      → {o.name}: {' / '.join(o.lines)}  {o.score:+.1f}  ({effect(o.changes)}){note}")
            if not s.best:
                print("      лучше текущей вставки ничего нет")


if __name__ == "__main__":
    main()
