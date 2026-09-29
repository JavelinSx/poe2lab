"""poe.ninja's ladder, read without the network: its dictionaries, a builds search answer, the interface's endpoints."""
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poe2lab import library, pobfiles, profile
from poe2lab.economy import ladder

H = {"X-Poe2lab": "1"}
CODE = (Path(__file__).resolve().parent / "fixtures" / "titan.txt").read_text(encoding="utf-8").strip()


def vint(x: int) -> bytes:
    out = bytearray()
    while True:
        b = x & 0x7F
        x >>= 7
        out.append(b | (0x80 if x else 0))
        if not x:
            return bytes(out)


def field(num: int, value) -> bytes:
    if isinstance(value, int):
        return vint(num << 3) + vint(value)
    value = value.encode() if isinstance(value, str) else value
    return vint(num << 3 | 2) + vint(len(value)) + value


def ndic(entries: list[str], table: bytes = b"") -> bytes:
    """A dictionary file as poe.ninja writes it: the magic, a header with the count at byte 12, the lengths, the text."""
    data = [e.encode() for e in entries]
    return (b"NDIC" + struct.pack("<Q", 2) + struct.pack("<I", len(data)) + b"\0" * 12 + table
            + b"".join(vint(len(d)) for d in data) + b"".join(data))


CLASSES = ["Deadeye", "Invoker", "Titan"]
GEMS = ["Comet", "Falling Thunder", "Spark"]


def search_answer() -> bytes:
    dim = field(1, "class") + field(2, "class") + field(3, field(2, 7)) + field(3, field(1, 1) + field(2, 233)) \
        + field(3, field(1, 2) + field(2, 60))
    col = lambda name, *parts: field(12, field(1, name) + field(2, name) + b"".join(parts))  # noqa: E731
    result = (field(1, 300) + field(2, dim)
              + field(6, field(1, "class") + field(2, "hash-class"))
              + field(6, field(1, "gem") + field(2, "hash-gem") + field(3, "other"))
              + col("name", field(7, "Aaeaala"), field(7, "Nimlotian"))
              + col("account", field(7, "aa-1"), field(7, "nim-2"))
              + col("class", field(6, vint(1) + vint(2)))
              + col("level", field(6, vint(98) + vint(97)))
              + col("dps.skill", field(6, vint(1) + vint(0)))
              + col("ehp__str", field(7, "98k"), field(7, "54k"))
              + col("dps.total", field(7, "646k"), field(7, "1.2M")))
    return field(1, result)


def test_a_dictionary_file():
    assert ladder.dictionary(ndic(CLASSES)) == CLASSES
    assert ladder.dictionary(ndic(GEMS, table=b"\x10\0\0\0\x05\0\0\0" * 3)) == GEMS  # a block table first
    with pytest.raises(ValueError):
        ladder.dictionary(b"XXXX")


def test_a_search_answer():
    names = {"hash-class": CLASSES, "hash-gem": GEMS}
    s = ladder.parse_search(search_answer(), names.__getitem__)
    assert s["total"] == 300 and s["ascendancies"] == {"Deadeye": 7, "Invoker": 233, "Titan": 60}
    assert s["characters"] == [
        {"name": "Aaeaala", "account": "aa-1", "level": 98, "class": "Invoker", "skill": "Falling Thunder", "life": 0,
         "es": 0, "ehp": "98k", "dps": "646k"},
        {"name": "Nimlotian", "account": "nim-2", "level": 97, "class": "Titan", "skill": "Comet", "life": 0,
         "es": 0, "ehp": "54k", "dps": "1.2M"}]


def test_a_character_s_page():
    snap = {"url": "forbiddenrites"}
    assert ladder.character_url(snap, "gucheng-0340", "孤城") == \
        "https://poe.ninja/poe2/builds/forbiddenrites/character/gucheng-0340/%E5%AD%A4%E5%9F%8E"


def test_the_interface_takes_a_ladder_build(tmp_path, monkeypatch):
    from poe2lab.web import server
    for module in (library, pobfiles, profile, server):
        if hasattr(module, "PROJECT_BUILDS"):
            monkeypatch.setattr(module, "PROJECT_BUILDS", tmp_path)
    monkeypatch.setattr(library, "TRASH", tmp_path / ".trash")
    names = {"hash-class": CLASSES, "hash-gem": GEMS}
    monkeypatch.setattr(ladder, "search", lambda asc=None, league=None: ladder.parse_search(search_answer(), names.__getitem__)
                        | {"league": "Forbidden Rites"})
    monkeypatch.setattr(ladder, "character_code", lambda account, name, league=None: CODE)
    with TestClient(server.app) as client:
        shares = client.get("/api/ladder/ascendancies").json()
        assert shares["total"] == 300 and shares["shares"]["Invoker"] == {"count": 233, "share": 233 / 300}
        top = client.get("/api/ladder/top?ascendancy=Invoker&limit=1").json()
        assert [c["name"] for c in top["characters"]] == ["Aaeaala"]
        b = client.post("/api/ladder/take", json={"account": "aa-1", "name": "Aaeaala", "skill": "Falling Thunder"},
                        headers=H).json()
        assert b["name"] == "Aaeaala (Falling Thunder)" and b["info"]["ascendancy"] == "Titan"  # the fixture's code
        assert b["profileRaw"]["constructor"]["from"] == {"account": "aa-1", "name": "Aaeaala"}
        again = client.post("/api/ladder/take", json={"account": "aa-1", "name": "Aaeaala", "skill": "Falling Thunder"},
                            headers=H).json()
        assert again["name"] == "Aaeaala (Falling Thunder) 2"  # a taken name gets a number
    server.session.engine = None
