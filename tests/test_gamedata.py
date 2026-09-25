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


def test_templates_follow_the_translation_s_own_order_of_numbers():
    """The Russian text may reorder the numbers, leave a fixed one out ("200% of Armour" -> "удвоенной броней") or
    keep its own: '#{i}' names the English line's i-th number."""
    from poe2lab.i18n import fill
    same = gamedata._template("{0}% increased Damage", "{0}% увеличение урона")
    assert same == "#% увеличение урона"
    left_out = gamedata._template("{0}% chance to Defend with 200% of Armour", "{0}% шанс на защиту с удвоенной броней")
    assert left_out == "#{0}% шанс на защиту с удвоенной броней"
    assert fill(left_out, "10% chance to Defend with 200% of Armour") == "10% шанс на защиту с удвоенной броней"
    swapped = gamedata._template("{0} to {1} Fire Damage for {2} seconds", "На {2} с: от {0} до {1} урона от огня")
    assert fill(swapped, "3 to 7 Fire Damage for 4 seconds") == "На 4 с: от 3 до 7 урона от огня"
    assert gamedata._template("{0}% of Damage", "{0}% урона за {1} с") is None  # a value the line does not print


def test_slips_in_the_game_s_translation_are_put_right():
    text = ('description\n1 some_stat\n1\n# "you and Allies in your Presence gain {0}"\nlang "Russian"\n1\n'
            '# "вы и союзники in your присутствии получают {0}"\n')
    parsed = gamedata.parse_csd(text, "ru")
    assert parsed["entries"][0]["want"][0]["text"] == "вы и союзники в вашем присутствии получают {0}"
