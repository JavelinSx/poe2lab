"""The build author's layer over poe2lab's own picture. Every tab shows what poe2lab worked out; the author changes
it: a note under any block, a list of its own instead of the automatic one. Game things are written into the text
as tokens - [[gem:Ice Strike]], [[unique:Astramentis]], [[passive:12345|Flow Like Water]] - picked from one search
over everything the game has (gems, uniques, item bases, runes, passives, the glossary's terms), and the page shows
each with its picture and its card on hover.

The blocks live in the build's profile under "author": {"v": 1, "blocks": {block id: {"text": str, "list": [token]}}}.
A block id names the tab's block: "ov:about", "lv:act1:skills", "sk:Ice Strike", "gear:Body Armour", "tree:about"."""
import re

KINDS = ("gem", "support", "unique", "base", "rune", "passive", "term")
# a token in a text: [[kind:id]]; a passive's id is its node id with its name after "|"
TOKEN = re.compile(r"\[\[(" + "|".join(KINDS) + r"):([^\[\]\n]{1,200})\]\]")
# a list's item: kind:id
ITEM = re.compile(r"^(" + "|".join(KINDS) + r"):([^\[\]\n]{1,200})$")
BLOCK_ID = re.compile(r"^[a-z]{2,6}:[^\n\[\]]{1,160}$")
MAX_TEXT = 8000
MAX_LIST = 40
MAX_BLOCKS = 800
# what a search shows first when nothing tells the kinds apart: skills before supports before items...
ORDER = {k: i for i, k in enumerate(KINDS)}
# PoB's passive node types worth a search: the small ones repeat ("Strength") and are no help in a text
PASSIVE_TYPES = ("Notable", "Keystone", "Socket")


class AuthorError(ValueError):
    pass


def normalize(s: str) -> str:
    return " ".join((s or "").lower().replace("ё", "е").split())


def tokens(text: str) -> list[tuple[str, str]]:
    return TOKEN.findall(text or "")


def clean_block(block: dict) -> dict:
    """A block as the page sends it, checked: a text up to MAX_TEXT, a list of up to MAX_LIST items in the token
    form; anything else is refused (the file stays readable by the next version)."""
    if not isinstance(block, dict):
        raise AuthorError("блок — не объект")
    out = {}
    text = block.get("text")
    if text is not None:
        if not isinstance(text, str):
            raise AuthorError("текст блока — не строка")
        text = text.replace("\r\n", "\n").strip()
        if len(text) > MAX_TEXT:
            raise AuthorError(f"текст длиннее {MAX_TEXT} знаков")
        if text:
            out["text"] = text
    items = block.get("list")
    if items is not None:
        if not isinstance(items, list) or len(items) > MAX_LIST:
            raise AuthorError(f"список — не больше {MAX_LIST} элементов")
        bad = [x for x in items if not isinstance(x, str) or not ITEM.match(x)]
        if bad:
            raise AuthorError(f"не элемент игры: {bad[0]!r}")
        out["list"] = list(dict.fromkeys(items))  # each once, in the author's order
    return out


def set_block(doc: dict | None, block_id: str, block: dict) -> dict:
    """The author's document with one block set (an empty one removed)."""
    if not isinstance(block_id, str) or not BLOCK_ID.match(block_id):
        raise AuthorError(f"неизвестный блок {block_id!r}")
    doc = {"v": 1, "blocks": dict((doc or {}).get("blocks") or {})}
    clean = clean_block(block)
    if clean:
        doc["blocks"][block_id] = clean
    else:
        doc["blocks"].pop(block_id, None)
    if len(doc["blocks"]) > MAX_BLOCKS:
        raise AuthorError(f"блоков больше {MAX_BLOCKS}")
    return doc


def build_index(gems: list[dict], uniques: list[dict], bases: list[dict], runes: list[dict], nodes: list[dict],
                terms: dict, names: dict) -> list[dict]:
    """Everything a token can be, with its English and local names for the search. `names`: English -> local."""
    out, seen = [], set()

    def add(kind, id_, en, sub="", local=None, **extra):
        if not en or (kind, id_) in seen:
            return
        seen.add((kind, id_))
        local = (names or {}).get(en, "") if local is None else local
        out.append({"kind": kind, "id": id_, "en": en, "local": local if local != en else "", "sub": sub,
                    "keys": [normalize(en)] + ([normalize(local)] if local and local != en else []), **extra})

    for g in gems:
        add("support" if g.get("support") else "gem", g["name"], g["name"])
    for u in uniques:
        add("unique", u["name"], u["name"], u.get("base", ""), base=u.get("base", ""))
    for b in bases:
        if not b.get("hidden"):
            add("base", b["name"], b["name"], b.get("type", ""))
    for r in runes:
        add("rune", r["name"], r["name"])
    for n in nodes:
        if n.get("type") in PASSIVE_TYPES and n.get("name"):
            sub = n.get("asc") or n["type"]
            add("passive", f"{n['id']}|{n['name']}", n["name"], sub, img=n.get("img", ""))
    named = set()  # the glossary's aliases point at one entry: it is found once
    for kid, e in (terms or {}).items():
        if e.get("name") not in named:
            named.add(e.get("name"))
            add("term", kid, e.get("name", ""), "", local=e.get("nameLocal", ""))
    return out


def search(index: list[dict], query: str, kinds: list[str] | None = None, limit: int = 30) -> list[dict]:
    """The index's entries every word of the query is in (English or local name), the closest first: the whole
    name, its start, a word's start, anywhere."""
    words = normalize(query).split()
    if not words:
        return []
    want = set(kinds or KINDS)
    scored = []
    for e in index:
        if e["kind"] not in want:
            continue
        best = None
        for key in e["keys"]:
            if not all(w in key for w in words):
                continue
            phrase = " ".join(words)
            rank = 0 if key == phrase else 1 if key.startswith(phrase) else \
                2 if all(re.search(r"(^|[\s\-'(])" + re.escape(w), key) for w in words) else 3
            best = rank if best is None else min(best, rank)
        if best is not None:
            scored.append((best, ORDER[e["kind"]], len(e["en"]), e["en"], e))
    scored.sort(key=lambda x: x[:4])
    return [{k: v for k, v in x[4].items() if k != "keys"} for x in scored[:limit]]
