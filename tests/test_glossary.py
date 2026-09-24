"""The beginner's glossary: our own words for the game's key terms, linked to each other, used by the popups."""
import re

from fastapi.testclient import TestClient

from poe2lab import glossary, keywords
from poe2lab.web.server import app

LINK = re.compile(r"\[([^|\]]+)")


def test_every_entry_has_both_languages_and_links_that_resolve():
    for lang in ("ru", "en"):
        terms = glossary.entries(lang)
        for kid, k in terms.items():
            assert k["nameLocal"] and k["textLocal"] and k["source"] == "poe2lab"
            assert set(LINK.findall(k["textLocal"])) <= set(terms), kid


def test_chill_and_freeze_explain_each_other():
    ru = glossary.entries("ru")
    assert "Freeze" in LINK.findall(ru["Chill"]["textLocal"]) and "Chill" in LINK.findall(ru["ElementalColdChain"]["textLocal"])
    assert "PrimedFreeze" in LINK.findall(ru["Freeze"]["textLocal"])


def test_the_popups_use_our_words_where_we_have_them():
    found = keywords.entries(["Freeze"], "ru")
    assert found["Freeze"]["source"] == "poe2lab" and "AilmentThreshold" in found  # linked terms come along


def test_every_group_is_listed_on_the_page():
    groups = glossary.groups("ru")
    assert [g["key"] for g in groups] == [g for g, _ in glossary.GROUPS]
    assert sum(len(g["ids"]) for g in groups) == len(glossary.ENTRIES)
    with TestClient(app) as c:
        r = c.get("/api/glossary?lang=en").json()
        assert r["groups"][0]["name"] == "Damage: how it adds up" and r["terms"]["Freeze"]["nameLocal"] == "Freeze"
