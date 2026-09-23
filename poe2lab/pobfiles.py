"""Builds saved by Path of Building itself. Importing a character in PoB (its own official OAuth login) and
pressing Save writes an XML file there; commands accept that file or just its name, so no code copying is needed."""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# the player's own builds (not in git); POE2LAB_BUILDS points elsewhere, e.g. the tests' public fixtures
PROJECT_BUILDS = Path(os.environ.get("POE2LAB_BUILDS") or REPO_ROOT / "builds")


def pob_build_dirs() -> list[Path]:
    """Where PoB-PoE2 keeps saved builds: the bundled dev copy and the usual install locations."""
    home = Path(os.environ.get("USERPROFILE", Path.home()))
    candidates = [REPO_ROOT / "pob2" / "src" / "Builds"]
    for docs in (home / "Documents", home / "OneDrive" / "Documents", home / "OneDrive" / "Документы"):
        candidates.append(docs / "Path of Building (PoE2)" / "Builds")
    return [d for d in candidates if d.is_dir()]


def list_pob_builds() -> list[Path]:
    builds = [p for d in pob_build_dirs() for p in d.rglob("*.xml") if not p.stem.startswith("~~")]  # PoB temp files
    return sorted(builds, key=lambda p: p.stat().st_mtime, reverse=True)


def resolve_build(arg: str | Path) -> Path:
    """A path to a .txt code or .xml build, or the name of a build saved in PoB (without extension)."""
    path = Path(arg)
    if path.exists():
        return path.resolve()
    if path.suffix == "":
        for candidate in (PROJECT_BUILDS / f"{path.name}.txt", *(d / f"{path.name}.xml" for d in pob_build_dirs())):
            if candidate.exists():
                return candidate.resolve()
        for saved in list_pob_builds():
            if saved.stem.lower() == path.name.lower():
                return saved.resolve()
    raise FileNotFoundError(f"build not found: {arg} (see `python -m poe2lab builds` for PoB-saved builds)")
