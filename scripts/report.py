"""Build report: what must be fixed, where to invest for a goal, and a step-by-step upgrade path.

Example: python scripts/report.py builds/titan.txt --group 4 --mode balanced --json out.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poe2lab.analysis.report import MODES, build_report
from poe2lab.analysis.threats import DAMAGE_TYPES, MapProfile
from poe2lab.engine import PobEngine

LEVEL_MARK = {"must": "[!!]", "priority": "[! ]", "warn": "[ .]"}
SHORT = {"Physical": "физ", "Fire": "огонь", "Cold": "холод", "Lightning": "молн", "Chaos": "хаос"}
MODE_NAMES = {"damage": "урон", "balanced": "баланс", "defence": "защита"}


def defence_summary(values: dict, keys=("Physical", "Chaos")) -> str:
    return "  ".join(f"{SHORT[t]} {values[t]:+5.1f}%" for t in keys)


def print_report(r: dict):
    b, base = r["build"], r["baseline"]
    p = r["profile"]
    print(f"{b['class']} / {b['ascendancy']}, {b['level']} ур., основной скилл: {b['mainSkill']}")
    print(f"Цель: {MODE_NAMES[r['mode']]}. Враг: моб {p['enemy_level']} ур. (boss={p['boss']}), "
          f"сочная карта: +{p['damage_pct']:g}% урона и +{p['crit_bonus']:g}% бонуса крита монстров")
    print(f"Сейчас: DPS {base['dps']:,.0f}, жизнь {base['life']:,.0f}, попадание {base['hitChance']:.0f}%, "
          f"восстановление {base['recoveryPerSecond']:,.0f}/с")
    hits = base["survivableHit"]
    print("Переживаемый удар монстра (обычный / крит / крит на сочной): " + "; ".join(
        f"{SHORT[t]} {hits[t]['normal']:,.0f} / {hits[t]['crit']:,.0f} / {hits[t]['juiced']:,.0f}" for t in DAMAGE_TYPES))

    names = {"Str": "сила", "Dex": "ловкость", "Int": "интеллект"}
    a = r["attributes"]
    print("Атрибуты (есть / нужно / запас): " + "; ".join(
        f"{names[s['attr']]} {s['have']:.0f} / {s['need']:.0f} / {s['margin']:+.0f} "
        f"(нод в дереве: {s['from_nodes']})" for s in a["status"]))
    holders = [d for d in a["itemDependencies"]]
    if holders:
        print("Атрибуты с предметов: " + "; ".join(
            f"{d['slot']} " + ", ".join(f"+{v:.0f} {names[k]}" for k, v in d["provides"].items()) for d in holders))

    print("\n1. ОБЯЗАТЕЛЬНО И ГЛАВНЫЕ ДЫРЫ   [!!] не работает в игре  [! ] главная дыра  [ .] стоит учесть")
    order = {"must": 0, "priority": 1, "warn": 2}
    for g in sorted(r["gates"], key=lambda g: order[g["level"]]):
        print(f"  {LEVEL_MARK[g['level']]} {g['title']}: {g['detail']}")
    if not r["gates"]:
        print("  всё закрыто")
    for attr, lst in a["supportsAtRisk"].items():
        print(f"  В игре один из саппортов на {names[attr]} выключен, а PoB считает все включёнными. Потеря, если выключен:")
        for s in lst:
            cond = f"  (при условии: {'; '.join(s['conditions'])})" if s["conditions"] else ""
            print(f"      {s['name']:22} на {s['skill']:16} DPS этого скилла {s['skill_dps_pct']:+6.1f}%, "
                  f"основного {s['main_dps_pct']:+6.1f}%{cond}")

    print(f"\n2. КУДА ВКЛАДЫВАТЬСЯ (один мод ≈ один средний аффикс; цель — {MODE_NAMES[r['mode']]})")
    for x in r["ranking"]:
        print(f"  {x['mod']:52} DPS {x['dps']:+5.1f}%  физ-удар {x['physHit']:+5.1f}%  "
              f"хаос-удар {x['chaosHit']:+5.1f}%  лечение {x['recovery']:+5.1f}%")

    print("\n3. ПУТЬ АПГРЕЙДА (каждый шаг пересчитан с учётом предыдущих; каждый стат один раз)")
    if any(g["level"] == "must" for g in r["gates"]):
        print("  сначала закрой пункты [!!] — PoB считает их работающими, а в игре они выключены")
    for i, s in enumerate(r["path"], 1):
        print(f"  {i}. {s['mod']:50} шаг: DPS {s['dps']:+5.1f}%  {defence_summary(s['defence'])}  "
              f"лечение {s['recovery']:+5.1f}%")
    if r["path"]:
        last = r["path"][-1]
        print(f"  Итого: DPS {last['total_dps']:+.1f}%, переживаемый удар: {defence_summary(last['total_defence'], DAMAGE_TYPES)}, "
              f"лечение {last['total_recovery']:+.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path)
    ap.add_argument("--group", type=int)
    ap.add_argument("--skill", type=int, default=1)
    ap.add_argument("--mode", default="balanced", choices=list(MODES))
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--level", type=int, default=79)
    ap.add_argument("--boss", default="None", choices=["None", "Boss", "Pinnacle", "Uber"])
    ap.add_argument("--map-damage", type=float, default=50)
    ap.add_argument("--map-crit", type=float, default=50)
    ap.add_argument("--json", type=Path, help="also write the report as JSON")
    args = ap.parse_args()

    code = args.build.resolve().read_text()
    json_path = args.json.resolve() if args.json else None
    engine = PobEngine()
    engine.load_code(code)
    if args.group:
        engine.set_main_skill(args.group, args.skill)

    report = build_report(engine, MapProfile(args.level, args.boss, args.map_damage, args.map_crit),
                          mode=args.mode, steps=args.steps)
    print_report(report)
    if json_path:
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {json_path}")


if __name__ == "__main__":
    main()
