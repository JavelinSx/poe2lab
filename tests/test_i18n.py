"""Official localized texts: template keys, number filling, line translation (offline, fixture dictionary)."""
import pytest
from fastapi.testclient import TestClient

from poe2lab import i18n
from poe2lab.i18n import fill, stat_key, translate_line

RU = {
    "stats": {
        "# to maximum life": "# к максимуму здоровья",
        "#% increased attack speed": "#% повышение скорости атаки",
        "adds # to # physical damage": "Добавляет от # до # физического урона",
        "#% to chaos resistance": "#% к сопротивлению хаосу",
    },
    "names": {"Furious Slam": "Яростный удар"},
}


def test_stat_key_ignores_numbers_signs_and_case():
    assert stat_key("+80 to maximum Life") == stat_key("# to maximum Life") == "# to maximum life"
    assert stat_key("+(24-27)% to Chaos Resistance") == "#% to chaos resistance"
    assert stat_key("Adds 26 to 42 Physical Damage") == "adds # to # physical damage"


def test_fill_keeps_numbers_in_order_and_signs():
    assert fill("# к максимуму здоровья", "+80 to maximum Life") == "+80 к максимуму здоровья"
    assert fill("Добавляет от # до # физического урона", "Adds 26 to 42 Physical Damage") == \
        "Добавляет от 26 до 42 физического урона"
    assert fill("+# к чему-то", "+5 to something") == "+5 к чему-то"
    assert fill("# и #", "only 1 number") == ""


def test_translate_line_and_hybrids():
    assert translate_line("24% increased Attack Speed", RU) == "24% повышение скорости атаки"
    assert translate_line("+30 to maximum Life / 8% increased Attack Speed", RU) == \
        "+30 к максимуму здоровья / 8% повышение скорости атаки"
    assert translate_line("+(24-27)% to Chaos Resistance", RU) == "+(24-27)% к сопротивлению хаосу"
    assert translate_line("Some unknown line", RU) is None


def test_i18n_endpoint_uses_dictionary(monkeypatch):
    from poe2lab.web import server
    monkeypatch.setattr(server, "translation_dictionary", lambda lang: RU)
    server._dictionaries.clear()
    with TestClient(server.app) as c:
        d = c.get("/api/i18n/ru").json()
        assert d["available"] and d["names"]["Furious Slam"] == "Яростный удар"
    server._dictionaries.clear()


def test_unsupported_language():
    with pytest.raises(ValueError):
        i18n.dictionary("xx")
