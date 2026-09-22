"""Map survival report: what hits you survive, how fast you recover, and which mods fix the weak spots.

Example: python scripts/threats.py builds/titan.txt --group 4 --map-damage 50 --map-crit 50
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poe2lab.analysis.gradients import compute
from poe2lab.analysis.stats import mod_line
from poe2lab.analysis.threats import MapProfile, recovery, survivable_hits
from poe2lab.profile import open_build

FIXES = [
    ("phys_hit", "Physical max hit", "Physical"),
    ("chaos_hit", "Chaos max hit", "Chaos"),
    ("recovery", "Life recovery per second", None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path)
    ap.add_argument("--group", type=int, help="main skill socket group (default: from the build profile)")
    ap.add_argument("--skill", type=int)
    ap.add_argument("--no-corrections", action="store_true", help="ignore the profile's corrections for PoB gaps")
    ap.add_argument("--level", type=int, default=79, help="monster level (T15 waystone = 79)")
    ap.add_argument("--boss", default="None", choices=["None", "Boss", "Pinnacle", "Uber"])
    ap.add_argument("--map-damage", type=float, default=50, help="monsters' increased damage from map/juice, %%")
    ap.add_argument("--map-crit", type=float, default=50, help="extra monster critical damage bonus from map/juice, %%")
    ap.add_argument("--top", type=int, default=6)
    args = ap.parse_args()

    engine, bp = open_build(args.build, args.group, args.skill, corrections=not args.no_corrections)
    profile = MapProfile(args.level, args.boss, args.map_damage, args.map_crit, bp.rage, bp.mana_sustained)

    print(f"{engine.info()} | main skill: {engine.main_skill()}")
    print(f"enemy: level {profile.enemy_level}, boss={profile.boss}; juiced map = +{profile.damage_pct:g}% monster damage, "
          f"+{profile.crit_bonus:g}% monster crit bonus (example values - set them from your waystone mods)")

    rows = survivable_hits(engine, profile)
    best = max(r.normal for r in rows)
    print("\nLARGEST MONSTER HIT YOU SURVIVE FROM FULL LIFE (monster damage before map mods)")
    print(f"  {'type':10} {'normal':>9} {'crit':>9} {'juiced crit':>12}   vs your best type")
    for r in rows:
        print(f"  {r.damage_type:10} {r.normal:9,.0f} {r.crit:9,.0f} {r.juiced:12,.0f}   {r.normal / best * 100:5.0f}%")

    rec = recovery(engine, profile)
    print(f"\nLIFE RECOVERY WHILE ATTACKING: {rec.total:,.0f}/s = leech+on-hit {rec.leech:,.0f} + regen {rec.regen:,.0f}"
          f" + recoup {rec.recoup:,.0f}  (life {rec.life:,.0f}; half of it back in {rec.half_life_refill_seconds:.1f}s)")
    if rec.leech_capped_per_hit:
        print("  leech per hit is at its cap - more '% leeched' does nothing; recovery rate, more life, faster hits do")

    _, grads = compute(engine, config=profile.config())
    for metric, title, _ in FIXES:
        ranked = sorted((g for g in grads if g.one[metric] >= 0.5), key=lambda g: -g.one[metric])[: args.top]
        print(f"\nBEST MODS FOR: {title}")
        for g in ranked:
            print(f"  {mod_line(g.stat):52} {g.one[metric]:+6.1f}%   (DPS {g.one['dps']:+.1f}%)")
        if not ranked:
            print("  nothing in the probed stat list helps")


if __name__ == "__main__":
    main()
