"""Which stats are worth the most for a build right now.

Example: python scripts/gradients.py builds/titan.txt --group 4
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poe2lab.analysis.gradients import compute
from poe2lab.analysis.stats import mod_line
from poe2lab.engine import PobEngine


def sat_label(s):
    if s is None:
        return ""
    if s < 0.1:
        return "capped"
    if s < 0.8:
        return f"diminishing ({s:.2f})"
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path)
    ap.add_argument("--group", type=int)
    ap.add_argument("--skill", type=int, default=1)
    args = ap.parse_args()

    code = args.build.resolve().read_text()
    engine = PobEngine()
    engine.load_code(code)
    if args.group:
        engine.set_main_skill(args.group, args.skill)

    t = time.perf_counter()
    base, grads = compute(engine)
    print(f"{engine.info()} | main skill: {engine.main_skill()} | {len(grads) * 2 + 1} calcs in {time.perf_counter() - t:.1f}s")
    print(f"base: DPS {base['CombinedDPS']:,.0f} | EHP {base['TotalEHP']:,.0f} | Life {base['Life']:,.0f} | "
          f"max hit phys {base['PhysicalMaximumHitTaken']:,.0f} / fire {base['FireMaximumHitTaken']:,.0f} / "
          f"cold {base['ColdMaximumHitTaken']:,.0f} / light {base['LightningMaximumHitTaken']:,.0f} / "
          f"chaos {base['ChaosMaximumHitTaken']:,.0f}")

    print("\nDAMAGE - value of one mod (sorted by DPS gain)")
    for g in sorted(grads, key=lambda g: -g.one["dps"]):
        if abs(g.one["dps"]) < 0.05:
            continue
        print(f"  {mod_line(g.stat):48} DPS {g.one['dps']:+6.1f}%  {sat_label(g.saturation('dps'))}")

    print("\nDEFENCE - value of one mod (sorted by EHP gain)")
    for g in sorted(grads, key=lambda g: -g.one["ehp"]):
        if abs(g.one["ehp"]) < 0.05 and abs(g.one["phys_hit"]) < 0.05:
            continue
        print(f"  {mod_line(g.stat):48} EHP {g.one['ehp']:+6.1f}%  phys hit {g.one['phys_hit']:+6.1f}%  "
              f"chaos hit {g.one['chaos_hit']:+6.1f}%  {sat_label(g.saturation('ehp'))}")

    dead = [g for g in grads if all(abs(v) < 0.05 for v in g.one.values())]
    print(f"\nNo effect for this build ({len(dead)}): " + ", ".join(g.stat.label for g in dead))


if __name__ == "__main__":
    main()
