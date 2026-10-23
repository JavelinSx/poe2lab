"""Precursor Tablets and Waystones: their modifiers from the installed game, sorted by what a player farms with them.

Both are rows of mods.datc64: tablets are the domain the game keeps for them (34) - the tablet's type (its implicit:
Breach, Delirium, Ritual...) and the modifiers it can roll, general ones and ones for one type only (spawn tag
tower_augment_<type>); waystones are the map domain's prefixes and suffixes that roll on waystones (spawn tags
map_key_<tier>). A waystone modifier is a danger (what the monsters or the player get) paid with a reward: its stats
named *_final_from_map are what the map gives back (more waystones, rarity, pack size, effectiveness...).

What a modifier is good for, and how dangerous a waystone's is, is found by its stats - so a patch that changes the
numbers or adds tiers is followed without changes here. Texts are the game's own, in English and the player's language,
from all its stat descriptions."""
import json
import re
import subprocess
from pathlib import Path

from . import gamedata
from .atlas import describe
from .gamedata import BUN, GAME_CACHE, RAW, GameDataError, read_table

CACHE = GAME_CACHE / "endgame.json"
VERSION = 4
TABLES = ["mods", "tags", "stats", "clientstrings", "baseitemtypes", "itemvisualidentity"]
TABLET_DOMAIN, MAP_DOMAIN = 34, 6
# what a modifier gives, by its stats (the interface names them: egG_<goal>)
GOALS = [
    ("waystones", r"map_item_drop_chance|map_map_item_drop|dropped_maps|map_drop_chance"),
    ("rarity", r"item_drop_rarity|boss_item_rarity|item_rarity"),
    ("quantity", r"item_drop_quantity|dropped_item_quantity"),
    ("monsters", r"pack_size|magic_packs|rare_packs|magic_and_rare|monster_potency|rare_monster_modifiers|additional_modifier"
                 r"|additional_rare_monsters|rare_monsters_\+|magic_monsters_\+"),
    ("experience", r"experience"),
    ("gold", r"gold"),
    ("content", r"shrine|strongbox|monolith|essence|tormented_spirit|spawn_extra_torment|rogue_exile|spawn_extra_exiles"
                r"|stone_circle|rare_chest|additional_mods|num_additional_modifiers"),
    ("mechanic", r"breach|expedition|verisium|delirium|affliction|simulacrum|ritual|abyss|incursion|vaal_beacon"),
]
# how dangerous a waystone modifier's own part is, for most builds (egD_<level>); the first match wins
DANGER = [
    ("deadly", r"player_maximum_resistances|life_and_es_recovery|recovery_speed|penetrate|player_curse|no_regen|cannot_leech"
               r"|reflect"),
    ("hard", r"monsters_damage_\+|damage_to_gain_as|critical_strike|attack_cast_and_movement_speed|additional_number_of_proj"
             r"|monsters_life_\+|armour_break|elemental_ailment|cooldown|charges_gained"),
    ("mild", r"."),
]
TIERS = ["map_key_low", "map_key_medium", "map_key_high", "map_key_highest"]


def _extract(game: Path):
    if not BUN.is_file():
        raise GameDataError(f"нет {BUN.relative_to(gamedata.ROOT)}")
    patterns = [rf"^data/balance/({'|'.join(TABLES)})\.datc64$", r"^data/balance/russian/clientstrings\.datc64$",
                r"^data/statdescriptions/[^/]+\.csd$"]
    res = subprocess.run([str(BUN), "extract-files", "--regex", str(game), str(RAW), *patterns],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise GameDataError(f"bun_extract_file: {res.stderr.strip() or res.stdout.strip()}")


def _descriptions(lang: str) -> dict:
    """All the game's top-level stat description files as one index (the first file to describe a stat wins)."""
    merged = {"entries": [], "index": {}}
    files = sorted((RAW / "data/statdescriptions").glob("*.csd"),
                   key=lambda f: (f.name not in ("tablet_stat_descriptions.csd", "map_stat_descriptions.csd",
                                                 "atlas_stat_descriptions.csd", "stat_descriptions.csd"), f.name))
    for f in files:
        d = gamedata.parse_csd(f.read_bytes().decode("utf-16-le").lstrip("﻿"), lang)
        off = len(merged["entries"])
        merged["entries"] += d["entries"]
        for stat, i in d["index"].items():
            merged["index"].setdefault(stat, i + off)
    return merged


_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def ranged(low: list[str], high: list[str]) -> list[str]:
    """The lowest and the highest tier's lines as one: the numbers that differ become "low–high"."""
    if len(low) != len(high):
        return high
    out = []
    for a, b in zip(low, high):
        na, nb = _NUM.findall(a), _NUM.findall(b)
        if len(na) != len(nb) or _NUM.sub("#", a) != _NUM.sub("#", b):
            out.append(b)
            continue
        parts = _NUM.split(b)
        out.append("".join(p + (("" if x == y else f"{x}–") + y if i < len(nb) else "")
                           for i, (p, x, y) in enumerate(zip(parts, na + [""], nb + [""]))))
    return out


def _tags(stats: list[str], table: list[tuple[str, str]]) -> list[str]:
    return [t for t, pat in table if any(re.search(pat, s) for s in stats)]


def build(game: Path | None = None, lang: str = "ru") -> dict:
    game = game or gamedata.game_dir()
    if game is None:
        raise GameDataError("нужна установленная игра")
    _extract(game)
    balance = RAW / "data/balance"
    tags = [r["Id"] for r in read_table(balance / "tags.datc64", ["Id"])]
    stat_ids = [r["Id"] for r in read_table(balance / "stats.datc64", ["Id"])]
    cols = ["Id", "Domain", "GenerationType", "Level", "SpawnTags"] + [f"Stat{i}" for i in range(1, 5)] + \
        [f"Stat{i}Value" for i in range(1, 5)]
    descs = _descriptions(lang)
    families: dict[tuple, dict] = {}
    for r in read_table(balance / "mods.datc64", cols):
        spawn = [tags[t] for t in r["SpawnTags"] if t < len(tags)]
        if r["Domain"] == TABLET_DOMAIN:
            kind = {1: "prefix", 2: "suffix", 3: "implicit"}.get(r["GenerationType"])
            ttype = next((t.removeprefix("tower_augment_") for t in spawn if t.startswith("tower_augment_")), "")
            if r["Id"].startswith("Unique"):
                kind = "unique"
            m = re.match(r"TowerAdd(\w+?)ToMapsImplicit", r["Id"])
            if m:  # the tablet's type: what it adds to the maps around its tower
                ttype = re.sub(r"(?<!^)(?=[A-Z])", "_", m.group(1)).lower().replace("map_bosses", "map_boss")
        elif r["Domain"] == MAP_DOMAIN and r["GenerationType"] in (1, 2) and any(t in TIERS for t in spawn):
            kind, ttype = {1: "prefix", 2: "suffix"}[r["GenerationType"]], ""
        else:
            continue
        stats = [(stat_ids[r[f"Stat{i}"]], r[f"Stat{i}Value"]) for i in range(1, 5)
                 if r[f"Stat{i}"] is not None and r[f"Stat{i}"] < len(stat_ids) and r[f"Stat{i}Value"] != [0, 0]]
        # (a stat at 0 is a slot the game leaves unused: "0% more waystones" would only confuse)
        if not stats:
            continue
        family = re.sub(r"\d+$", "", r["Id"])
        key = ("tablet" if r["Domain"] == TABLET_DOMAIN else "waystone", family, kind)
        f = families.setdefault(key, {"item": key[0], "id": family, "kind": kind, "type": ttype, "tiers": [],
                                      "stats": [s for s, _ in stats]})
        f["tiers"].append({"level": r["Level"], "spawn": [t for t in spawn if t in TIERS],
                           "low": [(s, v[0]) for s, v in stats], "high": [(s, v[1]) for s, v in stats]})
    mods = []
    for f in families.values():
        f["tiers"].sort(key=lambda t: (TIERS.index(t["spawn"][0]) if t["spawn"] else 0, t["level"]))
        first, last = f["tiers"][0], f["tiers"][-1]
        text = {}
        for code, key in (("en", "en"), (lang, "want")):
            text[code] = ranged(describe(first["low"], descs, key), describe(last["high"], descs, key))
        if not text["en"]:
            continue  # the game shows nothing for it (an empty or retired modifier)
        reward = [s for s in f["stats"] if s.endswith("_final_from_map")] if f["item"] == "waystone" else f["stats"]
        own = [s for s in f["stats"] if s not in reward] if f["item"] == "waystone" else []
        parts = {}
        if f["item"] == "waystone":  # the danger and the reward, each in its own lines
            for part, names in (("risk", own), ("reward", reward)):
                lo = [(st, v) for st, v in first["low"] if st in names]
                hi = [(st, v) for st, v in last["high"] if st in names]
                parts[part] = {code: ranged(describe(lo, descs, key), describe(hi, descs, key))
                               for code, key in (("en", "en"), (lang, "want"))}
        mods.append({"item": f["item"], "id": f["id"], "kind": f["kind"], "type": f["type"], "text": text, **parts,
                     "base": bool(re.match(r"TowerAdd\w+?ToMapsImplicit", f["id"])),  # the tablet's type itself, not one of its modifiers
                     "tiers": len(f["tiers"]), "goals": _tags(reward, GOALS), "stats": sorted(f["stats"]),
                     "danger": (_tags(own, DANGER) or [""])[0] if f["item"] == "waystone" else ""})
    out = {"version": VERSION, "lang": lang, "properties": _properties(balance, lang), "mods": sorted(mods, key=lambda m: (m["item"], m["kind"], m["type"], m["id"]))}
    CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def _markup(text: str) -> str:
    return re.sub(r"\[[^|\]]+\|([^\]]+)\]", r"\1", text).strip()


def _properties(balance: Path, lang: str) -> list[dict]:
    """The lines a waystone shows in its header (Monster Effectiveness, Item Rarity...), with the shortest ending of
    each name that no other one has: what a stash search can look for without catching the others."""
    strings = read_table(balance / "clientstrings.datc64", ["Id", "Text"])
    local = read_table(balance / gamedata.LANG_NAMES[lang].lower() / "clientstrings.datc64", ["Text"])
    props = [{"id": r["Id"].removeprefix("ItemDisplayMap"), "name": {"en": _markup(r["Text"]), lang: _markup(local[i]["Text"])}}
             for i, r in enumerate(strings) if r["Id"].startswith("ItemDisplayMap") and r["Id"] != "ItemDisplayMapTier"]
    for p in props:
        for code in ("en", lang):
            name = p["name"][code].lower()
            others = [q["name"][code].lower() for q in props if q is not p]
            tail = next((name[-k:] for k in range(6, len(name) + 1)
                         if not any(name[-k:] in o for o in others) and not name[-k:].startswith(" ")), name)
            p.setdefault("search", {})[code] = tail
    return props


def load(game: Path | None = None, lang: str = "ru") -> dict | None:
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    index = game / "Bundles2" / "_.index.bin" if game else None
    if index and index.is_file() and index.stat().st_mtime > CACHE.stat().st_mtime:
        return None
    return data if data.get("version") == VERSION and data.get("lang") == lang else None


# the tablet types (as endgame names them) -> the base item that carries the type
TABLET_BASES = {"breach": "Breach Tablet", "expedition": "Expedition Tablet", "delirium": "Delirium Tablet",
                "ritual": "Ritual Tablet", "irradiated": "Irradiated Tablet", "map_boss": "Overseer Tablet",
                "abyss": "Abyss Tablet", "incursion": "Temple Tablet"}


def _art() -> dict:
    """The tablets' (per type) and the waystone's item art paths."""
    balance = RAW / "data/balance"
    try:
        vis = [r["DDSFile"] for r in read_table(balance / "itemvisualidentity.datc64", ["DDSFile"])]
        bases = read_table(balance / "baseitemtypes.datc64", ["Name", "ItemVisualIdentityKey"])
    except (OSError, KeyError):
        return {}
    by_name = {r["Name"]: vis[r["ItemVisualIdentityKey"]] for r in bases
               if r["ItemVisualIdentityKey"] is not None and r["ItemVisualIdentityKey"] < len(vis)}
    out = {"tablets": {t: by_name.get(n, "") for t, n in TABLET_BASES.items()}, "waystone": by_name.get("Waystone (Tier 15)", "")}
    out["tablet"] = out["tablets"].get("irradiated", "")
    return out


def item_art(names, game: Path | None = None) -> dict[str, str]:
    """English item name -> its picture under /icons (converted from the game when missing); "" when it has none."""
    from . import icons
    balance = RAW / "data/balance"
    try:
        vis = [r["DDSFile"] for r in read_table(balance / "itemvisualidentity.datc64", ["DDSFile"])]
        bases = read_table(balance / "baseitemtypes.datc64", ["Name", "ItemVisualIdentityKey"])
    except (OSError, KeyError):
        return {}
    wanted = set(names)
    paths = {}
    for r in bases:
        k = r["ItemVisualIdentityKey"]
        if r["Name"] in wanted and r["Name"] not in paths and k is not None and k < len(vis) and vis[k]:
            paths[r["Name"]] = vis[k]
    if game and any(not icons.art_file(p) for p in paths.values()):
        icons.convert(game, set(paths.values()))
    return {n: icons.art_file(paths.get(n, "")) for n in wanted}


def farm_art(result: dict, game: Path | None = None) -> dict:
    """The farming options' drops with their pictures ("img")."""
    names = {d["name"] for o in result.get("options", []) for d in o["drops"]}
    art = item_art(names, game)
    for o in result.get("options", []):
        for d in o["drops"]:
            d["img"] = art.get(d["name"], "")
    return result


def guide(game: Path | None = None) -> dict:
    from . import icons
    data = load(game) or build(game)
    art = _art()
    paths = {p for p in [*art.get("tablets", {}).values(), art.get("waystone", ""), art.get("tablet", "")] if p}
    if game and any(not icons.art_file(p) for p in paths):
        icons.convert(game, paths)
    data["art"] = {"tablets": {t: icons.art_file(p) for t, p in art.get("tablets", {}).items()},
                   "waystone": icons.art_file(art.get("waystone", "")), "tablet": icons.art_file(art.get("tablet", ""))}
    return data


# ---------- farming options by current prices ----------

# A way to farm: the poe.ninja categories its loot is sold in, the tablet type that brings it, the atlas sub-tree for
# it, and the stats (of atlas and master nodes, tablet and waystone modifiers) that feed it. "leveling" has no loot
# to price: it is about experience.
FARM = [
    ("breach", ["Breach"], "breach", "Breach", r"breach"),
    ("delirium", ["Delirium"], "delirium", "Delirium", r"delirium|affliction|simulacrum"),
    ("ritual", ["Ritual"], "ritual", "Ritual", r"ritual"),
    ("expedition", ["Expedition", "Verisium"], "expedition", "Expedition", r"expedition|verisium"),
    ("abyss", ["Abyss"], "abyss", "Abyss", r"abyss"),
    ("essence", ["Essences"], "", "", r"monolith|essence"),
    ("bosses", ["Fragments", "LineageSupportGems"], "map_boss", "", r"boss|pinnacle|lineage"),
    ("currency", ["Currency"], "", "", r"item_drop_rarity|item_drop_quantity|rare_packs|magic_packs|pack_size"),
    ("leveling", [], "", "", r"experience"),
]
TOP_DROPS = 4
MIN_VOLUME = 1.0  # traded volume (divines) a drop needs to count as one that sells
UNITS = {"divine", "exalted", "chaos"}  # what the market pays with: not loot of any one way to farm
JACKPOT = 1000.0  # divines: a drop this rare (a Mirror) is luck, not what a way of farming brings


def farm(league: str | None = None) -> dict:
    """Each farming option with what its loot trades for now on poe.ninja: the total traded volume of its categories
    (how much of that loot the market moves - a stand-in for how rewarding and sellable it is, not a profit per hour)
    and its dearest drops that do sell."""
    from .economy import ninja
    league = league or ninja.chosen_league() or ninja.leagues()[0]
    rate = 0.0
    options = []
    for fid, types, tablet, part, pattern in FARM:
        volume, drops = 0.0, []
        for t in types:
            try:
                data = ninja._get("exchange/current/overview", league=league, type=t)
            except OSError:
                continue
            rate = rate or data.get("core", {}).get("rates", {}).get("exalted", 0.0)
            names = {i["id"]: i.get("name", "") for i in data.get("items", [])}
            for line in data.get("lines", []):
                if line["id"] in UNITS:
                    continue
                v, p = float(line.get("volumePrimaryValue", 0)), float(line.get("primaryValue", 0))
                if p >= JACKPOT:
                    continue
                volume += v
                if names.get(line["id"]) and v >= MIN_VOLUME:
                    drops.append({"name": names[line["id"]], "div": p, "volume": v, "kind": t})
        drops.sort(key=lambda d: -d["volume"])  # what sells the most, not the rare jackpot
        options.append({"id": fid, "types": types, "tablet": tablet, "part": part, "stats": pattern,
                        "volume": round(volume, 1), "drops": drops[:TOP_DROPS]})
    priced = [o for o in options if o["types"]]
    top = max((o["volume"] for o in priced), default=0) or 1
    for o in priced:
        o["score"] = round(o["volume"] / top, 3)
    options.sort(key=lambda o: (not o["types"], -o.get("score", 0)))
    return {"league": league, "exaltedPerDivine": rate, "options": options}
