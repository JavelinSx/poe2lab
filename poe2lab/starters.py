"""Starters: how players' guides level a class - the program's levelling ways lean on them before the ones it makes
from the gem data (poe2lab.analysis.leveling.ways).

Two kinds of source, both from the player's research base (data/transcripts, see its _tools):
- maxroll's levelling guides: their planner's "Campaign" profile keeps the gems step by step ("Level 2: Clearfell",
  "Level 8: ...") - each skill from the level the guide takes it at;
- starter videos with a build (a link or the author's .build stages): the build's skills, each from the level its
  uncut gem can be had at (the earliest stage when there are stages), and the author's levelling advice.
Votes: how many starter sources (videos and guides, overviews included) speak of the starter's main skill.

build() makes data/starters.json once (it fetches the planners); the program only reads it."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STARTERS = ROOT / "data" / "starters.json"
TRANSCRIPTS = ROOT / "data" / "transcripts"
# a source is about starting a league / levelling
_STARTER = re.compile(r"стартер|старт|starter|leveling|levelling|кач\b|\(кач\)|новичк|сборка 1 дня", re.I)
_LEVEL = re.compile(r"(?:level\s*|^)(\d+)", re.I)
_ACT = re.compile(r"\bact\s*(\d)", re.I)
# a step named by its part of the game: the level it starts at (poe2lab.analysis.leveling.stages)
ACT_LEVELS = {1: 1, 2: 16, 3: 33, 4: 46, 5: 54}
_INTERLUDE, _MAPS = re.compile(r"interlude", re.I), re.compile(r"maps", re.I)
_ENDGAME = re.compile(r"endgame|engame", re.I)  # past levelling: not a starter's step
TIP_KINDS = {"leveling", "start", "order"}
# maxroll's class ids (a planner profile's "class"); its ascendancy ids are PoB's internal ones (Monk2 = Invoker)
MAXROLL_CLASSES = {"StrFourb": "Warrior", "DexFour": "Ranger", "DexFourb": "Huntress", "IntFour": "Witch",
                   "IntFourb": "Sorceress", "StrDexFourb": "Mercenary", "DexIntFourb": "Monk", "StrIntFourb": "Druid"}
MAX_TIPS = 4


def load() -> list[dict]:
    try:
        return json.loads(STARTERS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def for_class(cls: str, ascendancy: str | None = None) -> list[dict]:
    """The class's starters: the build's ascendancy first, then the most spoken of."""
    return sorted((s for s in load() if s["class"] == cls),
                  key=lambda s: (ascendancy not in s["ascendancies"], -s["votes"], s["source"] != "maxroll"))


# ---------- making data/starters.json ----------

def _gem_names(engine) -> tuple[dict, dict]:
    """(gem id -> catalog entry, name -> catalog entry); maxroll writes "Metadata/Items/Gem/" for some of them."""
    catalog = engine.gem_catalog()
    by_id = {}
    for g in catalog:
        by_id[g["id"].lower()] = g
        by_id[g["id"].lower().replace("/gems/", "/gem/")] = g
    return by_id, {g["name"]: g for g in catalog}


def _levels_with(g: dict) -> bool:
    """A skill one kills with while levelling: not a support, buff, offering, curse or mark (beyond the levelling
    ways' own rule, poe2lab.analysis.leveling.way_of)."""
    from .analysis.leveling import way_of
    return (not g["support"] and way_of(g) is not None
            and not {"AppliesCurse", "Mark", "Buff", "Offering"} & set(g["types"]))


def _first_levels(steps: list[dict], by_name: dict) -> list[dict]:
    """Each skill gem of the steps one levels with, from the first level it is used at."""
    seen = {}
    for st in steps:
        for group in st["gems"]:
            for name in group:
                g = by_name.get(name)
                if g and _levels_with(g) and name not in seen:
                    seen[name] = st["level"]
    return [{"name": n, "level": lv, "tier": by_name[n]["tier"]} for n, lv in sorted(seen.items(), key=lambda x: x[1])]


PLANNERS = ROOT / "data" / "cache" / "maxroll"


def _planner(pid: str) -> dict:
    """A maxroll planner, kept on disk (a guide's planner changes rarely; delete the file to fetch it again);
    asked three times - maxroll drops a connection now and then."""
    from . import maxroll
    key = PLANNERS / f"{pid}.json"
    if key.exists():
        return json.loads(key.read_text(encoding="utf-8"))
    for attempt in range(3):
        try:
            planner = maxroll.fetch(pid)
            break
        except maxroll.MaxrollError:
            if attempt == 2:
                raise
    PLANNERS.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps(planner, ensure_ascii=False), encoding="utf-8")
    return planner


def _maxroll(engine, by_id: dict, by_name: dict) -> list[dict]:
    import gzip
    from . import maxroll, newbuild
    ascendancy = {a["id"]: a["name"] for c in newbuild.classes(engine) for a in c["ascendancies"]}
    out = []
    for raw in sorted((TRANSCRIPTS / "maxroll" / "raw").glob("*.html.gz")):
        slug = raw.name.removesuffix(".html.gz")
        claims_file = TRANSCRIPTS / "maxroll" / f"{slug}.claims.json"
        claims = json.loads(claims_file.read_text(encoding="utf-8")) if claims_file.exists() else {}
        if not _STARTER.search(slug + " " + claims.get("title", "")):
            continue
        pid = maxroll.planner_id(gzip.decompress(raw.read_bytes()).decode("utf-8", "replace"))
        if not pid:
            continue
        planner = _planner(pid)
        for index, prof in enumerate(planner["data"]["profiles"]):
            if index and "endgame" in (prof.get("name") or "").lower():
                continue
            steps, level = [], 1
            for st in prof.get("skills", {}).get("steps") or []:
                name = st.get("name") or ""
                if _ENDGAME.search(name):
                    break
                m, act = _LEVEL.search(name), _ACT.search(name)
                level = (int(m.group(1)) if m else ACT_LEVELS.get(int(act.group(1)), level) if act
                         else 54 if _INTERLUDE.search(name) else 65 if _MAPS.search(name) else level)
                gems = [[by_id[x["id"].lower()]["name"] for x in grp.get("gems") or [] if x and x.get("id", "").lower() in by_id]
                        for grp in st.get("skills") or []]
                steps.append({"level": level, "name": (st.get("name") or "").split(":", 1)[-1].strip(),
                              "gems": [g for g in gems if g]})
            if len({st["level"] for st in steps}) < 2:  # not a step-by-step levelling (one endgame set of gems)
                continue
            cls = MAXROLL_CLASSES.get(prof.get("class") or "")
            if not cls:
                continue
            skills = _first_levels(steps, by_name)
            # the main skill: the most linked skill of the last step (its group has the most supports)
            heads = [grp for grp in steps[-1]["gems"] if grp and _levels_with(by_name[grp[0]])]
            main = max(heads, key=len)[0] if heads else (skills[-1]["name"] if skills else "")
            out.append({"id": f"maxroll:{slug}:{index}", "source": "maxroll",
                        "title": claims.get("title") or planner.get("name") or slug,
                        "profile": prof.get("name") or "", "url": f"https://maxroll.gg/poe2/build-guides/{slug}",
                        "class": cls, "ascendancies": [a for a in [ascendancy.get(prof.get("ascendancy"))] if a],
                        "mainSkill": main, "skills": skills, "steps": steps,
                        "tips": [c["says"] for c in claims.get("claims", []) if c.get("kind") in TIP_KINDS | {"passive", "gear"}][:MAX_TIPS],
                        "patch": claims.get("patch", "")})
    return out


def _videos(engine, by_name: dict) -> list[dict]:
    from .analysis.skills import available_level
    out = []
    for folder in sorted((p for p in TRANSCRIPTS.iterdir() if p.name.isdigit()), key=lambda p: int(p.name)):
        claims = json.loads((folder / "claims.json").read_text(encoding="utf-8"))
        if claims.get("topic") not in (None, "build") or not _STARTER.search(claims.get("title", "")):
            continue
        stages = sorted(folder.glob("build.stage-*.pob.txt"))
        code_file = stages[0] if stages else folder / "build.pob.txt"
        if not code_file.exists() or (folder / "build.source.json").exists():  # a ladder stand-in is not the author's
            continue
        engine.load_code(code_file.read_text(encoding="utf-8").strip())
        info = engine.info()
        skills, seen = [], set()
        for g in engine.skill_groups():
            for gem in g["gems"]:
                cat = by_name.get(gem["name"])
                if gem["support"] or not cat or not _levels_with(cat) or gem["name"] in seen:
                    continue
                lv = available_level(gem)
                if lv is not None:
                    seen.add(gem["name"])
                    skills.append({"name": gem["name"], "level": lv, "tier": cat["tier"]})
        skills.sort(key=lambda s: s["level"])
        out.append({"id": f"video:{claims['build']}", "source": "video", "title": claims["title"], "profile": "",
                    "url": "", "class": info["class"], "ascendancies": [a for a in [info.get("ascendancy")] if a],
                    "mainSkill": engine.main_skill() or "", "skills": skills, "steps": [],
                    "tips": [c["says"] for c in claims["claims"] if c.get("kind") in TIP_KINDS][:MAX_TIPS],
                    "patch": claims.get("patch", "")})
    return out


def _votes(starters: list[dict]):
    """How many starter sources speak of each starter's main skill (data/transcripts/mechanics.json)."""
    base = json.loads((TRANSCRIPTS / "mechanics.json").read_text(encoding="utf-8"))
    starter_sources = {s["id"] for s in base["sources"] if _STARTER.search((s.get("title") or "") + " " + s["id"])}
    for s in starters:
        mentions = set(base["elements"].get(s["mainSkill"], {}).get("sources", [])) & starter_sources
        s["votes"] = len(mentions | ({s["id"].rsplit(":", 1)[0]} if s["source"] == "maxroll" else {s["id"]}))


def build(engine) -> list[dict]:
    by_id, by_name = _gem_names(engine)
    starters = _maxroll(engine, by_id, by_name) + _videos(engine, by_name)
    _votes(starters)
    STARTERS.write_text(json.dumps(starters, ensure_ascii=False, indent=1), encoding="utf-8")
    return starters


if __name__ == "__main__":
    import sys
    from .engine import PobEngine
    sys.stdout.reconfigure(encoding="utf-8")
    for s in build(PobEngine()):
        print(s["id"], "|", s["class"], s["ascendancies"], "|", s["mainSkill"], "| votes", s["votes"], "|",
              [(x["name"], x["level"]) for x in s["skills"][:6]])
