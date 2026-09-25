"""A better item for one slot on the official trade site: which mods to ask for, the searches, the listings as items
PoB can read, and their prices.

The trade site's API is the one its own page uses (www.pathofexile.com/api/trade2): it is not documented as a public
API, so requests are few (a search or two and a fetch per search), carry an identifying User-Agent and stay within the
limits the site states in its X-Rate-Limit headers; a listing is only read, never bought or messaged from here."""
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from ..data.moddb import ModDB, numbers, ranges
from ..i18n import USER_AGENT, _get as trade_data

SITE = "https://www.pathofexile.com"
KEY_MODS = 4  # the first search: the mods that matter most
IDEAL_MODS = 8  # the second: an item made for the build, most of these at once
IDEAL_COUNT = 5
FETCH = 10  # listings read per search (the cheapest ones)
MAX_WAIT = 25.0  # seconds a search may wait for the site's rate limit before giving up
REQ_LEVEL_SHARE = 0.8  # an item's level requirement is about 80% of its highest mod's level
KEEP_SHARE = 0.9  # a mod the worn item has: the replacement's roll at least this share of it

# item class (PoB's type) -> the site's category; bucklers and quarterstaves are told by their tags
CATEGORY = {
    "Body Armour": "armour.chest", "Helmet": "armour.helmet", "Gloves": "armour.gloves", "Boots": "armour.boots",
    "Shield": "armour.shield", "Focus": "armour.focus", "Quiver": "armour.quiver", "Amulet": "accessory.amulet",
    "Ring": "accessory.ring", "Belt": "accessory.belt", "One Hand Mace": "weapon.onemace",
    "Two Hand Mace": "weapon.twomace", "Spear": "weapon.spear", "Staff": "weapon.staff", "Bow": "weapon.bow",
    "Crossbow": "weapon.crossbow", "Wand": "weapon.wand", "Sceptre": "weapon.sceptre", "Talisman": "weapon.talisman",
    "Claw": "weapon.claw", "Dagger": "weapon.dagger", "One Hand Sword": "weapon.onesword",
    "Two Hand Sword": "weapon.twosword", "One Hand Axe": "weapon.oneaxe", "Two Hand Axe": "weapon.twoaxe",
    "Flail": "weapon.flail",
}


class TradeError(RuntimeError):
    pass


def category(item_type: str, tags) -> str | None:
    tags = set(tags or ())
    if "warstaff" in tags:
        return "weapon.warstaff"
    if "buckler" in tags:
        return "armour.buckler"
    return CATEGORY.get(item_type)


# ---------- the site's rate limits: each policy's rules, from the headers of its last answer ----------

class Limiter:
    """Sliding windows per policy ("hits:period:restriction" rules); one request is always kept in reserve, and a
    restriction or a 429 blocks the policy for the time the site names."""

    def __init__(self, rules: list[tuple[int, int]]):
        self.rules = rules
        self.times: list[float] = []
        self.blocked_until = 0.0

    def delay(self, now: float) -> float:
        wait = max(0.0, self.blocked_until - now)
        for hits, period in self.rules:
            recent = [t for t in self.times if now - t < period]
            if len(recent) >= max(1, hits - 1):
                wait = max(wait, period - (now - recent[0]) + 0.1)
        return wait

    def taken(self, now: float):
        self.times = [t for t in self.times if now - t < max((p for _, p in self.rules), default=0)] + [now]

    def update(self, headers, now: float):
        rules, state = headers.get("X-Rate-Limit-Ip"), headers.get("X-Rate-Limit-Ip-State")
        if rules:
            self.rules = [(int(r.split(":")[0]), int(r.split(":")[1])) for r in rules.split(",")]
        if rules and state:
            for rule, current in zip(rules.split(","), state.split(",")):
                hits, period, _ = (int(x) for x in rule.split(":"))
                seen, _, restricted = (int(x) for x in current.split(":"))
                if restricted:
                    self.blocked_until = max(self.blocked_until, now + restricted)
                elif seen >= hits - 1:  # other tools on this address count too
                    self.blocked_until = max(self.blocked_until, now + period)


LIMITS = {"search": Limiter([(5, 10), (15, 60), (30, 300)]), "fetch": Limiter([(12, 4), (16, 12), (50, 300)])}
_limit_lock = threading.Lock()


def _call(policy: str, url: str, body: dict | None = None) -> dict:
    limiter = LIMITS[policy]
    with _limit_lock:
        wait = limiter.delay(time.monotonic())
        if wait > MAX_WAIT:
            raise TradeError(f"торговая площадка просит паузу: попробуй через {wait:.0f} с")
        if wait:
            time.sleep(wait)
        limiter.taken(time.monotonic())
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as res:
            limiter.update(res.headers, time.monotonic())
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        limiter.update(err.headers, time.monotonic())
        if err.code == 429:
            after = int(err.headers.get("Retry-After") or 60)
            limiter.blocked_until = max(limiter.blocked_until, time.monotonic() + after)
            raise TradeError(f"торговая площадка просит паузу: попробуй через {after} с") from None
        try:
            detail = json.loads(err.read().decode("utf-8")).get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detail = ""
        raise TradeError(f"торговая площадка ответила {err.code}" + (f": {detail}" if detail else "")) from None
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        raise TradeError(f"нет связи с торговой площадкой ({err})") from None


# ---------- what to ask for ----------

def _trade_value(line: str) -> float | None:
    """The number the site filters a line by: its value, or the mean of "# to #" pairs."""
    nums = [lo for lo, _ in ranges(line)] or numbers(line)
    if not nums or "reduced" in line.lower():
        return None
    return (nums[0] + nums[1]) / 2 if len(nums) == 2 and " to " in line else nums[0]


def pick_mods(db: ModDB, plan: dict, tags, level: int) -> list[dict]:
    """The slot's mods by their worth to the build (plan: poe2lab.analysis.slots.SlotPlan as a dict): what the worn
    item has and what it could have. `must` marks what the build leans on (a capped resistance, an attribute it
    needs, movement speed): a replacement has to carry it too. Each with the site's stat id and a minimum: the low
    roll of the third best tier the character can wear, and for a mod the worn item has, at least 90% of its roll."""
    known = {e["id"] for g in trade_data("en", "stats") for e in g["entries"]}
    by_lines = {}
    for m in db.mods:
        by_lines.setdefault(tuple(m.lines), m)
    by_id = {m.id: m for m in db.mods}
    wearable = max(1, int(level / REQ_LEVEL_SHARE))
    entries = [(a, by_lines.get(tuple(a["template"])), True) for a in plan["affixes"]]
    entries += [(c, by_id.get(c.get("mod_id", "")), False) for c in plan["candidates"]]
    out, seen = [], set()
    for row, mod, worn in entries:
        if mod is None or not mod.trade_hashes:
            continue
        family = (mod.group, mod.patterns)
        stat = f"explicit.stat_{mod.trade_hashes[0]}"
        if family in seen or stat not in known:
            continue
        must = worn and (bool(row.get("holds")) or any("Movement Speed" in l for l in row["lines"]))
        if row["score"] <= 0 and not must:
            continue
        tiers = [m for m in db.tiers_of(mod, tags) if m.level <= wearable] or [mod]
        low = _trade_value(tiers[min(2, len(tiers) - 1)].lines[0])
        if low is None:
            continue
        if worn:
            # what the worn item already gives, a replacement has to give nearly as much, or it is a step back
            now = _trade_value(row["lines"][0])
            low = max(low, now * KEEP_SHARE) if now else low
        seen.add(family)
        out.append({"id": stat, "min": round(low), "line": row["lines"][0], "type": mod.type,
                    "score": row["score"], "must": must, "worn": worn})
    out.sort(key=lambda x: (not x["must"], -x["score"]))
    return out


def queries(mods: list[dict], cat: str, level: int, attributes: dict[str, float] | None = None) -> list[dict]:
    """The two searches: the key mods (all of them), then an item made for the build (most of the best eight).
    Only what the character can wear: its level, and its attributes without the worn item (an item's own
    attributes do not count towards its requirements)."""
    reqs = {"lvl": {"max": level}}
    for key, value in (attributes or {}).items():
        reqs[key] = {"max": int(value)}

    def body(stats):
        return {"query": {"status": {"option": "available"}, "stats": stats,
                          "filters": {"type_filters": {"filters": {"category": {"option": cat},
                                                                   "rarity": {"option": "nonunique"}}},
                                      "req_filters": {"filters": reqs}}},
                "sort": {"price": "asc"}}

    def flt(m):
        return {"id": m["id"], "value": {"min": m["min"]}, "disabled": False}

    out = []
    key = mods[:KEY_MODS]
    if key:
        out.append({"kind": "key", "mods": key, "body": body([{"type": "and", "filters": [flt(m) for m in key]}]),
                    "relaxed": body([{"type": "and", "filters": [flt(m) for m in key if m["must"]]},
                                     {"type": "count", "value": {"min": max(1, len(key) - 1 - sum(m["must"] for m in key))},
                                      "filters": [flt(m) for m in key if not m["must"]]}]) if len(key) >= 3 else None})
    ideal = mods[:IDEAL_MODS]
    if len(ideal) > KEY_MODS:
        must, rest = [m for m in ideal if m["must"]], [m for m in ideal if not m["must"]]
        need = max(1, min(len(rest), IDEAL_COUNT - len(must)))
        out.append({"kind": "ideal", "mods": ideal, "relaxed": None,
                    "body": body([{"type": "and", "filters": [flt(m) for m in must]},
                                  {"type": "count", "value": {"min": need}, "filters": [flt(m) for m in rest]}])})
    return out


def search(league: str, body: dict) -> dict:
    """{id, total, result: [listing ids, cheapest first]}"""
    return _call("search", f"{SITE}/api/trade2/search/poe2/{urllib.parse.quote(league)}", body)


def fetch(query_id: str, ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 10):  # the site gives ten per request
        part = ",".join(ids[i:i + 10])
        out += [r for r in _call("fetch", f"{SITE}/api/trade2/fetch/{part}?query={query_id}").get("result", []) if r]
    return out


def search_url(league: str, query_id: str) -> str:
    return f"{SITE}/trade2/search/poe2/{urllib.parse.quote(league)}/{query_id}"


# ---------- a listing as an item PoB reads, and its price ----------

_MARKUP = re.compile(r"\[([^\]|]+)(?:\|([^\]]+))?\]")


def plain(text: str) -> str:
    """"+29% to [Resistances|Cold Resistance]" -> "+29% to Cold Resistance"."""
    return _MARKUP.sub(lambda m: m.group(2) or m.group(1), text or "")


def mod_lines(mods) -> list[str]:
    lines = []
    for m in mods or []:
        text = m.get("description", "") if isinstance(m, dict) else m
        lines += [plain(l) for l in str(text).split("\n") if l.strip()]
    return lines


def item_text(item: dict) -> str:
    """The listing in the game's copy format (as poe2lab.itemtext writes it for PoB)."""
    rarity = (item.get("rarity") or "Rare").capitalize()
    base = plain(item.get("baseType") or item.get("typeLine", ""))
    lines = [f"Rarity: {rarity}"]
    if rarity == "Unique":
        lines.append(plain(item.get("name", "")))
    elif rarity == "Rare":
        lines.append("poe2lab item")  # a rare's random name means nothing to PoB
    lines += [base, "--------"]
    for p in item.get("properties", []):
        if plain(p.get("name", "")) == "Quality" and p.get("values"):
            number = re.search(r"\d+", p["values"][0][0])
            if number:
                lines += [f"Quality: {number.group(0)}", "--------"]
    lines += [f"Item Level: {item.get('ilvl', 1)}", "--------"]
    tagged = [(mod_lines(item.get("enchantMods")), " (enchant)"), (mod_lines(item.get("runeMods")), " (rune)"),
              (mod_lines(item.get("implicitMods")), " (implicit)")]
    for group, tag in tagged:
        if group:
            lines += [l + tag for l in group] + ["--------"]
    lines += mod_lines(item.get("fracturedMods")) + mod_lines(item.get("explicitMods"))
    lines += mod_lines(item.get("desecratedMods")) + mod_lines(item.get("craftedMods"))
    if item.get("corrupted"):
        lines += ["--------", "Corrupted"]
    return "\n".join(lines)


def requirements(item: dict) -> dict[str, int]:
    out = {}
    for r in item.get("requirements", []):
        name, values = plain(r.get("name", "")), r.get("values") or []
        number = re.search(r"\d+", values[0][0]) if values else None
        if number:
            out[{"Strength": "Str", "Dexterity": "Dex", "Intelligence": "Int"}.get(name, name)] = int(number.group(0))
    return out


def price(listing: dict, prices) -> dict | None:
    """The asking price, and in exalted and divine orbs by poe.ninja's rates when the currency is known there."""
    p = (listing or {}).get("price")
    if not p or p.get("amount") is None:
        return None
    amount, currency = float(p["amount"]), p.get("currency", "")
    out = {"amount": amount, "currency": currency, "ex": None, "div": None}
    if prices:
        rate = prices.exalted_per_divine
        divine = amount / rate if currency == "exalted" and rate else (
            amount if currency == "divine" else (prices.prices[currency].divine * amount if currency in prices.prices
                                                 else None))
        if divine is not None:
            out["div"] = divine
            out["ex"] = divine * rate if rate else None
    return out
