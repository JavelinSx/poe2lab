"""Compare a candidate item with the one you wear.

Save the current item to edit it:   python scripts/compare_item.py builds/titan.txt --slot "Weapon 1" --dump weapon.txt
Compare a candidate (game Ctrl+C):  python scripts/compare_item.py builds/titan.txt --group 4 --slot "Weapon 1" --item new.txt
Find how weak a line may be:        ... --item new.txt --breakeven "Adds 26 to 42 Physical Damage"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poe2lab.analysis.items import breakeven, compare
from poe2lab.analysis.threats import MapProfile
from poe2lab.engine import PobEngine

SHORT = {"Physical": "физ", "Fire": "огонь", "Cold": "холод", "Lightning": "молн", "Chaos": "хаос"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path)
    ap.add_argument("--slot", required=True, help='e.g. "Weapon 1", "Helmet", "Ring 1"')
    ap.add_argument("--group", type=int)
    ap.add_argument("--skill", type=int, default=1)
    ap.add_argument("--item", type=Path, help="candidate item text")
    ap.add_argument("--dump", type=Path, help="write the equipped item text here")
    ap.add_argument("--breakeven", help="a mod line of the candidate to shrink until it only ties the current item")
    ap.add_argument("--rage", type=int, help="current Rage in combat (default: maximum)")
    args = ap.parse_args()

    code = args.build.resolve().read_text()
    item_path = args.item.resolve() if args.item else None
    dump_path = args.dump.resolve() if args.dump else None
    engine = PobEngine()
    engine.load_code(code)
    if args.group:
        engine.set_main_skill(args.group, args.skill)

    if dump_path:
        dump_path.write_text(engine.item_text(args.slot), encoding="utf-8")
        print(f"current {args.slot} written to {dump_path}")
    if not item_path:
        return

    config = MapProfile(rage=args.rage).config()
    text = item_path.read_text(encoding="utf-8")
    c = compare(engine, config, args.slot, text)
    print(f"{args.slot}: кандидат против текущего (основной скилл {engine.main_skill()}, свирепость "
          f"{'максимум' if args.rage is None else args.rage})")
    print(f"  DPS {c.dps_pct:+.1f}%   жизнь {c.life_pct:+.1f}%   лечение {c.recovery_pct:+.1f}%")
    print("  переживаемый удар: " + "  ".join(f"{SHORT[t]} {v:+.1f}%" for t, v in c.hit_pct.items()))
    for attr, (have, need) in c.unmet_requirements.items():
        print(f"  [!!] с этим предметом не хватит {attr}: {have:.0f} из {need:.0f} — что-то перестанет работать")
    if args.breakeven:
        res = breakeven(engine, config, args.slot, text, args.breakeven)
        if res is None:
            print(f"  хуже текущего даже с полным «{args.breakeven}»")
        else:
            factor, line = res
            print(f"  не хуже текущего, пока «{args.breakeven}» не ниже «{line}» ({factor:.0%} от указанного)")


if __name__ == "__main__":
    main()
