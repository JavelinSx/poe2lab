"""The build author's layer over poe2lab's own picture. Every tab shows what poe2lab worked out; the author changes
it: a note under any block, a list of its own instead of the automatic one. Game things are written into the text
as tokens - [[gem:Ice Strike]], [[unique:Astramentis]], [[passive:12345|Flow Like Water]] - picked from one search
over everything the game has (gems, uniques, item bases, runes, passives, the glossary's terms) by name or by what
it is (its tags: "атака удар посох"), and the page shows each with its picture and its card on hover.

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
MAX_TIP = 1000  # a hover tip is short: a line or two over the element
MAX_LABEL = 60  # the author's own label of a note ("Важно", "Механика", "Откуда урон")
MAX_LIST = 40
MAX_BLOCKS = 800
# what a search shows first when nothing tells the kinds apart: skills before supports before items...
ORDER = {k: i for i, k in enumerate(KINDS)}
# PoB's passive node types worth a search: the small ones repeat ("Strength") and are no help in a text
PASSIVE_TYPES = ("Notable", "Keystone", "Socket")

# What a thing is, besides its name, for the search - "атака удар посох" finds Ice Strike. A gem's tags (PoB's gem
# data) as the game names them in English and in the Russian client, with other words players use:
# tag -> (shown in English, shown in Russian, more words it is found by, each a word of its own)
GEM_TAGS = {
    "attack": ("attack", "атака", ""), "spell": ("spell", "чары", "заклинание"), "melee": ("melee", "ближний бой", ""),
    "strike": ("strike", "удар", ""), "slam": ("slam", "могучий удар", ""), "area": ("AoE", "область", "aoe"),
    "projectile": ("projectile", "снаряд", ""), "duration": ("duration", "длительность", ""),
    "physical": ("physical", "физический", "физ"), "fire": ("fire", "огонь", "огненный"),
    "cold": ("cold", "холод", "ледяной лед"), "lightning": ("lightning", "молния", "электричество"),
    "chaos": ("chaos", "хаос", ""), "minion": ("minion", "приспешник", "миньон призыв"),
    "buff": ("buff", "бафф", "усиление"), "persistent": ("persistent", "постоянный", "резерв дух"),
    "trigger": ("trigger", "срабатывание", "триггер"), "totem": ("totem", "тотем", ""),
    "curse": ("curse", "проклятие", "проклятье"), "aura": ("aura", "аура", ""), "warcry": ("warcry", "боевой клич", "клич"),
    "herald": ("herald", "вестник", ""), "mark": ("mark", "метка", ""), "nova": ("nova", "кольцо", "нова"),
    "channelling": ("channelling", "поддержание", "канал"), "meta": ("meta", "мета", ""),
    "grenade": ("grenade", "граната", ""), "ammunition": ("ammunition", "боеприпасы", "болты"),
    "shapeshift": ("shapeshift", "превращение", "форма"), "companion": ("companion", "компаньон", "спутник питомец"),
    "travel": ("travel", "перемещение", "движение"), "chaining": ("chaining", "цепь", "отскок"),
    "remnant": ("remnant", "остаток", ""), "storm": ("storm", "буря", "шторм"), "orb": ("orb", "сфера", ""),
    "invocation": ("invocation", "воззвание", ""), "detonator": ("detonator", "детонатор", "подрыв взрыв"),
    "hazard": ("hazard", "опасность", "ловушка"), "plant": ("plant", "растение", ""), "stages": ("stages", "этапы", "стадии"),
    "wind": ("wind", "ветер", ""), "command": ("command", "команда", ""), "bear": ("bear", "медведь", ""),
    "wyvern": ("wyvern", "виверна", ""), "wolf": ("wolf", "волк", "оборотень"), "merging": ("merging", "слияние", ""),
    "banner": ("banner", "знамя", ""), "repeatable": ("repeatable", "повторяемый", ""),
    "lineage": ("lineage", "родословная", ""), "sustained": ("sustained", "длительное действие", ""),
    "payoff": ("payoff", "завершение", ""), "conditional": ("conditional", "условие", ""),
    "support": ("support", "поддержка", "саппорт"),
}
# a gem's weapon (PoB's weapon types)
WEAPONS = {
    "Staff": ("quarterstaff", "боевой посох", "посох"), "Bow": ("bow", "лук", ""), "Crossbow": ("crossbow", "арбалет", ""),
    "Spear": ("spear", "копьё", "копье"), "One Handed Mace": ("one hand mace", "одноручная булава", "булава"),
    "Two Handed Mace": ("two hand mace", "двуручная булава", "булава"), "Talisman": ("talisman", "талисман", ""),
    "Claw": ("claw", "когти", ""), "Dagger": ("dagger", "кинжал", ""), "Wand": ("wand", "жезл", ""),
    "Sceptre": ("sceptre", "скипетр", ""), "One Handed Sword": ("one hand sword", "одноручный меч", "меч"),
    "Two Handed Sword": ("two hand sword", "двуручный меч", "меч"),
    "One Handed Axe": ("one hand axe", "одноручный топор", "топор"),
    "Two Handed Axe": ("two hand axe", "двуручный топор", "топор"), "Flail": ("flail", "цеп", ""),
    "Shield": ("shield", "щит", ""), "Buckler": ("buckler", "баклер", "щит"), "None": ("unarmed", "без оружия", "кулаки"),
}
# an item's kind
ITEM_TYPES = {
    "Staff": ("quarterstaff", "боевой посох", "посох"), "Ring": ("ring", "кольцо", ""), "Amulet": ("amulet", "амулет", ""),
    "Belt": ("belt", "пояс", ""), "Body Armour": ("body armour", "нательная броня", "доспех броня"),
    "Helmet": ("helmet", "шлем", ""), "Gloves": ("gloves", "перчатки", ""), "Boots": ("boots", "сапоги", "ботинки обувь"),
    "Shield": ("shield", "щит", ""), "Focus": ("focus", "фокус", ""), "Quiver": ("quiver", "колчан", ""),
    "Bow": ("bow", "лук", ""), "Crossbow": ("crossbow", "арбалет", ""), "Spear": ("spear", "копьё", "копье"),
    "One Hand Mace": ("one hand mace", "одноручная булава", "булава"),
    "Two Hand Mace": ("two hand mace", "двуручная булава", "булава"), "Sceptre": ("sceptre", "скипетр", ""),
    "Wand": ("wand", "жезл", ""), "Talisman": ("talisman", "талисман", ""), "Jewel": ("jewel", "самоцвет", ""),
    "Flask": ("flask", "флакон", "колба"), "Charm": ("charm", "оберег", ""), "Claw": ("claw", "когти", ""),
    "Dagger": ("dagger", "кинжал", ""), "One Hand Sword": ("one hand sword", "одноручный меч", "меч"),
    "Two Hand Sword": ("two hand sword", "двуручный меч", "меч"), "One Hand Axe": ("one hand axe", "одноручный топор", "топор"),
    "Two Hand Axe": ("two hand axe", "двуручный топор", "топор"), "Flail": ("flail", "цеп", ""),
    "TrapTool": ("trap tool", "ловушка", ""),
}
# what an item's, a rune's or a passive's lines are about, by the English words in them (a Russian name of more than
# one word is kept whole when it is one name; otherwise its first word is shown and the rest are synonyms)
KEEP = {"ближний бой", "скорость атаки", "скорость сотворения", "скорость передвижения", "могучий удар",
        "энергетический щит"}
LINE_WORDS = [(re.compile(rx, re.I), en, ru.split()[0] if len(ru.split()) > 1 and ru not in KEEP else ru,
               " ".join(ru.split()[1:]) if len(ru.split()) > 1 and ru not in KEEP else "") for rx, en, ru in (
    (r"\bcold\b|freez|chill", "cold", "холод"), (r"\bfire\b|ignit", "fire", "огонь"),
    (r"lightning|shock", "lightning", "молния"), (r"\bchaos\b|poison", "chaos", "хаос"),
    (r"physical", "physical", "физический"), (r"\blife\b", "life", "здоровье"), (r"\bmana\b", "mana", "мана"),
    (r"energy shield", "energy shield", "энергетический щит"), (r"evasion", "evasion", "уклонение"),
    (r"\barmour\b", "armour", "броня"), (r"resistance", "resistance", "сопротивление"),
    (r"critical", "critical", "критический крит"), (r"attack speed", "attack speed", "скорость атаки"),
    (r"cast speed", "cast speed", "скорость сотворения"), (r"\bspirit\b", "spirit", "дух"),
    (r"minion", "minion", "приспешник"), (r"projectile", "projectile", "снаряд"), (r"area of effect", "area", "область"),
    (r"\bstun", "stun", "оглушение"), (r"freez", "freeze", "заморозка"), (r"ignit", "ignite", "поджог"),
    (r"shock", "shock", "шок"), (r"bleed", "bleeding", "кровотечение"), (r"poison", "poison", "яд"),
    (r"accuracy", "accuracy", "точность"), (r"\bblock", "block", "блок"),
    (r"movement speed", "movement speed", "скорость передвижения"), (r"strength", "strength", "сила"),
    (r"dexterity", "dexterity", "ловкость"), (r"intelligence", "intelligence", "интеллект"),
    (r"charges?\b", "charges", "заряд"), (r"\brage\b", "rage", "свирепость"), (r"totem", "totem", "тотем"),
    (r"\bcurse", "curse", "проклятие"), (r"\bspell", "spell", "чары"), (r"\battack", "attack", "атака"),
    (r"\bmelee\b", "melee", "ближний бой"), (r"quarterstaff", "quarterstaff", "посох"),
    (r"regenerat", "regeneration", "регенерация"), (r"leech", "leech", "похищение"), (r"\bflask", "flask", "флакон"),
    (r"elemental", "elemental", "стихии стихийный"), (r"deflect", "deflection", "отклонение"),
    (r"presence", "presence", "присутствие"), (r"\bcombo\b", "combo", "комбо"), (r"infusion", "infusion", "вливание"),
    (r"\bslam", "slam", "могучий удар"), (r"\bstrike", "strike", "удар"), (r"warcr", "warcry", "клич"),
    (r"companion", "companion", "компаньон"), (r"\bherald", "herald", "вестник"),
)]


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
    # the note shown at once (text, under the author's label) and the one shown over the element (tip)
    for key, limit, what in (("text", MAX_TEXT, "текст"), ("tip", MAX_TIP, "подсказка"), ("label", MAX_LABEL, "метка")):
        value = block.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise AuthorError(f"{what} блока — не строка")
        value = value.replace("\r\n", "\n").strip()
        if key == "label":
            value = " ".join(value.split())
        if len(value) > limit:
            raise AuthorError(f"{what} длиннее {limit} знаков")
        if value:
            out[key] = value
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


def _line_tags(lines) -> list[tuple]:
    text = " ".join(lines or [])
    return [(en, ru, more) for rx, en, ru, more in LINE_WORDS if rx.search(text)]


def build_index(gems: list[dict], uniques: list[dict], bases: list[dict], runes: list[dict], nodes: list[dict],
                terms: dict, names: dict, local: bool = True) -> list[dict]:
    """Everything a token can be, with its English and local names and what it is (its tags) for the search.
    `names`: English -> local; `local`: the tags shown in the local language (Russian), else in English."""
    out, seen = [], set()

    def add(kind, id_, en, sub="", local_name=None, tags=(), **extra):
        if not en or (kind, id_) in seen:
            return
        seen.add((kind, id_))
        loc = (names or {}).get(en, "") if local_name is None else local_name
        tags = list(dict.fromkeys(tags))
        out.append({"kind": kind, "id": id_, "en": en, "local": loc if loc != en else "", "sub": sub,
                    "tags": [ru if local else t_en for t_en, ru, _more in tags],
                    "keys": [normalize(en)] + ([normalize(loc)] if loc and loc != en else []),
                    "tagKey": [normalize(x) for t_en, ru, more in tags for x in (t_en, ru, *more.split())], **extra})

    def item_type(t):
        return [ITEM_TYPES[t]] if t in ITEM_TYPES else []

    for g in gems:
        tags = [GEM_TAGS[t] for t in g.get("tags", []) if t in GEM_TAGS]
        tags += [WEAPONS[w] for w in g.get("weapons", []) if w in WEAPONS]
        add("support" if g.get("support") else "gem", g["name"], g["name"], tags=tags)
    for u in uniques:
        add("unique", u["name"], u["name"], u.get("base", ""), base=u.get("base", ""),
            tags=item_type(u.get("type")) + _line_tags(u.get("lines")))
    for b in bases:
        if not b.get("hidden"):
            add("base", b["name"], b["name"], b.get("type", ""), tags=item_type(b.get("type")))
    for r in runes:
        add("rune", r["name"], r["name"], tags=_line_tags([l for lines in (r.get("targets") or {}).values() for l in lines]))
    for n in nodes:
        if n.get("type") in PASSIVE_TYPES and n.get("name"):
            sub = n.get("asc") or n["type"]
            kind = [("keystone", "ключевое", "кейстоун")] if n["type"] == "Keystone" else \
                [("notable", "значимое", "ноутбл")] if n["type"] == "Notable" else []
            add("passive", f"{n['id']}|{n['name']}", n["name"], sub, img=n.get("img", ""),
                tags=kind + _line_tags(n.get("stats")))
    named = set()  # the glossary's aliases point at one entry: it is found once
    for kid, e in (terms or {}).items():
        if e.get("name") not in named:
            named.add(e.get("name"))
            add("term", kid, e.get("name", ""), "", local_name=e.get("nameLocal", ""))
    return out


def _starts(word: str, text: str) -> bool:
    """`word` begins one of the words of `text` ("атак" in "атака", not "лук" in "клук")."""
    return re.search(r"(?:^|[\s\-'(])" + re.escape(word), text) is not None


def search(index: list[dict], query: str, kinds: list[str] | None = None, limit: int = 30) -> list[dict]:
    """The index's entries every word of the query is in - its English or local name, or what it is (a tag: "атака
    удар посох" finds Ice Strike) - the closest first: the whole name, its start, a word's start, anywhere in the
    name; then the ones found by their tags: each word a tag's start before a word inside a tag ("удар" is a
    strike's tag, and a word of a slam's "могучий удар")."""
    words = normalize(query).split()
    if not words:
        return []
    want = set(kinds or KINDS)
    phrase = " ".join(words)
    scored = []
    for e in index:
        if e["kind"] not in want:
            continue
        best = None
        for key in e["keys"]:
            if not all(w in key for w in words):
                continue
            rank = 0 if key == phrase else 1 if key.startswith(phrase) else 2 if all(_starts(w, key) for w in words) else 3
            best = rank if best is None else min(best, rank)
        if best is None and e["tagKey"]:  # by what it is: each word a tag or in the name, one at least a tag
            strong = [any(tag.startswith(w) for tag in e["tagKey"]) for w in words]
            weak = [any(_starts(w, tag) for tag in e["tagKey"]) for w in words]
            named = [any(_starts(w, k) for k in e["keys"]) for w in words]
            if any(weak) and all(wk or nm for wk, nm in zip(weak, named)):
                best = 4 if all(st or nm for st, nm in zip(strong, named)) else 5
        if best is not None:
            scored.append((best, ORDER[e["kind"]], len(e["en"]), e["en"], e))
    scored.sort(key=lambda x: x[:4])
    return [{k: v for k, v in x[4].items() if k not in ("keys", "tagKey")} for x in scored[:limit]]
