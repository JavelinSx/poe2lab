"""Game texts in the player's language: .csd parsing, PoB-shaped Lua output, and PoB's describer reading it."""
import pytest

from poe2lab import gamedata
from poe2lab.engine import PobEngine

CSD = '''description
	1 active_skill_requires_X_glory
	1
		# "Supported Skills requires {0} [Glory] to use"
	lang "German"
	1
		# "Unterstutzte Fertigkeiten erfordern {0} [Glory|Ruhm]"
	lang "Russian"
	1
		# "Усиленные умения требуют {0} [Glory|Славы] для использования"

description
	1 base_skill_effect_duration
	2
		1000 "Duration is {0} second" milliseconds_to_seconds_2dp_if_required 1
		#|99 "Duration is {0} seconds" milliseconds_to_seconds_2dp_if_required 1
	lang "Russian"
	1
		# "Длительность - {0} секунд(-ы)" milliseconds_to_seconds_2dp_if_required 1

description
	1 only_english_stat
	1
		# "Only in English {0}"
no_description hidden_stat
'''


def test_parse_takes_the_language_block_and_falls_back_to_english():
    parsed = gamedata.parse_csd(CSD, "ru")
    glory, duration, english, hidden = parsed["entries"]
    assert glory["want"][0]["text"] == "Усиленные умения требуют {0} Славы для использования"
    assert duration["want"][0]["specs"] == [{"k": "milliseconds_to_seconds_2dp_if_required", "v": 1}]
    assert duration["en"][1]["limit"] == [["#", 99]]  # "#|99" limit, not swallowed as a quality word
    assert english["want"] is None and english["en"][0]["text"] == "Only in English {0}"
    assert hidden == {"stats": ["hidden_stat"]}
    assert parsed["index"]["only_english_stat"] == 3


@pytest.fixture(scope="module")
def engine():
    return PobEngine()


def test_pob_describer_speaks_the_generated_language(engine, tmp_path):
    lua = gamedata.to_lua(gamedata.parse_csd(CSD, "ru"))
    (tmp_path / "stat_descriptions.lua").write_text(lua, encoding="utf-8")
    assert engine._local_describer(tmp_path)
    got = engine._lua('''local ok, r = pcall(_poe2lab_localDescribe,
      { active_skill_requires_X_glory = 50, base_skill_effect_duration = 4000, only_english_stat = 3 },
      "stat_descriptions")
    return ok and table.concat(r, " | ") or tostring(r)''')
    assert got == ("Усиленные умения требуют 50 Славы для использования | Длительность - 4 секунд(-ы) | "
                   "Only in English 3")


@pytest.mark.skipif(not gamedata.available("ru"), reason="game texts not unpacked on this machine")
def test_unpacked_names_cover_item_granted_skills_and_areas():
    names = gamedata.load_names("ru")
    assert names["Walking Calamity"] == "Ходячее бедствие"
    assert names["Summon Wolf"] == "Призыв волка"
    assert names["Spires of Deshar"] == "Шпили Дешара"  # PoB drops the article: "The Spires of Deshar"


def test_game_is_found_in_any_steam_library(tmp_path, monkeypatch):
    lib = tmp_path / "SteamLibrary"
    (lib / "steamapps" / "common" / "Path of Exile 2" / "Bundles2").mkdir(parents=True)
    steam = tmp_path / "Steam"
    (steam / "steamapps").mkdir(parents=True)
    path = str(lib).replace("\\", "\\\\")
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"0"\n\t{{\n\t\t"path"\t\t"{path}"\n\t}}\n}}\n', encoding="utf-8")
    monkeypatch.delenv("POE2_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(gamedata, "STEAM_DIRS", [])
    monkeypatch.setattr(gamedata, "_steam_libraries", lambda: [lib])
    assert gamedata.find_game() == (lib / "steamapps" / "common" / "Path of Exile 2", "steam")


def test_chosen_game_folder_is_checked_and_remembered(tmp_path, monkeypatch):
    monkeypatch.delenv("POE2_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(gamedata, "STEAM_DIRS", [])
    monkeypatch.setattr(gamedata, "_steam_libraries", lambda: [])
    with pytest.raises(gamedata.GameDataError):
        gamedata.save_game_dir(tmp_path)  # no game files there
    game = tmp_path / "PoE2"
    (game / "Bundles2").mkdir(parents=True)
    gamedata.save_game_dir(game)
    assert gamedata.find_game() == (game, "settings")
    st = gamedata.status("ru")
    assert st["game"] == str(game) and st["gameSource"] == "settings"
