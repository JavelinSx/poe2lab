"""The Atlas passive tree, read from the installed game, for a beginner's guide to it.

The tree's layout is the game's passive skill graph Metadata/AtlasSkillGraphs/AtlasSkillGraph.psg (the format PoB's
Export/Scripts/passivetree.lua reads for the character tree); its nodes are rows of passiveskills.datc64 joined by
PassiveSkillNodeId, their texts come from atlas_stat_descriptions.csd in English and the player's language. The main
tree and the league mechanics' sub-trees (Breach, Expedition...) are parts of the same graph.

What a beginner should take first is found by the node's stats, not by fixed node ids, so the guide follows the game
when a patch moves or renames nodes: e.g. the node whose stat lets cleansed monsters drop Fracturing Orbs. The route to
those nodes is the shortest path through the graph, the way points are actually spent."""
import json
import math
import re
import struct
import subprocess
from collections import deque
from pathlib import Path

from . import gamedata
from .gamedata import BUN, GAME_CACHE, RAW, GameDataError, read_table

GRAPH = "metadata/atlasskillgraphs/atlasskillgraph.psg"
CSD = "data/statdescriptions/atlas_stat_descriptions.csd"
TABLES = ["passiveskilltrees", "stats", "atlaspassiveskillsubtrees", "clientstrings"]
# the atlas masters (Doryani, Hilda, Jado) and their keystones, in English and the player's language
MASTER_TABLES = ["atlasclasspassives", "atlasclasspassiveclasses"]
CACHE = GAME_CACHE / "atlas.json"
VERSION = 4  # bumped when what is built from the game files changes
# orbits of a group: radius and how many places on it (PoB's tree constants for PoE2, the atlas uses the same)
RADII = [0, 82, 162, 335, 493, 662, 846, 251, 1080, 1322]
PER_ORBIT = [1, 12, 24, 24, 72, 72, 72, 24, 72, 144]
ANGLES_16 = [0, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330]
ANGLES_40 = [0, 10, 20, 30, 40, 45, 50, 60, 70, 80, 90, 100, 110, 120, 130, 135, 140, 150, 160, 170, 180, 190, 200,
             210, 220, 225, 230, 240, 250, 260, 270, 280, 290, 300, 310, 315, 320, 330, 340, 350]
# What to take first, in this order. A group is found by its nodes' stats (regular expressions on stat ids); the guide
# texts for each group are in the interface's dictionary (atlasG_<id>, atlasW_<id>).
KEY_GROUPS = [
    ("fracturing", r"^map_cleansed_monster_can_drop_fracturing_orb$"),
    ("exceptional", r"^map_\w+_can_be_exceptional$"),
    ("tablets", r"^dummy_display_tablets_can_be_rare"),
    ("lineage", r"_anomaly_%_chance_extra_deadly_boss_lineage$"),
]
# groups where one node is enough (the others give the same); in the rest every node counts
ANY_ONE = {"tablets"}
# good to take on the way (shown on the tree, not routed to): more and better monsters, rarity, shrines, waystones
USEFUL = [
    ("monsters", r"^map_number_of_(magic|rare)_packs_\+%$|^map_rare_monster_modifiers_chance_%$|^map_pack_size_\+%$"),
    ("rarity", r"^map_item_drop_rarity_\+%$|^map_unique_monster_item_rarity_\+%$|^map_boss_item_rarity_\+%$"),
    ("shrines", r"^map_shrine_chance_\+%$|^dummy_display_shrine_type_selector$"),
    ("waystones", r"^map_map_boss_bonus_map_drop_chance_\+%$|^map_dropped_maps_rarity_\+%$|^map_tower_augment_quantity"),
]
# when a node opens, in the order the endgame goes (the game's own requirement strings, by id); unknown ones last
STAGES = ["", "AtlasPassiveEndgameYellowFortressMapsAccessible", "AtlasPassiveBaronPinnacleBossDefeated",
          "AtlasPassiveDoryaniPinnacleBossDefeated", "AtlasPassiveFinalPinnacleBossKilled",
          "AtlasPassiveMotherSoulPieceGuardianFemaleKilled", "AtlasPassiveMotherSoulPieceGuardianMaleKilled",
          "AtlasPassiveEndgameArbiterBossDefeated1"]


# ---------- unpacking ----------

def _extract(game: Path):
    if not BUN.is_file():
        raise GameDataError(f"нет {BUN.relative_to(gamedata.ROOT)}")
    patterns = [rf"^{re.escape(GRAPH)}$", rf"^{re.escape(CSD)}$", rf"^data/balance/({'|'.join(TABLES)})\.datc64$",
                rf"^data/balance/(russian/)?(passiveskills|{'|'.join(MASTER_TABLES)})\.datc64$"]
    RAW.mkdir(parents=True, exist_ok=True)
    res = subprocess.run([str(BUN), "extract-files", "--regex", str(game), str(RAW), *patterns],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise GameDataError(f"bun_extract_file: {res.stderr.strip() or res.stdout.strip()}")


# ---------- the graph ----------

def parse_graph(data: bytes) -> dict:
    """A .psg passive skill graph: root passives and groups (a centre, and passives on its orbits with connections)."""
    pos = 0

    def take(fmt: str):
        nonlocal pos
        value = struct.unpack_from(fmt, data, pos)
        pos += struct.calcsize(fmt)
        return value[0]

    take("<H")  # version
    pos += 11
    roots = [take("<q") for _ in range(take("<i"))]
    groups = []
    for _ in range(take("<i")):
        group = {"x": take("<f"), "y": take("<f")}
        pos += 9  # flags, two unknowns
        passives = []
        for _ in range(take("<i")):
            p = {"id": take("<i"), "orbit": take("<i"), "index": take("<i"), "links": []}
            for _ in range(take("<i")):
                p["links"].append(take("<i"))
                take("<i")  # the link's curve radius
            passives.append(p)
        group["passives"] = passives
        groups.append(group)
    if pos != len(data):
        raise GameDataError("неизвестный формат графа атласа")
    return {"roots": roots, "groups": groups}


def _angle(orbit: int, index: int) -> float:
    n = PER_ORBIT[orbit]
    degrees = ANGLES_16[index] if n == 16 else ANGLES_40[index] if n == 40 else 360 * index / n
    return math.radians(degrees)


# ---------- texts ----------

def _matches(limit, value) -> bool:
    lo, hi = limit
    if lo == "!":
        return value != hi
    return (lo == "#" or value >= lo) and (hi == "#" or value <= hi)


def _apply(spec: str, value: float) -> float:
    if spec == "negate":
        return -value
    if spec.startswith("divide_by_"):
        word = spec.removeprefix("divide_by_").split("_")[0]
        div = {"two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "twenty": 20, "fifty": 50, "one": 100,
               "hundred": 100, "thousand": 1000, "sixty": 60}.get(word)
        if spec.startswith("divide_by_one_hundred"):
            div = 100
        return value / div if div else value
    if spec.startswith("milliseconds_to_seconds"):
        return value / 1000
    if spec == "per_minute_to_per_second":
        return value / 60
    if spec.startswith("multiply_by_"):
        word = spec.removeprefix("multiply_by_").split("_")[0]
        return value * {"two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "one": 100}.get(word, 1)
    return value


def _number(v: float, plus: bool) -> str:
    text = f"{v:.2f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    return ("+" if plus and v >= 0 else "") + text


def describe(stats: list[tuple[str, int]], descs: dict, lang_key: str) -> list[str]:
    """The node's stat lines in one language (lang_key "en" or "want"), like the game's tooltip."""
    values = dict(stats)
    lines, done = [], set()
    for stat, _ in stats:
        if stat in done:
            continue
        idx = descs["index"].get(stat)
        entry = descs["entries"][idx - 1] if idx else None
        if not entry or not entry.get("stats") or not (entry.get(lang_key) or entry.get("en")):
            continue
        done.update(entry["stats"])
        vals = [values.get(s, 0) for s in entry["stats"]]
        for variant in entry.get(lang_key) or entry["en"]:
            if all(_matches(lim, v) for lim, v in zip(variant["limit"], vals)):
                shown = list(vals)
                for spec in variant.get("specs", []):
                    if isinstance(spec.get("v"), int) and 1 <= spec["v"] <= len(shown):
                        shown[spec["v"] - 1] = _apply(spec["k"], shown[spec["v"] - 1])
                text = variant["text"]
                text = re.sub(r"\{(\d*)(:\+?d)?\}", lambda m: _number(shown[int(m.group(1) or 0)] if int(m.group(1) or 0) < len(shown) else 0,
                                                                    "+" in (m.group(2) or "")), text)
                lines.extend(t for t in text.split("\n") if t.strip())
                break
    return lines


# ---------- building ----------

def build(game: Path | None = None, lang: str = "ru") -> dict:
    """Unpack the atlas tree from the game and write data/cache/game/atlas.json (both languages)."""
    game = game or gamedata.game_dir()
    if game is None:
        raise GameDataError("нужна установленная игра")
    _extract(game)
    balance = RAW / "data/balance"
    graph = parse_graph((RAW / GRAPH).read_bytes())
    cols = ["Id", "Icon", "Stats", "Stat1", "Stat2", "Stat3", "Stat4", "Stat5", "Stat6", "Stat7", "PassiveSkillNodeId",
            "Name", "Keystone", "Notable", "AtlasSubTree", "IsRootOfAtlas", "IsOnlyImage", "Requirement"]
    rows = read_table(balance / "passiveskills.datc64", cols)
    local = read_table(balance / gamedata.LANG_NAMES[lang].lower() / "passiveskills.datc64", ["Name"])
    stat_ids = [r["Id"] for r in read_table(balance / "stats.datc64", ["Id"])]
    subtrees = [r["Id"] for r in read_table(balance / "atlaspassiveskillsubtrees.datc64", ["Id"])]
    strings = read_table(balance / "clientstrings.datc64", ["Id", "Text"])
    local_strings = read_table(balance / gamedata.LANG_NAMES[lang].lower() / "clientstrings.datc64", ["Text"])
    requirements = {}  # requirement id -> its text in both languages
    descs = gamedata.parse_csd((RAW / CSD).read_bytes().decode("utf-16-le").lstrip("\ufeff"), lang)
    by_id = {r["PassiveSkillNodeId"]: (i, r) for i, r in enumerate(rows)}
    nodes, links = {}, set()
    for group in graph["groups"]:
        for p in group["passives"]:
            if p["id"] not in by_id:
                continue
            i, r = by_id[p["id"]]
            stats = [(stat_ids[s], v) for s, v in zip(r["Stats"], [r[f"Stat{n}"] for n in range(1, 8)])]
            a = _angle(p["orbit"], p["index"])
            req = r["Requirement"]
            if req is not None and req < len(strings):
                requirements[strings[req]["Id"]] = {"en": strings[req]["Text"], lang: local_strings[req]["Text"]}
            nodes[p["id"]] = {
                "id": p["id"], "x": round(group["x"] + math.sin(a) * RADII[p["orbit"]], 1),
                "y": round(group["y"] - math.cos(a) * RADII[p["orbit"]], 1),
                "name": {"en": r["Name"], lang: local[i]["Name"] if i < len(local) else r["Name"]},
                "icon": r["Icon"], "stats": [s for s, _ in stats],
                "text": {"en": describe(stats, descs, "en"), lang: describe(stats, descs, "want")},
                "kind": "keystone" if r["Keystone"] else "notable" if r["Notable"] else "image" if r["IsOnlyImage"] else "small",
                "part": subtrees[r["AtlasSubTree"]] if r["AtlasSubTree"] is not None and r["AtlasSubTree"] < len(subtrees) else "Main",
                "root": bool(r["IsRootOfAtlas"]),
                "req": strings[req]["Id"] if req is not None and req < len(strings) else ""}
            for other in p["links"]:
                links.add(tuple(sorted((p["id"], other))))
    order = {k: i for i, k in enumerate(STAGES)}
    stages = [{"id": k, "text": requirements.get(k, {})} for k in sorted({n["req"] for n in nodes.values()},
                                                                      key=lambda k: (order.get(k, len(STAGES)), k))]
    out = {"version": VERSION, "lang": lang, "nodes": list(nodes.values()), "stages": stages,
           "links": [[a, b] for a, b in sorted(links) if a in nodes and b in nodes]}
    out["masters"] = _masters(balance, lang, stat_ids, descs)
    _convert_icons(game, {n["icon"] for n in nodes.values() if n["icon"]})
    CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


# what a master's keystone is for, found by its stats (the interface names the tags: atMT_<tag>); "start" marks the ones
# worth having from the first maps: more revives, more and stronger rare monsters, exceptional items
MASTER_TAGS = [
    ("safety", r"portals|revive"),
    ("pinnacle", r"pinnacle"),
    ("tablets", r"tablet|waystone|prefix_or_suffix"),
    ("strongbox", r"strongbox|chest"),
    ("explore", r"reveal|accessible|citadel|terraformer|hidden_map|atlas_event"),
    ("risky", r"irradiated|corrupt_or_cleansed"),
    ("mechanics", r"expedition|rogue_exile|azmeri|tormented_spirit|essence|extra_content|added_content|unique_monsters_gain"),
    ("loot", r"rare_packs|rare_monster_modifiers|magic_monster_additional|rarity|exceptional|potency|unique_item|powerful_boss|replaced_by_random_map_boss"),
]
START = r"^map_contains_\+_portals$|^map_number_of_rare_packs_\+%$|^map_items_drop_exceptional_chance_\+%$|^map_powerful_boss_chance_%$"


def _masters(balance: Path, lang: str, stat_ids: list[str], descs: dict) -> list[dict]:
    folder = gamedata.LANG_NAMES[lang].lower()
    if not (balance / "atlasclasspassives.datc64").is_file():
        return []
    classes = read_table(balance / "atlasclasspassiveclasses.datc64", ["Id", "Description"])
    local_classes = read_table(balance / folder / "atlasclasspassiveclasses.datc64", ["Description"])
    rows = read_table(balance / "atlasclasspassives.datc64", ["Id", "Class", "Stats", "StatValues", "Name", "KeystoneArt"])
    local = read_table(balance / folder / "atlasclasspassives.datc64", ["Name"])
    out = {}
    for i, r in enumerate(rows):
        c = r["Class"]
        if c is None or c >= len(classes) or not classes[c]["Id"]:
            continue
        m = out.setdefault(classes[c]["Id"], {"id": classes[c]["Id"], "title": {"en": classes[c]["Description"],
                           lang: local_classes[c]["Description"]}, "nodes": []})
        stats = [(stat_ids[s], v) for s, v in zip(r["Stats"], r["StatValues"]) if s < len(stat_ids)]
        ids = [s for s, _ in stats]
        tags = [t for t, pat in MASTER_TAGS if any(re.search(pat, s) for s in ids)]
        m["nodes"].append({"id": r["Id"], "name": {"en": r["Name"], lang: local[i]["Name"] if i < len(local) else r["Name"]},
                           "text": {"en": describe(stats, descs, "en"), lang: describe(stats, descs, "want")},
                           "tags": tags[:2], "start": any(re.search(START, s) for s in ids), "stats": ids})
    order = ["Hilda", "Doryani", "Jado"]
    return sorted(out.values(), key=lambda m: order.index(m["id"]) if m["id"] in order else 9)


def _convert_icons(game: Path, paths: set[str]):
    """The nodes' pictures icons.build leaves out: the clusters' centre art (nodes without a name) and nodes whose
    name another node's picture already took."""
    from . import icons
    icons.convert(game, paths)


def load(lang: str = "ru", game: Path | None = None) -> dict | None:
    """The built tree; None when there is none, it was built by an older poe2lab or before the game's last patch."""
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    index = game / "Bundles2" / "_.index.bin" if game else None
    if index and index.is_file() and index.stat().st_mtime > CACHE.stat().st_mtime:
        return None
    return data if data.get("version") == VERSION and data.get("lang") == lang else None


# ---------- the guide ----------

def _neighbours(tree: dict) -> dict[int, set[int]]:
    near: dict[int, set[int]] = {n["id"]: set() for n in tree["nodes"]}
    for a, b in tree["links"]:
        near[a].add(b)
        near[b].add(a)
    return near


def route(tree: dict) -> dict:
    """The key nodes of the main tree in the order to take them, each with the nodes on the way and the points spent
    so far: from the root, the closest not yet reached target first (breadth-first search from everything taken)."""
    near = _neighbours(tree)
    nodes = {n["id"]: n for n in tree["nodes"]}
    main = {i for i, n in nodes.items() if n["part"] == "Main" and n["kind"] != "image"}
    root = next((i for i in main if nodes[i]["root"]), None)

    def found_by(pairs):
        out = []
        for gid, pattern in pairs:
            ids = [i for i in main if any(re.search(pattern, s) for s in nodes[i]["stats"])]
            if ids:
                out.append({"id": gid, "nodes": sorted(ids), "any": gid in ANY_ONE})
        return out

    groups, useful = found_by(KEY_GROUPS), found_by(USEFUL)
    if root is None:
        return {"root": None, "groups": groups, "useful": useful, "steps": []}
    taken, steps, spent = {root}, [], 0
    wanted = {i: g["id"] for g in groups for i in g["nodes"]}
    while wanted.keys() - taken:
        prev, queue, found = {i: None for i in taken}, deque(taken), None
        while queue and found is None:
            cur = queue.popleft()
            for nxt in near[cur]:
                if nxt in main and nxt not in prev:
                    prev[nxt] = cur
                    if nxt in wanted and nxt not in taken:
                        found = nxt
                        break
                    queue.append(nxt)
        if found is None:  # the rest cannot be reached through the main tree
            break
        path, cur = [], found
        while cur not in taken:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        taken.update(path)
        spent += len(path)
        steps.append({"node": found, "group": wanted[found], "path": path, "points": spent})
        if wanted[found] in ANY_ONE:  # one node of such a group is enough: the others are no longer targets
            for i in [i for i, g in wanted.items() if g == wanted[found] and i != found]:
                del wanted[i]
    return {"root": root, "groups": groups, "useful": useful, "steps": steps}


def _master_art() -> dict[str, dict[str, str]]:
    """Each atlas master's portrait and tab icon (UI art: the texture next to the name the table keeps)."""
    # "Art/2DArt/UIImages/..." -> its texture "Art/Textures/Interface/2D/2DArt/UIImages/....dds" (as uiimages lays out)
    tex = lambda p: "Art/Textures/Interface/2D/" + p.removeprefix("Art/") + ".dds" if p else ""  # noqa: E731
    try:
        rows = read_table(RAW / "data/balance/atlasclasspassiveclasses.datc64", ["Id", "MasterNormal", "TabActive"])
    except (OSError, KeyError):
        return {}
    return {r["Id"]: {"portrait": tex(r["MasterNormal"]), "icon": tex(r["TabActive"])}
            for r in rows if r["Id"] and r["MasterNormal"]}


def guide(game: Path | None = None) -> dict:
    """The tree (names and texts in English and Russian) and what to take first; built from the game when needed."""
    from . import icons  # the nodes' pictures, converted with the other passives' (icons.build)
    tree = load("ru", game) or build(game, "ru")
    for n in tree["nodes"]:
        file = icons._file_name(n["icon"]) if n.get("icon") else ""
        n["img"] = file if file and (icons.ICONS / file).is_file() else ""
    art = _master_art()
    if game and any(not icons.art_file(p) for p in art.values() for p in p.values()):
        icons.convert(game, {p for a in art.values() for p in a.values()})
    for m in tree.get("masters", []):
        m["art"] = {k: icons.art_file(p) for k, p in art.get(m["id"], {}).items()}
    return {"tree": tree, "route": route(tree)}
