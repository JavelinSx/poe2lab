"""Summary of a build plus a check against the stats PoB stored in the export code.

Stored stats come from whatever PoB version exported the code, so differences can mean
either a different PoB version or a headless problem - confirm in the GUI before trusting either.

Example: python scripts/inspect_build.py builds/titan.txt
"""
import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poe2lab.engine import PobEngine, decode_pob_code

KEY_STATS = [
    "Life", "EnergyShield", "Mana", "Spirit", "Armour", "Evasion", "DeflectChance",
    "FireResist", "ColdResist", "LightningResist", "ChaosResist",
    "EffectiveBlockChance", "PhysicalDamageReduction", "TotalEHP",
    "PhysicalMaximumHitTaken", "FireMaximumHitTaken", "ColdMaximumHitTaken",
    "LightningMaximumHitTaken", "ChaosMaximumHitTaken",
    "TotalDPS", "CombinedDPS", "AverageHit", "Speed", "CritChance", "CritMultiplier",
]


def stored_stats(xml: str) -> tuple[dict, dict]:
    build = ET.fromstring(xml).find("Build")
    stats = {}
    for ps in build.findall("PlayerStat"):
        try:
            stats[ps.get("stat")] = float(ps.get("value"))
        except (TypeError, ValueError):
            pass
    return dict(build.attrib), stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path)
    ap.add_argument("--group", type=int)
    ap.add_argument("--skill", type=int, default=1)
    args = ap.parse_args()

    code = args.build.resolve().read_text()
    attrs, stored = stored_stats(decode_pob_code(code))
    engine = PobEngine()
    engine.load_code(code)
    if args.group:
        engine.set_main_skill(args.group, args.skill)

    print(engine.info(), "| main skill:", engine.main_skill())
    print("export attrs:", {k: attrs.get(k) for k in ("targetVersion", "className", "ascendClassName", "level", "mainSocketGroup")})
    print("\nSocket groups:")
    for g in engine.socket_groups():
        mark = "*" if g["index"] == engine.info()["mainSocketGroup"] else " "
        print(f" {mark}{g['index']:>2} {'on ' if g['enabled'] else 'off'} {g['slot'] or '-':10} {', '.join(g['skills'])}")

    ours = engine.stats()
    print(f"\n{'stat':26} {'ours':>14} {'stored':>14}")
    for k in KEY_STATS:
        if k in ours or k in stored:
            o, s = ours.get(k), stored.get(k)
            flag = ""
            if o is not None and s is not None and abs(o - s) > max(abs(s) * 0.005, 0.5):
                flag = f"  <- {(o - s) / s * 100:+.1f}%" if s else "  <- differs"
            print(f"{k:26} {'-' if o is None else f'{o:,.1f}':>14} {'-' if s is None else f'{s:,.1f}':>14}{flag}")

    diffs = [k for k, s in stored.items() if k in ours and abs(ours[k] - s) > max(abs(s) * 0.005, 0.5)]
    missing = [k for k in stored if k not in ours]
    print(f"\n{len(stored)} stored stats: {len(stored) - len(diffs) - len(missing)} match, "
          f"{len(diffs)} differ >0.5%, {len(missing)} not in our output")
    if diffs:
        print("differing:", ", ".join(diffs))
    if missing:
        print("missing:", ", ".join(missing))


if __name__ == "__main__":
    main()
