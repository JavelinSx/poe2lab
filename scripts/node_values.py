"""How much DPS/EHP each allocated passive node contributes (removing it one at a time).

Example: python scripts/node_values.py builds/ma95.txt --group 2 --skill 2
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poe2lab.engine import EnginePool, PobEngine

SKIP_TYPES = {"ClassStart", "AscendClassStart"}


def pct(new, base):
    return (new - base) / base * 100 if base else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path)
    ap.add_argument("--group", type=int, help="socket group index of the main skill")
    ap.add_argument("--skill", type=int, default=1, help="active skill index inside the group")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--repeat", type=int, default=1, help="repeat the pass to benchmark throughput")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    code = args.build.resolve().read_text()
    main_skill = (args.group, args.skill) if args.group else None

    engine = PobEngine()
    engine.load_code(code)
    if main_skill:
        engine.set_main_skill(*main_skill)
    base = engine.stats()
    nodes = [n for n in engine.allocated_nodes() if n["type"] not in SKIP_TYPES]
    print(f"{engine.info()} | main skill: {engine.main_skill()}")
    print(f"base CombinedDPS {base['CombinedDPS']:,.0f} | TotalEHP {base['TotalEHP']:,.0f} | {len(nodes)} nodes")

    t0 = time.perf_counter()
    with EnginePool(code, workers=args.workers, main_skill=main_skill) as pool:
        t1 = time.perf_counter()
        calls = [{"remove_nodes": [n["id"]]} for n in nodes] * args.repeat
        results = pool.map("what_if", calls)[: len(nodes)]
        t2 = time.perf_counter()
    print(f"pool of {pool.workers} workers warm in {t1 - t0:.1f}s; "
          f"{len(calls)} what-if calls in {t2 - t1:.1f}s ({len(calls) / (t2 - t1):.0f}/s)")

    rows = [
        (n, pct(r["CombinedDPS"], base["CombinedDPS"]), pct(r["TotalEHP"], base["TotalEHP"]))
        for n, r in zip(nodes, results)
    ]
    for title, key in (("DPS", 1), ("EHP", 2)):
        print(f"\nTop {args.top} nodes by {title} lost when removed:")
        for n, d_dps, d_ehp in sorted(rows, key=lambda r: r[key])[: args.top]:
            print(f"  {n['name'][:40]:40} {n['type']:9} DPS {d_dps:+6.1f}%  EHP {d_ehp:+6.1f}%")
    useless = [r for r in rows if abs(r[1]) < 0.05 and abs(r[2]) < 0.05]
    print(f"\n{len(useless)} nodes change neither DPS nor EHP by >0.05% (pathing, utility or unmodelled effects)")


if __name__ == "__main__":
    main()
