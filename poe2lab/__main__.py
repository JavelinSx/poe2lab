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
    from .profile import describe, open_build

    ap = argparse.ArgumentParser(prog="python -m poe2lab dossier")
    ap.add_argument("build", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--group", type=int, help="main skill socket group (default: from the build profile)")
    ap.add_argument("--skill", type=int)
    ap.add_argument("--no-corrections", action="store_true")
    ap.add_argument("--mode", default="balanced", choices=list(MODES))
    ap.add_argument("--rage", type=int)
    ap.add_argument("--league")
    ap.add_argument("--prices", action=argparse.BooleanOptionalAction, default=True)
    args = ap.parse_args(argv)

    out = args.out.resolve()
    engine, bp = open_build(args.build, args.group, args.skill, corrections=not args.no_corrections)
    prices = None
    if args.prices:
        try:
            prices = PriceBook.load(args.league or bp.league)
        except OSError as err:
            print(f"prices unavailable: {err}", file=sys.stderr)
    rage = args.rage if args.rage is not None else bp.rage
    data = build_dossier(engine, MapProfile(rage=rage, mana_sustained=bp.mana_sustained), args.mode, prices)
    data["buildProfile"] = describe(bp)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"dossier written to {out}")


def builds():
    """Builds saved inside Path of Building (after importing a character there and pressing Save)."""
    from datetime import datetime

    from .pobfiles import PROJECT_BUILDS, list_pob_builds, pob_build_dirs

    dirs = pob_build_dirs()
    print("PoB build folders: " + (", ".join(str(d) for d in dirs) or "none found"))
    for p in list_pob_builds():
        profile = "  (есть профиль)" if (PROJECT_BUILDS / f"{p.stem}.profile.json").exists() else ""
        print(f"  {datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d %H:%M}  {p.stem}{profile}")
    codes = sorted(PROJECT_BUILDS.glob("*.txt"))
    if codes:
        print("PoB codes in builds/: " + ", ".join(p.stem for p in codes))
    print('Use the name in any command, e.g. python -m poe2lab report "<name>"')


def ui(argv: list[str]):
    """Local web interface on http://127.0.0.1:<port>."""
    import threading
    import webbrowser

    import uvicorn

    ap = argparse.ArgumentParser(prog="python -m poe2lab ui")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    url = f"http://127.0.0.1:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"poe2lab UI: {url}  (Ctrl+C to stop)")
    uvicorn.run("poe2lab.web.server:app", host="127.0.0.1", port=args.port, log_level="warning")


def game_texts(rest):
    """Unpack official Russian texts from the installed game (re-run after a game patch; the UI also does it
    automatically when the game is newer than the unpacked copy)."""
    from . import gamedata
    ap = argparse.ArgumentParser(prog="python -m poe2lab gamedata", description=game_texts.__doc__)
    ap.add_argument("--game", type=Path, help="Path of Exile 2 folder (default: Steam / standalone install)")
    args = ap.parse_args(rest)
    try:
        info = gamedata.build("ru", args.game)
    except gamedata.GameDataError as err:
        sys.exit(str(err))
    print(f"{info['game']}: описаний статов {info['statFiles']}, названий {info['names']}, иконок {info['icons']}")


EXTRA = ("dossier", "builds", "ui", "gamedata")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in (*COMMANDS, *EXTRA):
        print("usage: python -m poe2lab {" + ",".join((*COMMANDS, *EXTRA)) + "} [args]  (-h after a command for help)")
        sys.exit(2)
    command, rest = sys.argv[1], sys.argv[2:]
    if command == "dossier":
        dossier(rest)
        return
    if command == "builds":
        builds()
        return
    if command == "ui":
        ui(rest)
        return
    if command == "gamedata":
        game_texts(rest)
        return
    script = SCRIPTS / COMMANDS[command]
    sys.argv = [str(script), *rest]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
