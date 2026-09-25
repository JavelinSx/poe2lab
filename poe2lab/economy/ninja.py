"""Prices from poe.ninja's PoE2 exchange overview, cached on disk for an hour (poe.ninja refreshes ~hourly)."""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE = "https://poe.ninja/poe2/api/economy"
USER_AGENT = "poe2lab/0.1 (personal build analysis tool)"
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "ninja"
CACHE_SECONDS = 3600
EXCHANGE_TYPES = ("Currency", "Essences", "SoulCores", "Runes", "Idols", "Ritual", "Abyss")  # Ritual: omens; Abyss: bones
THIN_MARKET = 1.0  # traded volume (in divines) below which a price is shaky


def slug(name: str) -> str:
    """poe.ninja line id for an item name: "Saqawal's Rune of the Sky" -> "saqawals-rune-of-the-sky"."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")


@dataclass(frozen=True)
class Price:
    divine: float
    volume: float  # traded value in divines, a rough liquidity signal

    @property
    def thin(self) -> bool:
        return self.volume < THIN_MARKET


class PriceBook:
    def __init__(self, league: str, prices: dict[str, Price], exalted_per_divine: float):
        self.league = league
        self.prices = prices
        self.exalted_per_divine = exalted_per_divine

    def get(self, name: str) -> Price | None:
        return self.prices.get(slug(name))

    def describe(self, price: Price) -> str:
        ex = price.divine * self.exalted_per_divine
        amount = f"{price.divine:.2f} div" if price.divine >= 0.1 else (f"{ex:.0f} ex" if ex >= 1 else "<1 ex")
        return amount + (" (мало сделок)" if price.thin else "")

    def per_divine(self, score: float, price: Price) -> float | None:
        """Score bought per divine; None for effectively free items where the ratio means nothing."""
        return score / price.divine if price.divine * self.exalted_per_divine >= 1 else None

    @classmethod
    def from_overviews(cls, league: str, overviews: dict[str, dict]) -> "PriceBook":
        prices, rate = {}, 0.0
        for data in overviews.values():
            rate = rate or data.get("core", {}).get("rates", {}).get("exalted", 0.0)
            # common currency has short ids ("alch", "exalted"): its name gives the usual key too
            names = {i["id"]: i.get("name", "") for i in data.get("items", [])}
            for line in data.get("lines", []):
                price = Price(float(line.get("primaryValue", 0)), float(line.get("volumePrimaryValue", 0)))
                prices[line["id"]] = price
                if names.get(line["id"]):
                    prices.setdefault(slug(names[line["id"]]), price)
        return cls(league, prices, rate)

    @classmethod
    def load(cls, league: str | None = None, types=EXCHANGE_TYPES) -> "PriceBook":
        league = league or leagues()[0]
        overviews = {}
        for t in types:
            try:
                overviews[t] = _get("exchange/current/overview", league=league, type=t)
            except OSError:
                if t in EXCHANGE_TYPES[:1]:
                    raise  # without currency there are no prices at all
        return cls.from_overviews(league, overviews)


def leagues() -> list[str]:
    return [l["id"] for l in _get("leagues")]


# The league the player chose for prices and trade searches (the interface's choice), kept with the player's settings.
def _league_path() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(root) / "poe2lab" / "market.json"


def chosen_league() -> str | None:
    try:
        return json.loads(_league_path().read_text(encoding="utf-8")).get("league") or None
    except (OSError, ValueError):
        return None


def choose_league(league: str | None):
    """None: back to poe.ninja's current league."""
    _league_path().parent.mkdir(parents=True, exist_ok=True)
    _league_path().write_text(json.dumps({"league": league}, ensure_ascii=False), encoding="utf-8")


# What a loot filter can tell apart by price: stackable items by name (exact BaseType), uniques by base only
# (a filter cannot read a unique's name).
MARKET_TYPES = EXCHANGE_TYPES + ("Fragments", "Delirium", "Breach", "Expedition", "UncutGems", "LineageSupportGems",
                                 "Verisium")
UNIQUE_TYPES = ("UniqueArmours", "UniqueWeapons", "UniqueAccessories", "UniqueFlasks", "UniqueCharms", "UniqueJewels")


def market(league: str) -> dict:
    """Prices in divines: {"items": {name: {"div", "kind"}}, "uniques": [{"name", "base", "div", "listings"}],
    "exaltedPerDivine"}. A type poe.ninja does not answer for is left out."""
    items, uniques, rate = {}, [], 0.0
    for t in MARKET_TYPES:
        try:
            data = _get("exchange/current/overview", league=league, type=t)
        except OSError:
            continue
        rate = rate or data.get("core", {}).get("rates", {}).get("exalted", 0.0)
        names = {i["id"]: i.get("name", "") for i in data.get("items", [])}
        for line in data.get("lines", []):
            if names.get(line["id"]):
                items[names[line["id"]]] = {"div": float(line.get("primaryValue", 0)), "kind": t}
    for t in UNIQUE_TYPES:
        try:
            data = _get("stash/current/item/overview", league=league, type=t)
        except OSError:
            continue
        for line in data.get("lines", []):
            if line.get("baseType") and line.get("name"):
                uniques.append({"name": line["name"], "base": line["baseType"], "div": float(line.get("primaryValue", 0)),
                                "listings": int(line.get("listingCount", 0))})
    return {"league": league, "items": items, "uniques": uniques, "exaltedPerDivine": rate}


def _get(path: str, **params) -> dict | list:
    key = CACHE_DIR / (slug(path + "-" + "-".join(f"{k}-{v}" for k, v in sorted(params.items()))) + ".json")
    if key.exists() and time.time() - key.stat().st_mtime < CACHE_SECONDS:
        return json.loads(key.read_text(encoding="utf-8"))
    url = f"{BASE}/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=30) as r:
        body = r.read().decode("utf-8")
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_text(body, encoding="utf-8")
    return json.loads(body)
