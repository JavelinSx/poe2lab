"""One-click setup: the PoB archive downloaded without git must be the same commit as the pob2 submodule."""
import subprocess

import pytest

from poe2lab.engine.luahost import DEFAULT_POB_ROOT, POB_COMMIT


def test_pinned_pob_commit_matches_the_submodule():
    try:
        head = subprocess.run(["git", "-C", str(DEFAULT_POB_ROOT), "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip()
    except OSError:
        pytest.skip("no git")
    if not head:
        pytest.skip("pob2 is not a git checkout (downloaded archive)")
    assert head == POB_COMMIT, "update POB_COMMIT in poe2lab/engine/luahost.py after moving the submodule"


def test_every_module_compiles():
    """start.bat runs `python -m poe2lab`: a syntax error in any module (e.g. __main__) breaks it for everyone."""
    import py_compile
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "poe2lab"
    for path in root.rglob("*.py"):
        py_compile.compile(str(path), doraise=True)
