"""Single entry point: python -m poe2lab <command> [args]. Each command is one of the scripts in scripts/,
plus `dossier`, which writes the whole analysis as one JSON file."""
import argparse
import json
import runpy
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
COMMANDS = {
    "report": "report.py",
    "slots": "slots.py",
    "threats": "threats.py",
    "compare": "compare_item.py",
    "inspect": "inspect_build.py",
    "gradients": "gradients.py",
    "nodes": "node_values.py",
}


def dossier(argv: list[str]):
    from .analysis.report import MODES
    from .analysis.threats import MapProfile
    from .economy.ninja import PriceBook
    from .dossier import build_dossier
    from .engine import PobEngine

    ap = argparse.ArgumentParser(prog="python -m poe2lab dossier")
    ap.add_argument("build", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--group", type=int)
    ap.add_argument("--skill", type=int, default=1)
    ap.add_argument("--mode", default="balanced", choices=list(MODES))
    ap.add_argument("--rage", type=int)
    ap.add_argument("--league")
    ap.add_argument("--prices", action=argparse.BooleanOptionalAction, default=True)
    args = ap.parse_args(argv)

    code, out = args.build.resolve().read_text(), args.out.resolve()
    prices = None
    if args.prices:
        try:
            prices = PriceBook.load(args.league)
        except OSError as err:
            print(f"prices unavailable: {err}", file=sys.stderr)
    engine = PobEngine()
    engine.load_code(code)
    if args.group:
        engine.set_main_skill(args.group, args.skill)
    data = build_dossier(engine, MapProfile(rage=args.rage), args.mode, prices)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"dossier written to {out}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in (*COMMANDS, "dossier"):
        print("usage: python -m poe2lab {" + ",".join((*COMMANDS, "dossier")) + "} [args]  (-h after a command for help)")
        sys.exit(2)
    command, rest = sys.argv[1], sys.argv[2:]
    if command == "dossier":
        dossier(rest)
        return
    script = SCRIPTS / COMMANDS[command]
    sys.argv = [str(script), *rest]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
