"""Opening Path of Building for a build update: which PoB, the build it opens on, and a running PoB left alone."""
from pathlib import Path

from poe2lab import pobapp

SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding2>
	<Mode mode="LIST">
		<Arg string="old"/>
	</Mode>
	<Accounts lastRefreshToken="keep-me" tokenExpiry="1"/>
	<Misc showWarnings="true"/>
</PathOfBuilding2>
"""


def fake_app(root: Path, bundled=False) -> pobapp.PobApp:
    (root / "Builds").mkdir(parents=True)
    exe = root / "PoB.exe"
    exe.write_bytes(b"")
    (root / "Settings.xml").write_text(SETTINGS, encoding="utf-8")
    return pobapp.PobApp(exe, root, bundled)


def test_the_build_decides_which_pob(tmp_path, monkeypatch):
    mine, bundled = fake_app(tmp_path / "installed"), fake_app(tmp_path / "bundled", bundled=True)
    monkeypatch.setattr(pobapp, "apps", lambda: [mine, bundled])
    build = bundled.builds_dir / "sub" / "x.xml"
    build.parent.mkdir()
    build.write_text("<PathOfBuilding2/>")
    assert pobapp.app_for(build) == bundled
    assert pobapp.app_for(tmp_path / "elsewhere.txt") == mine  # a code build: the player's own PoB first
    assert pobapp.app_for(None) == mine


def test_opens_on_the_build_and_keeps_the_rest_of_the_settings(tmp_path, monkeypatch):
    app = fake_app(tmp_path / "pob")
    build = app.builds_dir / "Мой билд.xml"
    build.write_text("<PathOfBuilding2/>", encoding="utf-8")
    started = []
    monkeypatch.setattr(pobapp, "apps", lambda: [app])
    monkeypatch.setattr(pobapp, "running", lambda: None)
    monkeypatch.setattr(pobapp.subprocess, "Popen", lambda args, **kw: started.append((args, kw["cwd"])))
    assert pobapp.open_pob(build) == {"state": "started", "bundled": False, "openedBuild": True}
    assert started == [([str(app.exe)], str(app.exe.parent))]
    text = (app.user_dir / "Settings.xml").read_text(encoding="utf-8")
    assert f'<Arg string="{build.resolve()}" />' in text and '<Arg string="Мой билд" />' in text
    assert 'mode="BUILD"' in text and 'lastRefreshToken="keep-me"' in text and 'showWarnings="true"' in text


def test_a_running_pob_is_not_restarted(monkeypatch):
    class Proc:
        pid = 42

    focused = []
    monkeypatch.setattr(pobapp, "running", lambda: Proc())
    monkeypatch.setattr(pobapp, "focus", focused.append)
    monkeypatch.setattr(pobapp.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("started")))
    assert pobapp.open_pob(None) == {"state": "running"} and focused == [42]


def test_no_pob_at_all(monkeypatch):
    monkeypatch.setattr(pobapp, "running", lambda: None)
    monkeypatch.setattr(pobapp, "apps", lambda: [])
    assert pobapp.open_pob(None) == {"state": "missing"}


def test_the_bundled_copy_is_found():
    assert any(a.bundled and a.exe.is_file() for a in pobapp.apps())
