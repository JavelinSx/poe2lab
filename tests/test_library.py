"""The UI's build list: adding from a PoB code, favourites first, removal to the trash, hiding PoB-saved builds."""
from pathlib import Path

import pytest

from poe2lab import library

ROOT = Path(__file__).resolve().parents[1]
CODE = (ROOT / "builds" / "titan.txt").read_text(encoding="utf-8").strip()


@pytest.fixture
def lib(tmp_path, monkeypatch):
    builds, pob = tmp_path / "builds", tmp_path / "pob"
    builds.mkdir()
    pob.mkdir()
    (pob / "Saved in PoB.xml").write_text("<PathOfBuilding2/>", encoding="utf-8")
    monkeypatch.setattr(library, "PROJECT_BUILDS", builds)
    monkeypatch.setattr(library, "TRASH", builds / ".trash")
    monkeypatch.setattr(library, "list_pob_builds", lambda: sorted(pob.glob("*.xml")))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    return builds


def test_add_names_from_the_code_and_refuses_duplicates(lib):
    name = library.add("", CODE)
    assert name == "Titan 77" and (lib / "Titan 77.txt").read_text(encoding="utf-8").strip() == CODE
    assert library.add("", CODE) == "Titan 77 (2)"
    with pytest.raises(library.LibraryError):
        library.add("titan 77", CODE)  # names are case-insensitive, like Windows file names
    with pytest.raises(library.LibraryError):
        library.add("../escape", CODE)
    with pytest.raises(library.LibraryError):
        library.add("x", "not a pob code")


def test_favourites_come_first(lib):
    library.add("a", CODE)
    library.add("b", CODE)
    library.set_favorite("b", True)
    assert [e["name"] for e in library.entries()] == ["b", "Saved in PoB", "a"]
    assert library.entries()[0]["favorite"]


def test_remove_moves_code_builds_to_trash_and_hides_pob_builds(lib):
    library.add("gone", CODE)
    (lib / "gone.profile.json").write_text("{}", encoding="utf-8")
    assert library.remove("gone") == "trashed"
    assert not (lib / "gone.txt").exists()
    assert sorted(p.name.split(" ", 1)[1] for p in (lib / ".trash").iterdir()) == ["gone.profile.json", "gone.txt"]

    assert library.remove("Saved in PoB") == "hidden"
    assert [e["name"] for e in library.entries()] == [] and library.hidden_count() == 1
    library.unhide_all()
    assert [e["name"] for e in library.entries()] == ["Saved in PoB"]
