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
from poe2lab.profile import describe, open_build

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

    core = r["core"]
    print("\nЯДРО УРОНА")
    res_names = {"Rage": "Свирепость", "Power Charges": "Заряды энергии", "Frenzy Charges": "Заряды ярости",
                 "Endurance Charges": "Заряды выносливости"}
    for res in core["resources"]:
        state = f"считаю {res['assumed']:.0f} из {res['maximum']:.0f}" if res["counted"] else "не учитываются в билде"
        ehp = ""
        if res["ehp_without"] and abs(res["ehp_with"] / res["ehp_without"] - 1) >= 0.005:
            ehp = f"; EHP {res['ehp_without']:,.0f} → {res['ehp_with']:,.0f}"
        print(f"  {res_names.get(res['name'], res['name'])}: {state}. DPS без них {res['dps_without']:,.0f}, "
              f"с ними {res['dps_with']:,.0f} (×{res['dps_with'] / res['dps_without']:.2f}){ehp}")
    if core["unit"]:
        u = core["unit"]
        print(f"  Курс в единицах «{u['name']}» (1 ед. = {u['dps_pct_per_point']:+.2f}% DPS):")
        for x in core["exchange"][:10]:
            print(f"    {x['mod']:48} DPS {x['dps']:+5.1f}%  ≈ {x['points']:.1f} ед.")

    def effect(c):
        parts = [(c["dps_pct"], "DPS"), (c["phys_hit_pct"], "физ-удар"), (c["chaos_hit_pct"], "хаос-удар"),
                 (c["ele_hit_pct"], "элем-удар"), (c["recovery_pct"], "лечение"), (c["life_pct"], "жизнь")]
        return ", ".join(f"{name} {v:+.1f}%" for v, name in parts if abs(v) >= 0.5)

    if r["notModelled"]:
        print("\nЧТО PoB НЕ СЧИТАЕТ (стат/строка есть в данных игры, но в расчёт не попадает):")
        for g in r["notModelled"]:
            print(f"  {g['where']}: {g['text']}")
        print("  Важное из этого стоит учесть поправкой в профиле билда (builds/<имя>.profile.json).")

    rng = r["damageRange"]
    if rng["conditions"]:
        print(f"\nВИЛКА УРОНА: {rng['low']:,.0f} (враг без дебаффов) … {rng['high']:,.0f} "
              f"(×{rng['high'] / rng['low']:.2f}, если одновременно: {', '.join(rng['conditions'])})")
        print("  Реальный урон между ними — зависит от того, как часто эти состояния висят на врагах.")

    off = [c for c in r["conditions"] if not c["checked"]]
    on = [c for c in r["conditions"] if c["checked"]]
    print("\nУСЛОВИЯ ВО ВКЛАДКЕ CONFIGURATION (PoB считает их так, как отмечено)")
    if off:
        print("  Выключены — если в игре это обычно правда, PoB недооценивает билд:")
        for c in off:
            print(f"    [ ] {c['label']:42} {effect(c)}")
    if on:
        print("  Включены — PoB считает выполненными, проверь, что так и в игре (цена, если нет):")
        for c in on:
            print(f"    [x] {c['label']:42} {effect(c)}")

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
    ap.add_argument("--group", type=int, help="main skill socket group (default: from the build profile)")
    ap.add_argument("--skill", type=int)
    ap.add_argument("--no-corrections", action="store_true", help="ignore the profile's corrections for PoB gaps")
    ap.add_argument("--mode", default="balanced", choices=list(MODES))
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--level", type=int, default=79)
    ap.add_argument("--boss", default="None", choices=["None", "Boss", "Pinnacle", "Uber"])
    ap.add_argument("--map-damage", type=float, default=50)
    ap.add_argument("--map-crit", type=float, default=50)
    ap.add_argument("--rage", type=int, help="current Rage in combat (default: maximum)")
    ap.add_argument("--json", type=Path, help="also write the report as JSON")
    args = ap.parse_args()

    json_path = args.json.resolve() if args.json else None
    engine, bp = open_build(args.build, args.group, args.skill, corrections=not args.no_corrections)
    rage = args.rage if args.rage is not None else bp.rage
    profile = MapProfile(args.level, args.boss, args.map_damage, args.map_crit, rage, bp.mana_sustained)

    report = build_report(engine, profile, mode=args.mode, steps=args.steps)
    for line in describe(bp):
        print(f"[профиль] {line}")
    print_report(report)
    if json_path:
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {json_path}")


if __name__ == "__main__":
    main()
