"""Local web interface: one loaded build, heavy analyses cached, everything served as JSON to a static page."""
import json
import re
import threading
import uuid
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..analysis.changes import capture as capture_build, diff as build_diff
from ..analysis.items import breakeven, compare
from ..analysis.skills import available_level, better_supports, build_view as skill_build_view, leveling_view as skill_leveling_view
from ..analysis.uniques import suggest as suggest_uniques
from ..analysis.report import MODES, build_report, defence_weights
from ..analysis.report import score as report_score
from ..analysis.gradients import metric_changes
from ..analysis.tree import analyse as analyse_tree
from ..analysis.tree import ascendancy as tree_ascendancy
from ..analysis.tree import mechanic_packages
from ..analysis.tree import optimize as optimize_tree
from ..analysis.tree import take_package
from ..analysis import leveling, quests as quest_rewards
from ..analysis.slots import AFFIX_LIMIT, craft_path, plan_all, plan_slot
from ..analysis.sockets import adds_stats, plan_sockets, refusal as rune_refusal
from ..analysis.threats import IMMUNE_HIT, MapProfile, survivable_hits
from ..analysis.triggers import trigger_view
from ..analysis.versus import versus
from ..assistant import (Assistant, LLMConfig, LLMError, Toolbox, build_context, build_glossary, list_models,
                         make_client)
from ..assistant.agent import STYLES
from ..assistant import prompt as prompt_builder
from ..assistant.providers import BY_ID, PROVIDERS, key_hint, load_settings, save_settings
from ..data.moddb import ModDB
from ..economy import ladder, trade
from ..economy import ninja
from ..economy.ninja import PriceBook
from ..engine import PobEngine, PobError
from ..engine.pobcode import encode_pob_code
from .. import (buildplanner, crafting, feedback, gamedata, gemcraft, glossary, icons, itemcraft, itemtext, jewelcraft,
               journal, library, lootfilter, mcpconnect, newbuild, pobapp, quality)
from ..i18n import _get as _trade_data
from ..i18n import dictionary as translation_dictionary
from ..i18n import pob_line, stat_templates
from ..knowledge import collect as collect_mechanics
from ..logs import log, log_file, setup as setup_log, tail as log_tail
from ..pobfiles import PROJECT_BUILDS, resolve_build
from ..profile import CORRECTION_BLOCK, BuildProfile, describe as describe_profile, open_build

STATIC = Path(__file__).resolve().parent / "static"
SLOTS_ORDER = ["Weapon 1", "Helmet", "Body Armour", "Gloves", "Boots", "Amulet", "Ring 1", "Ring 2", "Belt"]


class Session:
    """The build currently open in the UI. The PoB engine is single-threaded, so every use takes the lock."""

    def __init__(self):
        self.lock = threading.Lock()
        self.path: Path | None = None
        self.engine = None
        self.bp: BuildProfile | None = None
        self.cache: dict = {}
        self.assistant: Assistant | None = None
        self.toolbox: Toolbox | None = None
        self._prices: PriceBook | None | bool = False
        self.ref: tuple | None = None  # (name, engine, profile) of the reference build for comparisons
        self.main: Path | None = None  # the player's own character of the build (builds/<name>.main.txt), if any
        self.plan: dict | None = None  # passive tree edits on top of the build (see /api/tree/*)
        self.level: int | None = None  # character level: sets the enemy (see MapProfile.for_level)
        self.picked_filter: Path | None = None  # the player's filter chosen in the file dialog
        self.mtime = 0.0  # the build file's time when it was read: a newer file means PoB saved it again

    def require(self, build: str | None = None):
        if self.engine is None:
            raise HTTPException(409, "сначала откройте билд")
        if build is not None and build != self.path.stem:
            raise HTTPException(409, f"открыт другой билд ({self.path.stem}); запрос для {build} отменён")

    @property
    def profile(self) -> MapProfile:
        # the enemy of the character's stage: an area of its level while levelling, maps from level 65
        return MapProfile.for_level(self.level, rage=self.bp.rage, mana_sustained=self.bp.mana_sustained)

    def load(self, name: str, group: int | None = None, skill: int | None = None):
        """Open a build: the player's own character when the build has one (with the build's profile) - what every
        analysis and edit works on - else the build itself. The build as recorded is `recorded()`."""
        self.path = resolve_build(name)
        main = library.main_path(self.path.stem)
        self.main = main if main.exists() else None
        self.mtime = (self.main or self.path).stat().st_mtime
        self.engine, self.bp = open_build(self.main or self.path, group, skill,
                                          profile_of=self.path if self.main else None)
        if self.ref is not None and self.ref[0] == RECORDED:
            self.ref = None
        self.level = self.engine.info()["level"]
        self.plan = None
        self.cache.clear()
        self.assistant = self.toolbox = None

    def file_changed(self) -> bool:
        try:
            return self.path is not None and (self.main or self.path).stat().st_mtime > self.mtime
        except OSError:
            return False

    def cached(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    def db(self) -> ModDB:
        return self.cached("db", lambda: ModDB.from_engine(self.engine))

    def jewel_db(self) -> ModDB:
        """Jewel affixes: a jewel copied from the Russian client is read by them (poe2lab.itemtext)."""
        return self.cached("jewel-db", lambda: ModDB.from_engine(self.engine, sets=("Jewel", "Desecrated")))

    def prices(self) -> PriceBook | None:
        if self._prices is False:
            try:
                # the league the player chose in the interface; else the build profile's; else poe.ninja's current
                self._prices = PriceBook.load(ninja.chosen_league() or (self.bp.league if self.bp else None))
            except OSError:
                self._prices = None
        return self._prices


RECORDED = "@build"  # the reference name of the open build as its file records it (the guide, the gear before edits)
session = Session()
app = FastAPI(title="poe2lab")
app.add_middleware(GZipMiddleware, minimum_size=4096)  # the RU dictionary is several MB
setup_log()


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    """An error nothing expected: into the log with its traceback under a short code; the page gets the code and the
    error in one line, to show it and to send it with a report."""
    code = uuid.uuid4().hex[:6]
    log.error("%s %s?%s failed [%s]", request.method, request.url.path, request.url.query, code, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}", "errorId": code})

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver"}
CSRF_HEADER = "x-poe2lab"


@app.middleware("http")
async def local_only(request: Request, call_next):
    """The server holds API keys and drives the engine: answer only to this machine's page.
    Host check blocks DNS rebinding; the custom header on state-changing calls forces a CORS preflight,
    which other sites fail, so a web page elsewhere cannot change settings or send the key anywhere."""
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
    if host not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "forbidden host"}, status_code=403)
    if request.url.path.startswith("/api/") and request.method not in ("GET", "HEAD") \
            and request.headers.get(CSRF_HEADER) != "1":
        return JSONResponse({"detail": "missing X-Poe2lab header"}, status_code=403)
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"  # a local app: always pick up the current page and scripts
    return response


def _json(obj):
    """Round floats and make dataclasses/NaN JSON-safe."""
    return json.loads(json.dumps(obj, default=lambda o: asdict(o) if hasattr(o, "__dataclass_fields__") else str(o),
                                 allow_nan=False))


def _errors(fn):
    try:
        return fn()
    except (PobError, FileNotFoundError, ValueError) as err:
        log.warning("refused: %s", err)
        raise HTTPException(400, str(err))


class LoadRequest(BaseModel):
    name: str
    group: int | None = None
    skill: int | None = None


class CompareRequest(BaseModel):
    slot: str
    text: str
    breakeven: str | None = None


class ChatRequest(BaseModel):
    message: str
    lang: str = "ru"


@app.get("/api/status")
def status():
    cfg = LLMConfig.current()
    return {"loaded": session.engine is not None, "build": session.path.stem if session.path else None,
            "buildChanged": session.engine is not None and session.file_changed(),
            "llm": {"configured": cfg is not None, "model": cfg.model if cfg else None,
                    "provider": cfg.provider if cfg else None}}


stop_hook = None  # set by `python -m poe2lab ui`: ends the server (the interface's Stop button)


@app.post("/api/shutdown")
def shutdown():
    """The interface's Stop button: the server ends right after this answer - start.bat runs it with no window of
    its own, so this is how a player stops it. A server started otherwise (tests, another host) refuses."""
    if stop_hook is None:
        raise HTTPException(409, "сервер запущен не через poe2lab ui — остановите его там, где запускали")
    threading.Timer(0.5, stop_hook).start()  # the answer reaches the page first
    return {"ok": True}


class LLMSettings(BaseModel):
    provider: str
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # None/"" keeps the stored key
    clear_key: bool = False
    style: str | None = None  # "short" / "detailed" answers


def _llm_view() -> dict:
    s = load_settings()
    keys = s.get("keys") or {}
    return {
        "provider": s.get("provider"), "model": s.get("model"), "baseUrl": s.get("base_url"),
        "style": s.get("style", "short"),
        "providers": [{"id": p.id, "name": p.name, "baseUrl": p.base_url, "defaultModel": p.default_model,
                       "needsKey": p.needs_key, "note": p.note, "keyHint": key_hint(keys.get(p.id))}
                      for p in PROVIDERS],
        "active": status()["llm"],
    }


_dictionaries: dict = {}


_game_lock = threading.Lock()


def _game_texts(lang: str) -> Path | None:
    """Stat descriptions in `lang` unpacked from the installed game (built once and again after a game patch,
    ~15 s); None when there is no game install or extractor, so everything falls back to the English lines."""
    if lang not in gamedata.LANG_NAMES:
        return None
    with _game_lock:
        can_unpack = gamedata.game_dir() and gamedata.BUN.is_file()
        try:
            if gamedata.stale(lang) and can_unpack:
                gamedata.build(lang)
            elif can_unpack and not icons.INDEX.is_file():  # texts unpacked before icons existed
                icons.build()
            if gamedata.refresh_derived(lang):
                _dictionaries.pop(lang, None)
        except (gamedata.GameDataError, OSError) as err:
            gamedata.last_error = str(err)
            return None
    return gamedata.statdesc_dir(lang) if gamedata.available(lang) else None


@app.get("/api/gamedata")
def gamedata_status():
    """Why names are (not) Russian: the game install, the extractor, the unpacked texts, GGG's trade data."""
    st = gamedata.status("ru")
    st["tradeData"] = bool(_dictionaries.get("ru", {}).get("available", True))
    return st


class GameDataRequest(BaseModel):
    game_dir: str | None = None  # a folder the player points at; empty = search as usual


@app.post("/api/gamedata")
def gamedata_build(req: GameDataRequest):
    """Unpack the Russian texts and icons now (downloading the extractor if needed), optionally from a folder the
    player chose."""
    with _game_lock:
        try:
            if req.game_dir and req.game_dir.strip():
                gamedata.save_game_dir(Path(req.game_dir.strip().strip('"')))
            game = gamedata.game_dir()
            if game is None:
                raise gamedata.GameDataError("Path of Exile 2 не найдена — укажите папку игры")
            gamedata.ensure_bun()
            gamedata.build("ru", game)
            gamedata.last_error = None
        except (gamedata.GameDataError, OSError) as err:
            gamedata.last_error = str(err)
            raise HTTPException(400, str(err))
    _dictionaries.pop("ru", None)  # the next dictionary request picks up the new names and templates
    return gamedata_status()


@app.get("/api/icons")
def icon_index():
    """English skill / passive name -> icon file under /icons (empty without the game's files)."""
    _game_texts("ru")
    return icons.load_index()


@app.get("/api/i18n/{lang}")
def i18n(lang: str):
    """Official game texts for the UI language (stat templates, names); empty if GGG's data is unreachable."""
    if lang not in _dictionaries:
        _game_texts(lang)
        try:
            _dictionaries[lang] = {"available": True, **translation_dictionary(lang)}
        except ValueError as err:
            raise HTTPException(400, str(err))
        except OSError:
            return {"available": False, "stats": {}, "names": gamedata.load_names(lang)}
    return _dictionaries[lang]


_mod_catalog: dict = {}


def _catalog(lang: str) -> list[dict]:
    """Official stat templates PoB can actually use, like the trade filter's list (built once, ~3 s)."""
    if lang not in _mod_catalog:
        session.require()
        try:
            templates = stat_templates(lang)
        except OSError:
            raise HTTPException(503, "справочник модов недоступен (нет связи с pathofexile.com)")
        engine = session.engine
        _mod_catalog[lang] = [t | {"line": pob_line(t["en"])} for t in templates if engine.can_parse_mod(pob_line(t["en"]))]
    return _mod_catalog[lang]


@app.get("/api/mods/search")
def mods_search(q: str, lang: str = "ru", limit: int = 25):
    """Mods whose text (in English or the UI language) contains every word of the query."""
    # word stems, so Russian case endings still match: "скорость" finds "скорости", "умение" finds "умений"
    words = [w[:-2] if len(w) >= 6 else w[:-1] if len(w) == 5 else w for w in q.lower().split() if w]
    if not words:
        return {"results": []}
    with session.lock:
        catalog = _catalog(lang)
    hits = []
    for t in catalog:
        text = (t["en"] + " | " + t.get(lang, "")).lower()
        if all(w in text for w in words):
            local = t.get(lang, t["en"]).lower()
            rank = (not local.startswith(words[0]) and not t["en"].lower().startswith(words[0]), len(t["en"]))
            hits.append((rank, t))
    hits.sort(key=lambda x: x[0])
    return {"results": [{"en": t["en"], "text": t.get(lang, t["en"]), "line": t["line"]} for _, t in hits[:limit]]}


# Game wordings of skill effects that become a PoB mod line once the skill-side framing is dropped.
_REWRITES = [
    (re.compile(r"^(?:Buff grants |Grants )?(\d+(?:\.\d+)?)% of damage Gained as (\w+) damage$", re.I),
     r"Gain \1% of Damage as Extra \2 Damage"),
    (re.compile(r"^Buff grants (\d+(?:\.\d+)?) (\w+) regenerated per second$", re.I), r"Regenerate \1 \2 per second"),
]
_FRAMES = re.compile(r"^(?:Buff grants |Grants |Supported Skills (?:have |deal |grant )?|Skill (?:has |deals )?|"
                     r"You and Allies in your Presence (?:have |gain )?)", re.I)
_STOP = {"with", "your", "have", "from", "that", "this", "skills", "supported", "skill", "while", "when", "for",
         "each", "grants", "buff", "gain", "gained", "seconds", "second", "enemies", "enemy", "increased", "more",
         "less", "reduced", "used", "using"}
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _suggest(text: str, lang: str, limit: int = 8) -> dict:
    """A PoB line for a game line PoB does not calculate: the line itself or a known rewrite if PoB parses it,
    else the closest parseable mods by shared words, with the line's numbers filled in where they fit."""
    engine = session.engine
    text = " ".join(text.split())
    tries = [text]
    for pattern, repl in _REWRITES:
        if pattern.match(text):
            tries.append(pattern.sub(repl, text))
    stripped = _FRAMES.sub("", text)
    if stripped != text and stripped:
        tries.append(stripped[0].upper() + stripped[1:])
    direct = next((t for t in tries if engine.can_parse_mod(t)), None)
    words = {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in _STOP}
    numbers = _NUM.findall(text)
    scored = []
    for t in _catalog(lang):
        en = t["en"].lower()
        if en.startswith("allocates "):  # passive-notable allocation mods: never an equivalent of an effect
            continue
        score = sum(1 for w in words if w in en)
        if score:
            scored.append((-score, len(en), t))
    scored.sort(key=lambda x: (x[0], x[1]))
    out, seen = [], set()
    for _, _, t in scored:
        if len(out) >= limit:
            break
        shown = t.get(lang, t["en"])
        if shown in seen:  # "Gain 5 Rage on Hit" and "Grants 5 Rage on Hit" read the same to the player
            continue
        seen.add(shown)
        slots = t["en"].count("#")
        line = pob_line(t["en"], numbers[:slots]) if slots and len(numbers) >= slots else t["line"]
        if not engine.can_parse_mod(line):
            line = t["line"]
        out.append({"en": t["en"], "text": t.get(lang, t["en"]), "line": line})
    return {"direct": direct, "suggestions": out}


@app.get("/api/mods/suggest")
def mods_suggest(text: str, lang: str = "ru"):
    with session.lock:
        session.require()
        return _suggest(text, lang)


@app.get("/api/llm")
def llm_settings():
    return _llm_view()


@app.put("/api/llm")
def save_llm(req: LLMSettings):
    if req.provider not in BY_ID:
        raise HTTPException(400, "неизвестный провайдер")
    if req.provider == "custom" and not (req.base_url or "").startswith(("http://", "https://")):
        raise HTTPException(400, "для своего провайдера нужен адрес API (http:// или https://)")
    s = load_settings()
    keys = dict(s.get("keys") or {})
    if req.clear_key:
        keys.pop(req.provider, None)
    elif req.api_key:
        keys[req.provider] = req.api_key.strip()
    s.update({"provider": req.provider, "model": (req.model or "").strip() or BY_ID[req.provider].default_model,
              "base_url": (req.base_url or "").strip() or None, "keys": keys})
    if req.style in STYLES:
        s["style"] = req.style
    save_settings(s)
    session.assistant = session.toolbox = None  # next question uses the new model
    return _llm_view()


@app.get("/api/llm/models")
def llm_models():
    cfg = LLMConfig.from_settings()
    if cfg is None:
        raise HTTPException(400, "сначала выберите провайдера и сохраните ключ")
    try:
        return {"models": list_models(cfg)}
    except LLMError as err:
        raise HTTPException(502, str(err))


@app.get("/api/builds")
def builds():
    return library.entries()


@app.get("/api/builds/hidden")
def builds_hidden():
    return {"count": library.hidden_count()}


class AddBuildRequest(BaseModel):
    name: str = ""
    code: str  # PoB code, a pobb.in link, or the game's build planner file (.build: Mobalytics, PoB's export)


@app.post("/api/builds")
def add_build(req: AddBuildRequest):
    return _add_build(req.name, req.code)


def _add_build(name: str, code: str) -> dict:
    report = None
    if buildplanner.parse(code) is not None:
        # a build planner file: PoB builds it in an engine of its own (the open build stays as it is)
        try:
            code, report = buildplanner.to_code(code, PobEngine())
        except (buildplanner.BuildPlannerError, PobError) as err:
            raise HTTPException(400, f"не удалось собрать билд из файла планировщика: {err}")
    if not name.strip() and report and report["name"]:
        name = re.sub(r"\s+", " ", re.sub(r"[^\w\- .()]", " ", report["name"])).strip()[:60]
    try:
        name = library.add(name, code)
    except library.LibraryError as err:
        raise HTTPException(400, str(err))
    if report:
        # the guide's own levels, notes and source stay with the build: the levelling view and the export use them
        library.save_profile(name, {"planner": report.pop("plan")})
    return {"name": name, "report": report}


# ---------- the game's build planner folder ----------
class PlannerExport(BaseModel):
    overwrite: bool = False
    lang: str = "ru"
    who: str = ""  # the class, ascendancy and level as the page shows them (its own translations)


class PlannerImport(BaseModel):
    file: str


@app.get("/api/planner")
def planner_files():
    """The .build files in the game's planner folder (the game shows them in its build planner)."""
    folder = buildplanner.planner_dir()
    files = sorted(folder.glob("*.build"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
    return {"dir": str(folder), "exists": folder.is_dir(),
            "files": [{"file": p.name, "name": p.stem, "size": p.stat().st_size, "mtime": p.stat().st_mtime}
                      for p in files[:60]]}


def _planner_description(lang: str, who: str = "") -> str:
    """What the planner file says about the build in its description: who, the main skill, the key numbers."""
    e, ru = session.engine, lang == "ru"
    info = e.info()
    out = e.what_if(config=session.profile.config())
    names = i18n("ru")["names"] if ru else {}
    tr = lambda n: names.get(n) or n  # noqa: E731

    def num(v):
        return f"{v:,.0f}".replace(",", "\u00a0" if ru else ",")
    dps = out.get("CombinedDPS") or 0
    dps_text = (f"{dps / 1e6:.1f} млн".replace(".", ",") if ru else f"{dps / 1e6:.1f}M") if dps >= 1e6 else num(dps)
    res = " / ".join(f"{out.get(k, 0):.0f}" for k in ("FireResist", "ColdResist", "LightningResist"))
    immune = (out.get("ChaosMaximumHitTaken") or 0) >= IMMUNE_HIT
    res += (", иммунитет к хаосу" if ru else ", immune to chaos") if immune else f" / {out.get('ChaosResist', 0):.0f}"
    skill = tr(e.main_skill())
    who = re.sub(r"[{}]", "", who).strip() or (f"{tr(info['ascendancy'] or info['class'])}, "
                                               + (f"{info['level']} ур." if ru else f"level {info['level']}"))
    if ru:
        lines = [f"<b>{{{who}}}", f"Основной скилл: {skill}, около {dps_text} урона в секунду по PoB.",
                 f"Жизнь {num(out.get('Life', 0))}, энергощит {num(out.get('EnergyShield', 0))}, сопротивления {res}.",
                 "Самоцветы и выбор атрибутов — в подсказках узлов дерева.",
                 "Собрано в poe2lab: github.com/JavelinSx/poe2lab"]
    else:
        lines = [f"<b>{{{who}}}", f"Main skill: {skill}, about {dps_text} damage per second by PoB.",
                 f"Life {num(out.get('Life', 0))}, energy shield {num(out.get('EnergyShield', 0))}, resistances {res}.",
                 "Jewels and attribute choices: in the tree nodes' hover notes.",
                 "Made with poe2lab: github.com/JavelinSx/poe2lab"]
    return "\n".join(lines)


@app.post("/api/planner/export")
def planner_export(req: PlannerExport, build: str | None = None):
    """The open build into the game's planner folder, as the game reads it (see buildplanner.export_rich); 409 when a
    file of that name is there and overwrite is not asked."""
    with session.lock:
        session.require(build)
        folder = buildplanner.planner_dir()
        path = folder / f"{session.path.stem}.build"
        existed = path.exists()
        if existed and not req.overwrite:
            raise HTTPException(409, path.name)
        e = session.engine
        levels = {g["name"]: lv for grp in e.skill_groups() for g in grp["gems"] if (lv := available_level(g))}
        lang = req.lang if req.lang in ("ru", "en") else "ru"
        text = _errors(lambda: buildplanner.export_rich(
            e, session.path.stem, levels=levels, plan=session.bp.planner, description=_planner_description(lang, req.who),
            lang=lang, names=i18n("ru")["names"] if lang == "ru" else None))
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError as err:
            raise HTTPException(500, f"не удалось записать файл: {err}")
        return {"path": str(path), "file": path.name, "overwritten": existed}


@app.post("/api/planner/import")
def planner_import(req: PlannerImport):
    """A .build file of the game's planner folder added to the build list."""
    folder = buildplanner.planner_dir()
    path = folder / req.file
    if Path(req.file).name != req.file or path.suffix.lower() != ".build" or not path.is_file():
        raise HTTPException(404, f"нет файла {req.file!r} в папке планировщика")
    return _add_build("", path.read_text(encoding="utf-8-sig"))


def _guide_levels(bp) -> dict[str, int]:
    """The levels a guide's planner file gives its gems (from 1 means "from the start": the drop level stays)."""
    out = {}
    for s in ((bp.planner or {}).get("skills") or []) if bp else []:
        for g in [s] + list(s.get("supports") or []):
            if g.get("from") and g["from"] > 1 and g.get("known", True):
                out.setdefault(g["name"], g["from"])
    return out


class FavoriteRequest(BaseModel):
    favorite: bool


@app.put("/api/builds/{name}/favorite")
def favorite_build(name: str, req: FavoriteRequest):
    library.set_favorite(name, req.favorite)
    return {"ok": True}


@app.delete("/api/builds/{name}")
def remove_build(name: str):
    with session.lock:
        try:
            result = library.remove(name)
        except library.LibraryError as err:
            raise HTTPException(404, str(err))
        if session.ref is not None and session.ref[0] in (name, RECORDED):
            session.ref = None
        if session.path is not None and session.path.stem == name:  # the open build is gone: close it
            session.path = session.engine = session.bp = session.main = None
            session.cache.clear()
            session.assistant = session.toolbox = None
        return {"result": result}


@app.post("/api/builds/unhide")
def unhide_builds():
    library.unhide_all()
    return {"ok": True}


def _profile_questions() -> dict:
    """Which profile questions this build can even answer: Rage only when it moves the damage (every character has a
    Rage cap, but a spell build gains nothing from it), mana only when the main skill costs mana."""
    def compute():
        e, prof = session.engine, session.profile
        stats = e.what_if(config=prof.config())
        rage = False
        if stats.get("MaximumRage", 0) > 0:
            at_max = e.what_if(config=prof.config() | {"multiplierRage": 9999})["CombinedDPS"]
            none = e.what_if(config=prof.config() | {"multiplierRage": 0})["CombinedDPS"]
            rage = bool(none) and abs(at_max / none - 1) >= 0.005
        return {"rage": rage, "mana": stats.get("ManaPerSecondCost", 0) > 0}

    return session.cached("questions", compute)


def _summary():
    e = session.engine
    q = _errors(_profile_questions)
    return {"name": session.path.stem, "info": e.info(), "mainSkill": e.main_skill(), "groups": e.socket_groups(),
            "gems": sorted({g["name"] for g in e.gems()}),
            "gemColors": {g["name"]: {"color": g["color"], "support": g["support"]} for g in e.gems()},
            "profile": describe_profile(session.bp, rage=q["rage"]), "profileRaw": _profile_raw(),
            "hasProfile": _profile_path().exists(), "questions": q, "items": e.equipped_item_details(),
            "kind": "pob" if session.path.suffix.lower() == ".xml" else "code",
            # the player's own character (what all this is about) and the build it follows, when there is one
            "main": library.describe_file(session.main) if session.main else None,
            "guide": library.describe_file(session.path) if session.main else None}


@app.post("/api/load")
def load(req: LoadRequest):
    with session.lock:
        log.info("open build %r", req.name)
        _errors(lambda: session.load(req.name, req.group, req.skill))
        return _json(_summary())


class MainRequest(BaseModel):
    code: str  # the player's character: a PoB code or a pobb.in link


@app.post("/api/character")
def set_main(req: MainRequest):
    """The player's own character put into the open build: from now on every tab works on it, the build is the
    guide to compare with. A character already there is replaced (the old one to builds/.trash)."""
    with session.lock:
        session.require()
        name = session.path.stem
        try:
            library.set_main(name, req.code)
        except library.LibraryError as err:
            raise HTTPException(400, str(err))
        _errors(lambda: session.load(name))
        return _json(_summary())


@app.delete("/api/character")
def clear_main():
    with session.lock:
        session.require()
        name = session.path.stem
        try:
            library.clear_main(name)
        except library.LibraryError as err:
            raise HTTPException(400, str(err))
        _errors(lambda: session.load(name))
        return _json(_summary())


@app.post("/api/pob/open")
def pob_open():
    """Path of Building for updating the open build: started with it open, or the running window brought forward."""
    path = session.path if session.engine is not None else None
    try:
        return pobapp.open_pob(path)
    except OSError as err:
        raise HTTPException(500, f"не удалось запустить Path of Building: {err}")


class ReloadRequest(BaseModel):
    code: str = ""  # a newer PoB code or pobb.in link for a code build; empty: read the build file again


@app.post("/api/reload")
def reload_build(req: ReloadRequest):
    """The same build after the player changed gear or tree in the game: a PoB-saved build is read again from PoB's
    file, a code build takes the new code. Name, profile and main skill stay; the answer says what changed."""
    with session.lock:
        session.require()
        name, e = session.path.stem, session.engine
        before = capture_build(e, session.profile)
        skill_name, had_plan = e.main_skill(), session.plan is not None
        group = e.info()["mainSocketGroup"]
        if req.code.strip():
            try:  # the character is what changes in the game; the build it follows stays as recorded
                library.set_main(name, req.code) if session.main else library.replace(name, req.code)
            except library.LibraryError as err:
                raise HTTPException(400, str(err))
        _errors(lambda: session.load(name))
        # keep the skill the player was looking at if the new build still has it (the picker is not in the profile)
        groups = session.engine.socket_groups()
        spots = [(g["index"], i + 1) for g in groups for i, s in enumerate(g["skills"]) if s == skill_name]
        spots.sort(key=lambda gs: gs[0] != group)
        if spots and session.engine.main_skill() != skill_name:
            _errors(lambda: session.load(name, *spots[0]))
        if session.ref is not None and session.ref[0] == name:
            session.ref = None
        changes = build_diff(before, capture_build(session.engine, session.profile))
        changes["planReset"] = had_plan
        changes["skillKept"] = session.engine.main_skill() == skill_name
        changes["skillBefore"] = skill_name
        return _json(_summary() | {"changes": changes})


@app.get("/api/build")
def build():
    with session.lock:
        session.require()
        return _json(_summary())


@app.get("/api/report")
def report(mode: str = "balanced", build: str | None = None):
    with session.lock:
        session.require(build)
        return _json(session.cached(("report", mode), lambda: build_report(session.engine, session.profile, mode=mode,
                                                                              statdesc_dir=_game_texts("ru"))))


@app.get("/api/gear")
def gear(mode: str = "balanced", build: str | None = None):
    with session.lock:
        session.require(build)

        def compute():
            e, prof = session.engine, session.profile
            weights = defence_weights(survivable_hits(e, prof))
            check_mana = not prof.mana_sustained
            db, prices = session.db(), session.prices()
            by_id = {m.id: m for m in db.mods}
            essences = e.export_essences()
            plans = plan_all(e, db, prof.config(), mode, weights, top=4, check_mana=check_mana)
            plans.sort(key=lambda p: SLOTS_ORDER.index(p.slot) if p.slot in SLOTS_ORDER else 99)
            path = []
            by_slot = {p.slot: p for p in plans}
            items = {i["slot"]: i for i in e.equipped_item_details()}
            by_lines = {}
            for m in db.mods:
                by_lines.setdefault(tuple(m.lines), m)
            pools = {}
            for s in craft_path(e, db, prof.config(), mode, weights, steps=6, check_mana=check_mana):
                mod, plan, item = by_id.get(s.mod_id), by_slot.get(s.slot), items.get(s.slot)
                how = None
                if mod and plan and item:
                    # how to get it on the worn item: the chance per try (poe2lab.crafting.modify_routes)
                    if s.slot not in pools:
                        pools[s.slot] = (crafting.Pool(db, item["tags"], item["itemLevel"], item_type=item["type"]),
                                         crafting.Pool(db, item["tags"], item["itemLevel"], sets=("Desecrated",),
                                                       item_type=item["type"]))
                    stay = [a for a in plan.affixes if a.lines != s.removed]
                    have = {(m.group, m.patterns) for m in (by_lines.get(tuple(a.template)) for a in stay) if m}
                    how = crafting.modify_routes(db, *pools[s.slot], essences, item["type"], item["tags"],
                                                 item["itemLevel"], mod, have, plan.count(mod.type),
                                                 len(plan.affixes), bool(s.removed), crafting.bone_for(item["type"]))
                    for r in how["routes"]:
                        found = [prices.get(n) if prices else None for n in r["n"]]
                        r["prices"] = [prices.describe(x) if x else None for x in found]
                path.append(asdict(s) | {"how": how})
            sockets = []
            for s in plan_sockets(e, prof.config(), mode, weights):
                entry = asdict(s)
                for o in entry["best"]:
                    price = prices.get(o["name"]) if prices else None
                    o["price"] = prices.describe(price) if price else None
                sockets.append(entry)
            return {"slots": [asdict(p) | {"uncertain": p.uncertain, "prefixes": p.count("Prefix"),
                                           "suffixes": p.count("Suffix")} for p in plans],
                    "craftPath": path, "sockets": sockets,
                    "prices": {"league": prices.league} if prices else None}

        return _json(session.cached(("gear", mode), compute))


# ---- an equipped item's quality, catalyst, rune sockets and runes: edits of the plan, by the game's rules ----

def _gear_info(slot: str) -> dict:
    """The item in the slot with its quality, sockets and runes, and every augment that fits it - each with why the
    game would refuse it in a socket (analysis.sockets.refusal: another socket's rune counts for "one per item")."""
    e = session.engine
    item = next((i for i in e.equipped_item_details() if i["slot"] == slot), None)
    if item is None:
        raise HTTPException(400, f"в слоте {slot} ничего не надето")
    info = e.socket_info(slot)
    level, cls = session.level or 1, e.info()["class"]
    options = [o | {"refused": rune_refusal(o, info, [], level, cls)} for o in info["options"] if adds_stats(o)]
    options.sort(key=lambda o: (o["refused"] is not None, o["name"]))
    lines = [l["line"] for k in ("enchant", "implicit", "runes", "explicit") for l in item[k]]
    top = quality.max_quality(lines)
    catalyst = quality.takes_catalyst(info["itemType"], lines)
    return {"slot": slot, "item": item, "quality": info["quality"], "hasQuality": info["hasQuality"],
            "maxQuality": top if info["hasQuality"] else 0, "sockets": info["sockets"],
            "takesCatalyst": catalyst, "maxCatalystQuality": top if catalyst else 0,
            "catalyst": quality.CATALYSTS[info["catalyst"] - 1][0] if info["catalyst"] else "",
            "catalystQuality": info["catalystQuality"] if info["catalyst"] else 0,
            "catalysts": [{"name": n, "kind": k} for n, k, _ in quality.CATALYSTS] if catalyst else [],
            "socketLimit": max(info["socketLimit"], info["sockets"]), "runes": info["runes"],
            "corrupted": info["corrupted"], "rarity": info["rarity"], "options": options}


@app.get("/api/gear/item")
def gear_item(slot: str, build: str | None = None):
    with session.lock:
        session.require(build)
        return _json(_gear_info(slot) | {"plan": _plan_view()})


class GearEdit(BaseModel):
    """The item in `slot` with this quality, this many rune sockets and these runes (a name or "None" per socket),
    this catalyst (its name, "": none) at this quality; None: as it is."""
    slot: str
    quality: int | None = None
    sockets: int | None = None
    runes: list[str] | None = None
    catalyst: str | None = None
    catalyst_quality: int | None = None


def _gear_text(req: GearEdit) -> tuple[dict, str]:
    """The item's info and its edited text, if the game allows the edit: a corrupted item keeps its quality,
    catalyst and sockets and takes only the augments made for it; quality up to the item's maximum
    (poe2lab.quality); a catalyst on jewellery only; sockets added (never taken away) up to the base's limit; each
    rune one the item's type takes and the character can use, a one-per-item rune once."""
    info = _gear_info(req.slot)
    catalyst = info["catalyst"] if req.catalyst is None else req.catalyst
    cq = info["catalystQuality"] if req.catalyst_quality is None else req.catalyst_quality
    recatalysed = (catalyst, cq) != (info["catalyst"], info["catalystQuality"])
    same = lambda a, b: a is None or a == b  # noqa: E731
    if info["corrupted"] and (recatalysed or not (same(req.quality, info["quality"]) and same(req.sockets, info["sockets"]))):
        raise HTTPException(400, "предмет с порчей не изменить: ни качество, ни катализатор, ни гнёзда")
    if req.quality is not None and req.quality != info["quality"]:
        if not info["hasQuality"]:
            raise HTTPException(400, "у этого предмета нет качества")
        if not 0 <= req.quality <= info["maxQuality"]:
            raise HTTPException(400, f"качество этого предмета — от 0 до {info['maxQuality']}%")
    if recatalysed:
        if not info["takesCatalyst"]:
            raise HTTPException(400, "катализатор применяют к кольцам и амулетам")
        try:
            quality.catalyst_index(catalyst)
        except ValueError:
            raise HTTPException(400, f"нет такого катализатора: {catalyst}")
        if not 0 <= cq <= info["maxCatalystQuality"]:
            raise HTTPException(400, f"качество катализатора — от 0 до {info['maxCatalystQuality']}%")
        if not catalyst:
            cq = 0
    sockets = info["sockets"] if req.sockets is None else req.sockets
    if sockets < info["sockets"]:
        raise HTTPException(400, "гнездо для руны из предмета не убрать")
    if sockets > info["socketLimit"]:
        raise HTTPException(400, f"у этой базы не больше {info['socketLimit']} гнёзд для рун")
    runes = list(info["runes"]) if req.runes is None else list(req.runes)
    runes = (runes + ["None"] * sockets)[:sockets]
    by_name = {o["name"]: o for o in info["options"]}
    level, cls = session.level or 1, session.engine.info()["class"]
    for i, name in enumerate(runes):
        was = info["runes"][i] if i < len(info["runes"]) else "None"
        if name == "None" and was != "None":
            raise HTTPException(400, "руну из гнезда не вынуть — только заменить другой")
        if name in ("None", was):
            continue  # an empty socket, or the rune already there
        opt = by_name.get(name)
        if opt is None:
            raise HTTPException(400, f"{name} в этот предмет не вставить")
        why = rune_refusal(opt, info, runes[:i] + runes[i + 1:], level, cls)
        if why:
            raise HTTPException(400, {
                "class": f"{name} — только для класса {why.get('class')}",
                "unique": f"{name} не вставить в уникальный предмет",
                "corrupted": f"{name} не вставить в осквернённый предмет",
                "level": f"{name} требует {why.get('level')} уровня персонажа",
                "limit": f"{name} — не больше одной в предмете",
            }[why["code"]])
    old = (quality.catalyst_index(info["catalyst"]), info["catalystQuality"])
    new = (quality.catalyst_index(catalyst), cq)
    text = _errors(lambda: session.engine.edit_item(req.slot, req.quality, sockets, runes, *new))
    if new != old:
        item = info["item"]
        text = quality.recatalyse(text, [l["line"] for l in item["explicit"]], session.db(), item["tags"],
                                  item["itemLevel"] or 100, old, new)
    return info, text


@app.post("/api/gear/preview")
def gear_preview(req: GearEdit):
    """The item as it would be, and what it changes against the item as it is."""
    with session.lock:
        session.require()
        _, text = _gear_text(req)
        e, cfg = session.engine, session.profile.config()
        after = e.what_if(config=cfg, replace_item=(req.slot, text), keep_quality=True)
        return _json({"item": _errors(lambda: e.parse_item(text)) | {"slot": req.slot},
                      "change": metric_changes(after, e.what_if(config=cfg))})


@app.post("/api/gear/set")
def gear_set(req: GearEdit):
    """The edit onto the build's item - an edit of the plan."""
    with session.lock:
        session.require()
        info, text = _gear_text(req)
        _plan_start()
        session.plan["items"].setdefault(req.slot, session.engine.item_text(req.slot))
        session.engine.equip_item(req.slot, text, exact=True)
        new = session.engine.socket_info(req.slot)
        session.plan["log"].append({
            "action": "item", "target": req.slot, "item": info["item"]["name"],
            "quality": [info["quality"], new["quality"]] if new["quality"] != info["quality"] else None,
            "sockets": [info["sockets"], new["sockets"]] if new["sockets"] != info["sockets"] else None,
            "catalyst": ([quality.CATALYSTS[new["catalyst"] - 1][0] if new["catalyst"] else "", new["catalystQuality"]]
                         if (new["catalyst"], new["catalystQuality"]) != (quality.catalyst_index(info["catalyst"]),
                                                                        info["catalystQuality"]) else None),
            "added": [r for i, r in enumerate(new["runes"]) if r != "None" and
                      r != (info["runes"][i] if i < len(info["runes"]) else "None")]})
        _plan_changed()
        return _json(_gear_info(req.slot) | {"plan": _plan_view()})


# ---- an item of one's own choosing for a slot: made on a base, a unique or pasted; tried on, then worn ----

def _item_data() -> dict:
    return session.cached("item-data", lambda: session.engine.export_item_data())


def _slot_choice(slot: str) -> dict:
    """The bases the slot takes (with what the page shows of each) and the uniques on them."""
    def compute():
        names = set(session.engine.slot_bases(slot))
        bases = sorted(itemcraft.endgame_bases([b for b in _item_data()["bases"] if b["name"] in names]),
                       key=lambda b: (b["type"], b["subType"], -b["level"], b["name"]))
        uniques = sorted(({"name": u["name"], "base": u["base"], "lines": u["lines"], "level": u["level"],
                           "raw": u["raw"], "ranged": any(jewelcraft.RANGE.search(l) for l in u["lines"])}
                          for u in session.cached("unique-catalog", session.engine.unique_catalog) if u["base"] in names),
                         key=lambda u: (u["name"], u["base"]))
        return {"bases": bases, "uniques": uniques}
    return session.cached(("slot-choice", slot), compute)


@app.get("/api/gear/create")
def gear_create(slot: str, build: str | None = None):
    """What an item for the slot can be: the bases it takes, their uniques, the rarities' limits."""
    with session.lock:
        session.require(build)
        c = _slot_choice(slot)
        return _json({"slot": slot, "bases": c["bases"], "uniques": [{k: v for k, v in u.items() if k != "raw"}
                                                                      for u in c["uniques"]],
                      "limits": itemcraft.LIMITS, "itemLevel": itemcraft.DEFAULT_ITEM_LEVEL,
                      "itemLevels": itemcraft.ITEM_LEVELS,
                      "maxQuality": quality.DEFAULT_MAX})


def _base(slot: str, name: str) -> dict:
    base = next((b for b in _slot_choice(slot)["bases"] if b["name"] == name), None)
    if base is None:
        raise HTTPException(400, f"{name} не встаёт в слот {slot}")
    return base


@app.get("/api/gear/mods")
def gear_mods(slot: str, base: str, item_level: int = itemcraft.DEFAULT_ITEM_LEVEL):
    """The mod families the base rolls, each with its tiers (T1 first) and whether the item level lets it roll."""
    with session.lock:
        session.require()
        b = _base(slot, base)
        return _json({"base": b, "families": itemcraft.families(session.db(), b["tags"], item_level)})


class ItemMake(BaseModel):
    """An item for `slot`, one of: `unique` (its name; `base` too when it comes on several) rolled at `roll`, one
    made on `base` (rarity, item level, mods [{"id": a tier's id, "roll"}], quality, the implicit's roll), or
    `text` copied from the game, Russian or English, or PoB's."""
    slot: str
    text: str = ""
    unique: str = ""
    base: str = ""
    rarity: str = "rare"
    item_level: int = itemcraft.DEFAULT_ITEM_LEVEL
    mods: list[dict] = []
    quality: int | None = None
    implicit_roll: float = 0.5
    roll: float = 0.5
    breakeven: str | None = None  # a mod line of the item: how low it may roll and the item still not lose


def _made_item(req: ItemMake) -> tuple[str, bool]:
    """The item's text and whether its quality is as written (one made here)."""
    try:
        if req.unique:
            u = next((u for u in _slot_choice(req.slot)["uniques"]
                      if u["name"] == req.unique and req.base in ("", u["base"])), None)
            if u is None:
                raise HTTPException(400, f"{req.unique} не встаёт в слот {req.slot}")
            return jewelcraft.rolled_unique(u, req.roll, session.engine.resolve_ranges), False
        if req.base:
            b = _base(req.slot, req.base)
            fams = itemcraft.families(session.db(), b["tags"], req.item_level)
            q = None
            if b["quality"]:
                q = quality.DEFAULT_MAX if req.quality is None else req.quality
                if not 0 <= q <= quality.DEFAULT_MAX:
                    raise HTTPException(400, f"качество — от 0 до {quality.DEFAULT_MAX}%")
            return itemcraft.make(b, req.rarity, req.item_level, req.mods, fams, q, req.implicit_roll,
                                  session.engine.resolve_ranges), True
    except itemcraft.CraftError as err:
        raise HTTPException(400, str(err))
    if not req.text.strip():
        raise HTTPException(400, "нет вещи: создай её, выбери уникальную или вставь текст")
    return _english_item(req.text), False


def _checked_item(req: ItemMake) -> tuple[str, bool]:
    text, exact = _made_item(req)
    if not _errors(lambda: session.engine.item_fits(req.slot, text)):
        item = _errors(lambda: session.engine.parse_item(text))
        raise HTTPException(400, f"{item['baseName'] or item['name']} не встаёт в слот {req.slot}")
    return text, exact


@app.post("/api/gear/try")
def gear_try(req: ItemMake):
    """The item tried on in the slot: its text and lines, and the comparison with the slot's item; with
    `breakeven`, how far that mod line may fall and the item still be no worse than the worn one."""
    with session.lock:
        session.require()
        text, exact = _checked_item(req)
        e, cfg = session.engine, session.profile.config()
        result = asdict(_errors(lambda: compare(e, cfg, req.slot, text, keep_quality=exact)))
        if req.breakeven and req.breakeven.strip():
            res = _errors(lambda: breakeven(e, cfg, req.slot, text, req.breakeven.strip()))
            result["breakeven"] = None if res is None else {"factor": res[0], "line": res[1]}
        return _json(result | {"text": text, "item": _errors(lambda: e.parse_item(text))})


@app.post("/api/gear/equip")
def gear_equip(req: ItemMake):
    """The item worn in the slot - an edit of the plan."""
    with session.lock:
        session.require()
        text, exact = _checked_item(req)
        e = session.engine
        old = next((i for i in e.equipped_item_details() if i["slot"] == req.slot), None)
        _plan_start()
        session.plan["items"].setdefault(req.slot, e.item_text(req.slot) if old else None)
        e.equip_item(req.slot, text, exact=exact)
        new = next(i for i in e.equipped_item_details() if i["slot"] == req.slot)
        session.plan["log"].append({"action": "item", "target": req.slot, "item": new["name"],
                                    "worn": old["name"] if old else None})
        _plan_changed()
        return _json({"plan": _plan_view()})


@app.get("/api/plan")
def plan_view(build: str | None = None):
    """The plan of edits (tree, jewels, gems, gear) against the build, or null."""
    with session.lock:
        session.require(build)
        return _json(_plan_view())


@app.get("/api/mechanics")
def mechanics(build: str | None = None):
    with session.lock:
        session.require(build)
        m = session.cached("mechanics", lambda: collect_mechanics(session.engine, _game_texts("ru")))
        return _json({"gaps": m.gaps, "skills": m.skills, "uniques": m.uniques})


def _unique_prices() -> dict:
    """Uniques' prices on poe.ninja in the chosen league (empty without a connection)."""
    prices = session.prices()
    if prices is None:
        return {}
    try:
        names = session.cached(("unique-prices", prices.league), lambda: ninja.unique_prices(prices.league))
    except OSError:
        return {}
    return {"league": prices.league, "exaltedPerDivine": prices.exalted_per_divine, "byName": names}


@app.get("/api/skills")
def skills_view(view: str = "build", scope: str = "level", build: str | None = None, of: str | None = None):
    """The build's skills: each with its support gems and the links between skills ("build"), or when each gem can
    be had and what to socket meanwhile while levelling ("leveling"; of="target": the levelling of the build's
    target - the guide the player follows)."""
    if view not in ("build", "leveling", "uniques", "supports"):
        raise HTTPException(400, f"неизвестный вид {view!r}")
    with session.lock:
        session.require(build)
        e, cfg = session.engine, session.profile.config()
        if view in ("build", "uniques"):
            m = session.cached("mechanics", lambda: collect_mechanics(e, _game_texts("ru")))
            data = session.cached(("skills", "build"), lambda: skill_build_view(
                e, cfg, e.mechanics_raw(_game_texts("ru")), m.uniques,
                [asdict(g) for g in m.gaps if g.source == "item"]))
            if view == "uniques":
                # levelling: what a character of about this level can wear; on maps every unique
                cap = session.level + 5 if scope == "level" and session.level and session.level < 65 else None
                view_data = data
                data = session.cached(("skills", "uniques", cap), lambda: suggest_uniques(e, cfg, view_data, cap))
                data = data | {"level": session.level, "prices": _unique_prices()}
        elif view == "supports":
            # supports worth more than each skill's weakest, among those the character can have at its level
            data = session.cached(("skills", "supports"), lambda: better_supports(e, cfg, session.level))
            return _json({"skills": data, "level": session.level})
        elif of == "target":
            name = session.bp.target
            if not name:
                raise HTTPException(400, "у билда нет цели: её выбирают во вкладке «Профиль»")
            _, engine, bp = _reference(name)
            profile = MapProfile.for_level(engine.info()["level"], rage=bp.rage, mana_sustained=bp.mana_sustained)
            data = session.cached(("skills", "leveling", "target", name),
                                  lambda: skill_leveling_view(engine, profile.config(), levels=_guide_levels(bp))) | {"of": name}
        else:
            data = session.cached(("skills", "leveling"),
                                  lambda: skill_leveling_view(e, cfg, levels=_guide_levels(session.bp)))
        if view == "build":
            # gem edits are edits of the plan; each skill's own damage, crit, speed (crit is a skill's own in the game)
            numbers = session.cached(("skill-numbers",), lambda: e.skill_damage(cfg))
            # how often the triggered skills go off, which PoB does not count (poe2lab.analysis.triggers)
            data = data | {"plan": _plan_view(), "numbers": numbers,
                           "triggers": session.cached(("triggers",), lambda: trigger_view(e, cfg, numbers))}
        return _json(data)


def _reference(name: str):
    """The reference build, kept loaded in its own engine while it is in use: `@build` - the open build as its
    file records it (the guide the player's character follows, the gear before the plan's edits) - or another
    build of the list."""
    if name == session.path.stem:
        raise HTTPException(400, "эталон — это другой билд, не открытый")
    if session.ref is None or session.ref[0] != name:
        session.ref = None  # free the previous reference first
        path = session.path if name == RECORDED else resolve_build(name)
        engine, bp = _errors(lambda: open_build(path))
        session.ref = (name, engine, bp)
    return session.ref


@app.get("/api/tree")
def tree(mode: str = "balanced", points: int = 6, build: str | None = None):
    if mode not in MODES:
        raise HTTPException(400, f"неизвестная цель {mode!r}")
    with session.lock:
        session.require(build)
        points = max(1, min(points, 10))
        result = session.cached(("tree", mode, points), lambda: analyse_tree(
            session.engine, session.profile, mode=mode, max_points=points))
        return _json(result | {"plan": _plan_view(), "points": session.engine.points_budget()})


@app.get("/api/tree/packages")
def tree_packages(mode: str = "balanced", build: str | None = None):
    """Each mechanic's best notables taken together (rage, charges, crit, ailments...): what they give as one."""
    if mode not in MODES:
        raise HTTPException(400, f"неизвестная цель {mode!r}")
    with session.lock:
        session.require(build)
        return _json(session.cached(("tree-packages", mode), lambda: mechanic_packages(
            session.engine, session.profile, mode=mode)))


@app.get("/api/tree/graph")
def tree_graph(build: str | None = None):
    """The passive tree to draw: nodes with positions, links and what is allocated (the plan's edits included)."""
    with session.lock:
        session.require(build)
        edits = len(session.plan["log"]) if session.plan else -1
        return _json(session.cached(("tree-graph", edits), _tree_graph_with_icons))


def _tree_graph_with_icons() -> dict:
    """Each node gets its own picture (by the icon path PoB keeps for it), when the icons are unpacked."""
    graph = session.engine.tree_graph()
    have = {p.name for p in icons.ICONS.glob("*.png")} if icons.ICONS.is_dir() else set()
    for n in graph["nodes"]:
        file = icons._file_name(n.pop("icon")) if n.get("icon") else ""
        n["img"] = file if file in have else ""
    return graph


TREE_DATA = gamedata.ROOT / "pob2" / "src" / "TreeData"
TREE_ART = re.compile(r"[\w-]+\.dds\.zst")


@app.get("/api/tree/art/{version}/{file}")
def tree_art(version: str, file: str, request: Request):
    """One of PoB's tree textures (the game's art, zstd-packed DDS) as it is: the browser unpacks zstd itself
    (Content-Encoding), the page decodes the DDS. 406 for a browser without zstd: the page then draws without art."""
    if not re.fullmatch(r"[\w.]+", version) or not TREE_ART.fullmatch(file):
        raise HTTPException(404, "нет такой текстуры")
    path = TREE_DATA / version / file
    if not path.is_file():
        raise HTTPException(404, "нет такой текстуры")
    if "zstd" not in request.headers.get("accept-encoding", ""):
        raise HTTPException(406, "браузер не распаковывает zstd")
    return FileResponse(path, media_type="application/octet-stream",
                        headers={"Content-Encoding": "zstd", "Cache-Control": "max-age=604800"})


@app.get("/api/ascendancy")
def ascendancy_view(mode: str = "balanced", build: str | None = None):
    """The ascendancy's allocated notables and the ones not taken, priced by PoB on the build."""
    if mode not in MODES:
        raise HTTPException(400, f"неизвестная цель {mode!r}")
    with session.lock:
        session.require(build)
        edits = len(session.plan["log"]) if session.plan else -1
        return _json(session.cached(("ascendancy", mode, edits),
                                    lambda: tree_ascendancy(session.engine, session.profile, mode)))


# ---- tree plans: edits of the passive tree in the engine only; the build file is never changed ----

def _plan_start():
    if session.plan is None:
        session.engine.tree_snapshot("plan-base")
        session.engine.skills_snapshot("plan-base")
        session.plan = {"budget": session.engine.tree_points(),
                        "base": session.engine.what_if(config=session.profile.config()), "log": [],
                        "items": {}}  # slot -> its item's text before the first edit (None: it was empty)


GAME_DATA_KEYS = ("db", "jewel-db", "unique-catalog", "jewel-catalog", "gem-catalog", "item-data")


def _plan_changed():
    """Every analysis now sees the planned tree: drop cached results (the game's data does not depend on it)."""
    session.cache = {k: v for k, v in session.cache.items() if k in GAME_DATA_KEYS}
    session.assistant = session.toolbox = None


def _plan_view() -> dict | None:
    if session.plan is None:
        return None
    now = session.engine.what_if(config=session.profile.config())
    return {"budget": session.plan["budget"], "used": session.engine.tree_points(), "log": session.plan["log"],
            "changes": metric_changes(now, session.plan["base"])}


class TreeEdit(BaseModel):
    id: int
    name: str = ""
    set: int = Field(0, ge=0, le=2)  # 0: the main tree, 1 and 2: weapon set I and II (PoB's allocation mode)


@app.post("/api/tree/add")
def tree_add(req: TreeEdit):
    with session.lock:
        session.require()
        _plan_start()
        names = _errors(lambda: session.engine.tree_add(req.id, req.set))
        session.plan["log"].append({"action": "add", "target": req.name, "nodes": names} | ({"set": req.set} if req.set else {}))
        _plan_changed()
        return _json(_plan_view())


class TreePackage(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=12)  # the package's notables, nearest first
    mechanic: str = Field(min_length=1, max_length=40)
    mode: str = "balanced"
    force: bool = False  # taken even when the trade does not pay


@app.post("/api/tree/package")
def tree_package(req: TreePackage):
    """A mechanic's package taken as one edit of the plan: on a full tree, the weakest branches given up for it -
    kept only when the build comes out ahead (else nothing changes and the answer says what it would have cost)."""
    if req.mode not in MODES:
        raise HTTPException(400, f"неизвестная цель {req.mode!r}")
    with session.lock:
        session.require()
        _plan_start()
        points = session.engine.points_budget()
        limit = max(points["total"], points["used"])  # what the level gives - or the tree as it is, if already over
        r = _errors(lambda: take_package(session.engine, session.profile, req.mode, req.ids, limit, force=req.force))
        if r["kept"]:
            target = "package:" + req.mechanic
            session.plan["log"].append({"action": "swap", "target": target, "removed": r["removed"], "added": r["added"]}
                                       if r["removed"] else {"action": "add", "target": target, "nodes": r["added"]})
            _plan_changed()
        return _json(r | {"plan": _plan_view()})


@app.post("/api/tree/remove")
def tree_remove(req: TreeEdit):
    with session.lock:
        session.require()
        _plan_start()
        names = _errors(lambda: session.engine.tree_remove(req.id, req.set))
        session.plan["log"].append({"action": "remove", "target": req.name, "nodes": names} | ({"set": req.set} if req.set else {}))
        _plan_changed()
        return _json(_plan_view())


@app.post("/api/tree/reset")
def tree_reset():
    with session.lock:
        session.require()
        if session.plan is not None:
            session.engine.tree_restore("plan-base")
            session.engine.skills_restore("plan-base")
            for slot, text in session.plan["items"].items():  # the jewels and gear as they were
                if text:
                    session.engine.equip_item(slot, text, exact=True)
                else:
                    session.engine.clear_slot(slot)
            session.plan = None
            _plan_changed()
        return {"ok": True}


# ---- jewels in the tree's sockets: put in, taken out - edits of the plan like the tree's own ----

def _jewel_slot(node: int) -> dict:
    socket = next((s for s in session.engine.jewel_sockets() if s["node"] == node), None)
    if socket is None:
        raise HTTPException(400, "это не взятое гнездо самоцвета: сначала возьми его на дереве")
    return socket


@app.get("/api/jewels")
def jewels(build: str | None = None):
    """The allocated jewel sockets, the jewel in each and what taking it out would cost (damage, defences)."""
    with session.lock:
        session.require(build)

        def compute():
            e, cfg = session.engine, session.profile.config()
            base = e.what_if(config=cfg)
            out = []
            for s in sorted(e.jewel_sockets(), key=lambda s: (not s["item"], s["near"])):
                if s["item"]:
                    s["without"] = metric_changes(e.what_if(config=cfg, remove_slot=s["slot"]), base)
                out.append(s)
            return {"sockets": out}

        return _json(session.cached("jewels", compute))


def _jewel_catalog() -> dict:
    return session.cached("jewel-catalog", lambda: jewelcraft.catalog(
        session.engine.export_item_data(jewelcraft.MOD_SETS),
        session.cached("unique-catalog", session.engine.unique_catalog)))


@app.get("/api/jewels/catalog")
def jewel_catalog():
    """What a jewel can be made of, as the game makes them: the bases with the mods each rolls, the rarities' limits
    and the unique jewels (see poe2lab.jewelcraft)."""
    with session.lock:
        session.require()
        return _json(_jewel_catalog())


class JewelEdit(BaseModel):
    """A jewel for a socket (the node id), one of: `unique` (its name; `base` too when it comes on several) rolled
    at `roll`, one made on `base` (rarity, mods [{"id", "roll"}], corruption {"id", "roll"}) or `text` copied from
    the game, Russian or English, or PoB's."""
    node: int
    text: str = ""
    unique: str = ""
    base: str = ""
    rarity: str = "rare"
    mods: list[dict] = []
    corruption: dict | None = None
    roll: float = 0.5


def _jewel_text(req: JewelEdit) -> str:
    cat = _jewel_catalog()
    try:
        if req.unique:
            u = next((u for u in cat["uniques"] if u["name"] == req.unique and req.base in ("", u["base"])), None)
            if u is None:
                raise HTTPException(400, f"нет такого уникального самоцвета: {req.unique}")
            return jewelcraft.rolled_unique(u, req.roll, session.engine.resolve_ranges)
        if req.base:
            base = next((b for b in cat["bases"] if b["name"] == req.base), None)
            if base is None:
                raise HTTPException(400, f"на базе {req.base} самоцвет не создать: она бывает только уникальной")
            return jewelcraft.make(base, req.rarity, req.mods, req.corruption, session.engine.resolve_ranges)
    except jewelcraft.CraftError as err:
        raise HTTPException(400, str(err))
    if not req.text.strip():
        raise HTTPException(400, "нет самоцвета: выбери уникальный, создай или вставь текст")
    return _english_item(req.text, jewel=True)


def _jewel_checked(req: JewelEdit, socket: dict) -> tuple[str, dict]:
    """The jewel's text and how the page shows it, if the game would let it into this socket."""
    text = _jewel_text(req)
    item = _errors(lambda: session.engine.parse_item(text))
    if item["type"] != "Jewel":
        raise HTTPException(400, f"это не самоцвет: {item['baseName'] or item['name']}")
    if not session.engine.item_fits(socket["slot"], text):
        raise HTTPException(400, "в это гнездо такой самоцвет не встаёт (гнездо Лича — только простые не уникальные, "
                                 "зловещее — не уникальные)")
    limit = jewelcraft.limited_to(text)
    if limit is not None:
        name = item["name"].split(",")[0]
        held = sum(1 for s in session.engine.jewel_sockets()
                   if s["item"] and s["node"] != socket["node"] and s["item"]["name"].split(",")[0] == name)
        if held >= limit:
            raise HTTPException(400, f"«{name}» можно вставить не больше {limit}: он уже стоит в другом гнезде")
    return text, item


@app.post("/api/jewels/preview")
def jewel_preview(req: JewelEdit):
    """The jewel as it would be in the socket - its text, lines and what it changes against the socket as it is."""
    with session.lock:
        session.require()
        socket = _jewel_slot(req.node)
        text, item = _jewel_checked(req, socket)
        e, cfg = session.engine, session.profile.config()
        after = _errors(lambda: e.what_if(config=cfg, replace_item=(socket["slot"], text)))
        return _json({"text": text, "item": item, "change": metric_changes(after, e.what_if(config=cfg))})


@app.post("/api/jewels/set")
def jewel_set(req: JewelEdit):
    """A jewel into an allocated socket - an edit of the plan, like the tree's own."""
    with session.lock:
        session.require()
        socket = _jewel_slot(req.node)
        text, item = _jewel_checked(req, socket)
        _plan_start()
        session.plan["items"].setdefault(socket["slot"], session.engine.item_text(socket["slot"]) if socket["item"] else None)
        _errors(lambda: session.engine.equip_item(socket["slot"], text))
        session.plan["log"].append({"action": "jewel", "target": socket["near"], "added": item["name"],
                                    "removed": socket["item"]["name"] if socket["item"] else None})
        _plan_changed()
        return _json(_plan_view())


@app.post("/api/jewels/remove")
def jewel_remove(req: JewelEdit):
    with session.lock:
        session.require()
        socket = _jewel_slot(req.node)
        if not socket["item"]:
            return _json(_plan_view())
        _plan_start()
        session.plan["items"].setdefault(socket["slot"], session.engine.item_text(socket["slot"]))
        session.engine.clear_slot(socket["slot"])
        session.plan["log"].append({"action": "jewel", "target": socket["near"], "added": None,
                                    "removed": socket["item"]["name"]})
        _plan_changed()
        return _json(_plan_view())


# ---- gems: any skill's gems taken out, put in or swapped - edits of the plan, by the game's rules (gemcraft) ----

def _gem_catalog() -> dict[str, dict]:
    return session.cached("gem-catalog", lambda: {g["id"]: g for g in session.engine.gem_catalog()})


def _skill_name(groups: list[dict], group: int) -> str:
    g = next((x for x in groups if x["index"] == group), None)
    return (g["actives"][0]["name"] if g and g["actives"] else
            g["gems"][0]["name"] if g and g["gems"] else "")


@app.get("/api/gems/options")
def gem_options(group: int = 0, index: int | None = None, kind: str = "support"):
    """The gems that can go into a skill: for kind=support the supports that can support the group's skill, each
    with why the game would refuse it there (gemcraft.blocked) or none; for kind=skill every skill gem with the
    highest level the character can use."""
    if kind not in ("support", "skill"):
        raise HTTPException(400, f"неизвестный вид {kind!r}")
    with session.lock:
        session.require()
        e, level = session.engine, session.level or 1
        cat, groups = _gem_catalog(), e.skill_groups()
        if kind == "support":
            fits = set(e.gem_fits(group)) if group else set()
            gems = [g | {"blocked": gemcraft.blocked(g, groups, group, index, fits, level)}
                    for g in cat.values() if g["support"] and g["id"] in fits]
        else:
            gems = [g | {"usable": gemcraft.usable_level(g, level)} for g in cat.values() if not g["support"]]
        gems.sort(key=lambda g: (bool(g.get("blocked")), g["name"]))
        target = next((x for x in groups if x["index"] == group), None)
        current = next((x for x in target["gems"] if x["index"] == index), None) if target and index else None
        return _json({"gems": gems, "level": level, "skill": _skill_name(groups, group), "current": current,
                      "maxQuality": gemcraft.MAX_QUALITY})


class GemEdit(BaseModel):
    """A gem (a data.gems id) into socket group `group` (0: a new skill), in place of the gem at `index` or as one
    more; a skill gem's level (None: the highest the character can use) and quality."""
    group: int = 0
    index: int | None = None
    gem: str = ""
    level: int | None = None
    quality: int = 0


def _gem_checked(req: GemEdit) -> tuple[dict, int | None, int, list[dict]]:
    gem = _gem_catalog().get(req.gem)
    if gem is None:
        raise HTTPException(400, f"нет такого камня: {req.gem}")
    e, groups = session.engine, session.engine.skill_groups()
    fits = set(e.gem_fits(req.group)) if req.group and gem["support"] else set()
    try:
        level, quality = gemcraft.check(gem, groups, req.group, req.index, fits, session.level or 1, req.level,
                                        req.quality)
    except gemcraft.GemError as err:
        raise HTTPException(400, str(err))
    return gem, level, quality, groups


def _apply_gem(req: GemEdit, gem: dict, level: int | None, quality: int) -> tuple[int, list[str]]:
    """Socket it; a skill gem swapped in keeps the supports that can support it, the rest come out (the game does
    not let a support into a skill it cannot support). Returns the group and the supports taken out."""
    e = session.engine
    group = _errors(lambda: e.set_gem(req.group, req.index, gem["id"], level, quality))
    dropped = []
    if not gem["support"] and req.group:
        fits = set(e.gem_fits(group))
        g = next(x for x in e.skill_groups() if x["index"] == group)
        for x in sorted((x for x in g["gems"] if x["support"] and x["id"] not in fits), key=lambda x: -x["index"]):
            e.remove_gem(group, x["index"])
            dropped.append(x["name"])
    return group, dropped


@app.post("/api/gems/preview")
def gem_preview(req: GemEdit):
    """What the gem would change: the skill's own damage before and after, the build's numbers (its main skill),
    the supports a swapped skill gem would lose."""
    with session.lock:
        session.require()
        gem, level, quality, _ = _gem_checked(req)
        e, cfg = session.engine, session.profile.config()
        before = e.what_if(config=cfg)
        own_before = e.what_if(config=cfg, main_socket_group=req.group)["CombinedDPS"] if req.group else 0
        e.skills_snapshot("preview")
        try:
            group, dropped = _apply_gem(req, gem, level, quality)
            after = e.what_if(config=cfg)
            own_after = e.what_if(config=cfg, main_socket_group=group)["CombinedDPS"]
        finally:
            e.skills_restore("preview")
        return _json({"change": metric_changes(after, before), "own": {"before": own_before, "after": own_after},
                      "dropped": dropped, "level": level, "quality": quality})


@app.post("/api/gems/set")
def gem_set(req: GemEdit):
    with session.lock:
        session.require()
        gem, level, quality, groups = _gem_checked(req)
        at = next((x for g in groups if g["index"] == req.group for x in g["gems"] if x["index"] == req.index), None)
        _plan_start()
        group, dropped = _apply_gem(req, gem, level, quality)
        session.plan["log"].append({"action": "gem", "target": _skill_name(session.engine.skill_groups(), group),
                                    "added": gem["name"], "level": level, "quality": quality,
                                    "removed": at["name"] if at else None, "dropped": dropped})
        _plan_changed()
        return _json({"plan": _plan_view(), "group": group})


@app.post("/api/gems/remove")
def gem_remove(req: GemEdit):
    """Take a gem out of a skill; the skill gem itself (the first) takes its supports with it: the skill is gone."""
    with session.lock:
        session.require()
        e, groups = session.engine, session.engine.skill_groups()
        g = next((x for x in groups if x["index"] == req.group), None)
        at = next((x for x in g["gems"] if x["index"] == req.index), None) if g else None
        if at is None:
            raise HTTPException(400, f"в скилле №{req.group} нет камня №{req.index}")
        _plan_start()
        whole = at["index"] == g["gems"][0]["index"]
        for x in (sorted(g["gems"], key=lambda x: -x["index"]) if whole else [at]):
            e.remove_gem(req.group, x["index"])
        session.plan["log"].append({"action": "gem", "target": _skill_name(groups, req.group), "added": None,
                                    "removed": at["name"],
                                    "dropped": [x["name"] for x in g["gems"] if x is not at] if whole else []})
        _plan_changed()
        return _json({"plan": _plan_view()})


class TreeOptimize(BaseModel):
    mode: str = "balanced"
    seed: int | None = None


@app.post("/api/tree/optimize")
def tree_optimize(req: TreeOptimize):
    if req.mode not in MODES:
        raise HTTPException(400, f"неизвестная цель {req.mode!r}")
    with session.lock:
        session.require()
        _plan_start()
        result = optimize_tree(session.engine, session.profile, req.mode, session.plan["budget"], seed=req.seed)
        for step in result["steps"]:
            session.plan["log"].append({"action": "swap", "removed": step["removed"], "added": step["added"]})
        _plan_changed()
        return _json(_plan_view() | {"found": len(result["steps"])})


class TreeSave(BaseModel):
    name: str = ""


@app.post("/api/tree/save")
def tree_save(req: TreeSave):
    """The planned tree as a new build in the list (the profile goes with it), so it opens like any other."""
    with session.lock:
        session.require()
        code = _build_code()  # the copied profile re-applies the corrections
        try:
            name = library.add(req.name or f"{session.path.stem} план", code)
        except library.LibraryError as err:
            raise HTTPException(400, str(err))
        src = _profile_path()
        if src.exists():
            (PROJECT_BUILDS / f"{name}.profile.json").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return {"name": name}


def _build_code() -> str:
    """The open build as PoB has it now (the plan's edits in), without the profile's corrections: those live in the
    profile and are put back when the build opens."""
    engine, bp = session.engine, session.bp
    engine.set_custom_mods(CORRECTION_BLOCK, [])
    try:
        return engine.export_code()
    finally:
        engine.set_custom_mods(CORRECTION_BLOCK, [c.line for c in bp.corrections])


@app.post("/api/builds/commit")
def build_commit():
    """The plan's edits written into the open build itself (its previous code to builds/.trash): what the build
    constructor saves after each step. A build saved in PoB is updated in PoB, not here."""
    with session.lock:
        session.require()
        name = session.path.stem
        try:  # the player's character takes the edits when there is one; the build it follows stays
            library.set_main(name, _build_code()) if session.main else library.replace(name, _build_code())
        except library.LibraryError as err:
            raise HTTPException(400, str(err))
        _errors(lambda: session.load(name))
        return _json(_summary())


@app.get("/api/builds/code")
def build_code(build: str | None = None):
    """The open build's PoB code as it is now (for pobb.in, PoB's Import)."""
    with session.lock:
        session.require(build)
        return {"code": _build_code()}


# ---- the build constructor: a build from nothing (PLAN.md, "Конструктор билда с нуля") ----

@app.get("/api/new/classes")
def new_classes():
    """The classes with their ascendancies and the stages' levels, for the first step."""
    if "new-classes" not in _bare:
        _bare["new-classes"] = newbuild.classes(PobEngine())
    return {"classes": _bare["new-classes"], "stages": newbuild.STAGES}


# ---- the ladder of poe.ninja: which ascendancies players pick, and a top character's build to start from ----

def _ladder(ascendancy: str | None = None) -> dict:
    try:
        return ladder.search(ascendancy, ninja.chosen_league())
    except (OSError, ValueError, StopIteration) as err:
        raise HTTPException(502, f"poe.ninja не отвечает: {err}")


@app.get("/api/ladder/ascendancies")
def ladder_ascendancies():
    """How many characters of the league's ladder pick each ascendancy, and their share."""
    s = _ladder()
    total = s["total"] or 1
    return {"league": s["league"], "total": s["total"],
            "shares": {k: {"count": v, "share": v / total} for k, v in s["ascendancies"].items()}}


@app.get("/api/ladder/top")
def ladder_top(ascendancy: str, limit: int = 12):
    """The ascendancy's top characters on the ladder (by experience): level, main skill, damage, effective life,
    and each one's page on poe.ninja."""
    s = _ladder(ascendancy)
    return {"league": s["league"], "total": s["total"], "characters": s["characters"][:max(1, min(limit, 50))]}


class LadderTake(BaseModel):
    account: str
    name: str
    skill: str = ""


@app.post("/api/ladder/take")
def ladder_take(req: LadderTake):
    """A ladder character's build (its PoB code from poe.ninja) added to the list and opened, marked as the
    constructor's: the start of one's own build, to change step by step."""
    try:
        code = ladder.character_code(req.account, req.name, ninja.chosen_league())
    except (OSError, ValueError) as err:
        raise HTTPException(502, f"poe.ninja не отдал билд: {err}")
    clean = lambda s: re.sub(r"[^\w\- .()]", "", s).strip()  # noqa: E731  (the library's name rules)
    base = (clean(req.name) or "ladder")[:40] + (f" ({clean(req.skill)[:16]})" if clean(req.skill) else "")
    name, n = base, 2
    while True:
        try:
            name = library.add(name, code)
            break
        except library.LibraryError as err:
            if "уже есть" not in str(err) or n > 20:
                raise HTTPException(400, str(err))
            name, n = f"{base} {n}", n + 1
    library.save_profile(name, {"main_skill": {}, "rage": None, "mana_sustained": False, "league": None,
                                "corrections": [], "notes": [],
                                "constructor": {"stage": "ladder", "from": {"account": req.account, "name": req.name}}})
    with session.lock:
        _errors(lambda: session.load(name))
        return _json(_summary())


class NewBuild(BaseModel):
    ascendancy: str  # the planner's internal id: Monk2 = Invoker
    stage: str = "endgame"
    level: int | None = None  # the player's own level instead of the stage's
    name: str = ""


@app.post("/api/builds/new")
def new_build(req: NewBuild):
    """An empty build of the ascendancy at the stage's level, added to the list and opened; its profile marks it as
    the constructor's, so the page shows the constructor's steps."""
    try:
        level = newbuild.level_of(req.stage, req.level)
        xml = newbuild.empty_build(PobEngine(), req.ascendancy, level)
        name = library.add(req.name, encode_pob_code(xml))
    except (ValueError, library.LibraryError) as err:
        raise HTTPException(400, str(err))
    library.save_profile(name, {"main_skill": {}, "rage": None, "mana_sustained": False, "league": None,
                                "corrections": [], "notes": [],
                                "constructor": {"stage": req.stage if req.level is None else "custom", "level": level}})
    with session.lock:
        _errors(lambda: session.load(name))
        return _json(_summary())


class FeedbackRequest(BaseModel):
    message: str
    contact: str = ""
    images: list[str] = []  # data: URLs of pasted or chosen screenshots
    tab: str = ""
    mode: str = ""
    lang: str = ""
    attachLog: bool = False  # the end of poe2lab's log goes with it (the player ticks it, and can see it first)


class ClientError(BaseModel):
    message: str = Field("", max_length=2000)
    stack: str = Field("", max_length=4000)
    tab: str = Field("", max_length=40)


_client_errors = {"n": 0}
CLIENT_ERRORS = 50  # the page's errors logged per run (a broken loop must not fill the log)


@app.post("/api/log")
def client_error(req: ClientError):
    """An error in the page itself (a script error the player saw as a broken tab): into the log."""
    if _client_errors["n"] < CLIENT_ERRORS:
        _client_errors["n"] += 1
        log.error("page error on %s: %s\n%s", req.tab or "?", req.message, req.stack)
    return {"ok": True}


@app.get("/api/log")
def read_log():
    """The end of the log as it would go with a report, and where the log is."""
    return {"path": str(log_file()), "text": log_tail()}


@app.get("/api/feedback")
def feedback_status():
    return {"configured": bool(feedback.relay_url()), "maxImages": feedback.MAX_IMAGES}


@app.post("/api/feedback")
def send_feedback(req: FeedbackRequest):
    """The player's report with the open build (as it is in the file, and with the tree plan if there is one), its
    profile and where they were in the UI."""
    with session.lock:
        session.require()
        e = session.engine
        build = {"name": session.path.stem, "code": feedback.build_code(session.path)}
        if session.plan is not None:
            e.set_custom_mods(CORRECTION_BLOCK, [])
            try:
                build["planCode"] = e.export_code()
            finally:
                e.set_custom_mods(CORRECTION_BLOCK, [c.line for c in session.bp.corrections])
        context = {"tab": req.tab[:40], "mode": req.mode[:20], "lang": req.lang[:5], "mainSkill": e.main_skill(),
                   "treePlan": session.plan["log"] if session.plan else None,
                   "gameTexts": gamedata.status()["unpacked"]}
        profile = _profile_raw() if _profile_path().exists() else None
    if req.attachLog:
        context["log"] = log_tail()
    try:
        feedback.send(feedback.compose(req.message, req.contact, req.images, build, profile, context))
    except feedback.FeedbackError as err:
        raise HTTPException(400, str(err))
    return {"ok": True}


@app.get("/api/craft")
def craft(slot: str, need: int = 3, grade: str = "", item_level: int = 82, quality: str = "good",
          mode: str = "balanced", build: str | None = None):
    """Ways to craft the slot's item from a white or blue base: strategies played out on the base's mod pool, with
    the chance, the currency and its price (see poe2lab.crafting)."""
    grade = {"greater": "Greater ", "perfect": "Perfect "}.get(grade.lower(), "")
    item_level = max(1, min(int(item_level), 100))
    top_tiers = crafting.QUALITY_TIERS.get(quality, crafting.QUALITY_TIERS["good"])
    if mode not in MODES:
        raise HTTPException(400, f"неизвестная цель {mode!r}")
    with session.lock:
        session.require(build)
        e, prof = session.engine, session.profile

        def compute():
            item = next((i for i in e.equipped_item_details() if i["slot"] == slot), None)
            if item is None:
                raise HTTPException(400, f"в слоте {slot} ничего не надето — не из чего взять базу")
            db, prices = session.db(), session.prices()
            weights = defence_weights(survivable_hits(e, prof))
            plan = plan_slot(e, db, prof.config(), item, mode, weights, top=8, check_mana=not prof.mana_sustained)
            targets = crafting.pick_targets(db, plan, item["tags"], item_level, top_tiers=top_tiers)
            if not targets:
                return {"slot": slot, "base": item["baseName"], "targets": [], "strategies": []}
            # an essence (not Perfect/Corrupted: those work on rares) that guarantees a target at its wanted tier:
            # for the most valuable target it can, the cheapest tier of it
            by_id, essence = {m.id: m for m in db.mods}, None
            usable = [(es["name"], by_id.get(es["mods"].get(item["type"], "")))
                      for es in sorted(e.export_essences(), key=lambda x: x["tierLevel"])
                      if not es["name"].startswith(("Perfect", "Corrupted"))]
            for t in targets:
                essence = next(((name, m) for name, m in usable if m and m.group == t.group and
                                m.patterns == t.patterns and m.level >= t.min_level), None)
                if essence:
                    break
            pool = crafting.Pool(db, item["tags"], item_level, item_type=item["type"])
            desecrated = crafting.Pool(db, item["tags"], item_level, sets=("Desecrated",), item_type=item["type"])
            wanted = max(1, min(need, len(targets)))
            found = crafting.strategies(pool, targets, wanted, grade, essence, desecrated,
                                        crafting.bone_for(item["type"]))
            crafting.price(found, prices)
            # cheapest first when priced; otherwise the likeliest
            found.sort(key=lambda x: (x.per_base == 0, x.cost if x.cost is not None and x.priced else 1e9,
                                      -x.per_base))
            priced = {}
            for s_ in found:
                for name in s_.use:
                    price = prices.get(name) if prices else None
                    priced[name] = prices.describe(price) if price else None
            return {"slot": slot, "base": item["baseName"], "itemLevel": item_level, "grade": grade.strip().lower(),
                    "need": wanted, "targets": [asdict(t) | {"patterns": list(t.patterns)} for t in targets],
                    "essence": essence[0] if essence else None, "strategies": [asdict(x) for x in found],
                    "prices": priced, "exaltedPerDivine": prices.exalted_per_divine if prices else None,
                    "league": prices.league if prices else None,
                    "estimatedWeights": not crafting.WEIGHTS_FILE.is_file(),
                    "budget": crafting.BUDGET}

        return _json(session.cached(("craft", slot, need, grade, item_level, top_tiers, mode), compute))


@app.get("/api/craft/guide")
def craft_guide():
    """Prices of the currency the crafting guide names (the guide's text is the page's own)."""
    prices = session.prices()
    if prices is None:
        return {"prices": {}, "league": None, "exaltedPerDivine": None}
    found = {n: prices.get(n) for n in crafting.GUIDE_ITEMS}
    return {"prices": {n: prices.describe(p) for n, p in found.items() if p},
            "league": prices.league, "exaltedPerDivine": prices.exalted_per_divine}


class MarketChoice(BaseModel):
    """The loot filter's market block: what counts as "very valuable" (top) and "valuable" (low), each in exalted
    or divine orbs."""
    market: bool = True
    top: float = 1.0
    top_unit: str = "div"
    low: float = 50.0
    low_unit: str = "ex"


@app.get("/api/lootfilter")
def loot_filter(mode: str = "balanced", build: str | None = None, market: bool = True, top: float = 1.0,
                top_unit: str = "div", low: float = 50.0, low_unit: str = "ex"):
    if mode not in MODES:
        raise HTTPException(400, f"неизвестная цель {mode!r}")
    choice = MarketChoice(market=market, top=top, top_unit=top_unit, low=low, low_unit=low_unit)
    with session.lock:
        session.require(build)
        return _json(_loot(mode, choice) | {"dir": str(lootfilter.filters_dir()),
                                            "localFilters": lootfilter.local_filters(),
                                            "onlineFilters": lootfilter.online_filters()})


def _loot(mode: str, choice: MarketChoice | None = None) -> dict:
    """Rules and filter block for the open build, with the market block when chosen (caller holds the lock)."""
    def compute():
        e, prof = session.engine, session.profile
        weights = defence_weights(survivable_hits(e, prof))
        return lootfilter.slot_rules(e, session.db(), prof.config(), mode, weights)

    rules = session.cached(("lootfilter", mode), compute)
    market = _market(choice) if choice and choice.market else None
    return {"rules": rules, "block": lootfilter.render(rules, session.path.stem, market["blocks"] if market else None),
            "market": {k: v for k, v in market.items() if k != "blocks"} if market else None}


def _market(choice: MarketChoice) -> dict:
    """The market block for the thresholds chosen, priced by poe.ninja in the chosen league."""
    for unit in (choice.top_unit, choice.low_unit):
        if unit not in ("ex", "div"):
            raise HTTPException(400, f"единица цены — ex или div, а не {unit!r}")
    if choice.top <= 0 or choice.low <= 0:
        raise HTTPException(400, "порог цены должен быть больше нуля")
    prices = session.prices()
    if prices is None:
        return {"error": "нет цен poe.ninja (нет связи?) — блок рынка не добавлен", "blocks": []}
    data = session.cached(("market", prices.league), lambda: ninja.market(prices.league))
    rate = data["exaltedPerDivine"] or prices.exalted_per_divine
    if not rate:
        return {"error": "poe.ninja не дал курс exalted/divine — блок рынка не добавлен", "blocks": []}
    valid = gamedata.base_type_names()
    if not valid:
        return {"error": "нет распакованных данных игры, чтобы сверить названия предметов — блок рынка не добавлен "
                         "(с неизвестным игре названием она не примет весь фильтр)", "blocks": []}
    top = choice.top if choice.top_unit == "div" else choice.top / rate
    low = choice.low if choice.low_unit == "div" else choice.low / rate
    blocks, summary = lootfilter.market_blocks(data, top, low, valid)
    return {"blocks": blocks, "league": prices.league, "exaltedPerDivine": rate, "topDiv": top, "lowDiv": low,
            "summary": summary}


class LootFilterSave(MarketChoice):
    mode: str = "balanced"
    source: str = "none"  # "file": a filter in the game's folder, "text": pasted, "none": the block alone
    file: str | None = None
    text: str | None = None
    name: str | None = None


@app.post("/api/lootfilter/pick")
def loot_filter_pick():
    """The player picks their filter in a Windows dialog (the page cannot open a given folder itself)."""
    path = lootfilter.pick_filter()
    if path is None:
        return {"cancelled": True}
    if not path.is_file() or not lootfilter.looks_like_filter(path):
        raise HTTPException(400, f"это не файл лут-фильтра: {path.name}")
    session.picked_filter = path
    online = next((f for f in lootfilter.online_filters() if Path(f["path"]) == path), None)
    return {"path": str(path), "name": online["name"] if online else path.name}


@app.post("/api/lootfilter/save")
def loot_filter_save(req: LootFilterSave):
    """Write "the player's filter + the build block" as a new filter in the game's folder; the player's own file
    is never changed."""
    with session.lock:
        session.require()
        if req.mode not in MODES:
            raise HTTPException(400, f"неизвестная цель {req.mode!r}")
        block = _loot(req.mode, req)["block"]
        folder = lootfilter.filters_dir()
        base = ""
        if req.source == "file":
            picked = session.picked_filter
            # the file chosen in the dialog (anywhere), the game's copy of an online filter, or one of the game's
            # folder by name
            online = {f["path"]: f["name"] for f in lootfilter.online_filters()}
            if picked is not None and req.file == str(picked):
                src = picked
            elif req.file in online:
                src = Path(req.file)
            else:
                src = folder / Path(req.file or "").name
            if not src.is_file():
                raise HTTPException(400, f"нет файла фильтра {src}")
            base = src.read_text(encoding="utf-8-sig", errors="replace")
            label = online.get(str(src)) or (online.get(str(picked)) if src == picked else None) or src.stem
            default = f"{label} + poe2lab {session.path.stem}"
        elif req.source == "text":
            base = req.text or ""
            if "Show" not in base and "Hide" not in base:
                raise HTTPException(400, "вставленный текст не похож на лут-фильтр (нет блоков Show/Hide)")
            default = f"мой фильтр + poe2lab {session.path.stem}"
        else:
            default = f"poe2lab {session.path.stem}"
        name = lootfilter.safe_name(req.name or default)
        target = folder / f"{name}.filter"
        if req.source == "file" and target.resolve() == src.resolve():
            raise HTTPException(400, "имя совпадает с исходным фильтром — выберите другое, исходный файл не меняется")
        folder.mkdir(parents=True, exist_ok=True)
        target.write_text(lootfilter.merge(block, base) if base else block, encoding="utf-8")
        return {"path": str(target), "name": name}


@app.get("/api/versus")
def versus_view(ref: str, build: str | None = None):
    with session.lock:
        session.require(build)
        _, engine, bp = _reference(ref)
        return _json(session.cached(("versus", ref), lambda: versus(
            # the reference against the same enemy as the player's character: compared at the player's stage
            session.engine, session.profile, engine,
            replace(session.profile, rage=bp.rage, mana_sustained=bp.mana_sustained))))


@app.get("/api/versus/gear")
def versus_gear(ref: str, build: str | None = None):
    """The reference build's gear as the page shows it (the inventory next to the player's), with who it is."""
    with session.lock:
        session.require(build)
        _, engine, _ = _reference(ref)
        info = engine.info()
        return {"name": ref, "items": engine.equipped_item_details(), "level": info["level"],
                "class": info["class"], "ascendancy": info["ascendancy"], "skill": engine.main_skill()}


@app.get("/api/versus/skills")
def versus_skills(ref: str = RECORDED, build: str | None = None):
    """The reference build's gem groups next to the player's: which gems the build has that the character lacks."""
    with session.lock:
        session.require(build)
        _, engine, _ = _reference(ref)
        return _json({"mine": session.engine.skill_groups(), "ref": engine.skill_groups(), "refSkill": engine.main_skill()})


@app.get("/api/versus/tree")
def versus_tree(ref: str = RECORDED, build: str | None = None):
    """The reference build's passives against the character's: what the build has that the character has not taken
    yet (`missing`) and what the character took that the build does not (`extra`), with both trees' points."""
    starts = ("ClassStart", "AscendClassStart")
    with session.lock:
        session.require(build)
        _, engine, _ = _reference(ref)
        mine = {n["id"]: n for n in session.engine.allocated_nodes() if n["type"] not in starts}
        theirs = {n["id"]: n for n in engine.allocated_nodes() if n["type"] not in starts}
        # each node's lines, from the tree it is in (the build's ascendancy may not be the character's)
        missing = [i for i in theirs if i not in mine]
        extra = [i for i in mine if i not in theirs]
        their_lines = engine.node_lines(missing) if missing else {}
        my_lines = session.engine.node_lines(extra) if extra else {}

        def jewels(e) -> dict:  # a socket's jewel: what the socket is for
            out = {}
            for s in e.jewel_sockets():
                if s["item"]:
                    it = s["item"]
                    out[s["node"]] = {"name": it["name"], "base": it.get("baseName", ""), "rarity": it.get("rarity", ""),
                                      "lines": [x["line"] for k in ("implicit", "explicit") for x in it.get(k, [])]}
            return out
        their_jewels, my_jewels = jewels(engine), jewels(session.engine)
        return _json({"missing": [theirs[i] | {"stats": their_lines.get(i, []), "jewel": their_jewels.get(i)} for i in missing],
                      "extra": [mine[i] | {"stats": my_lines.get(i, []), "jewel": my_jewels.get(i)} for i in extra],
                      "points": session.engine.points_budget(), "refPoints": engine.points_budget()})


@app.get("/api/versus/item")
def versus_item(ref: str, slot: str):
    with session.lock:
        session.require()
        _, engine, _ = _reference(ref)
        return {"text": _errors(lambda: engine.item_text(slot))}


@app.get("/api/item/{slot}")
def item_text(slot: str):
    with session.lock:
        session.require()
        return {"text": _errors(lambda: session.engine.item_text(slot))}


def _english_item(text: str, jewel: bool = False) -> str:
    """PoB reads item text in English only: an item copied from the Russian client is translated first (a jewel
    by the jewel affixes)."""
    if not itemtext.is_russian(text):
        return text
    db, key = (session.jewel_db(), "jewel-names") if jewel else (session.db(), "names")
    if key not in _bare:
        _bare[key] = journal.Names(db)
    uniques = session.cached("unique-catalog", session.engine.unique_catalog)
    try:
        return itemtext.to_english(text, db, _bare[key], uniques)
    except itemtext.TranslationError as err:
        raise HTTPException(400, f"не смог прочитать предмет: {err}")


@app.post("/api/compare")
def compare_item(req: CompareRequest):
    with session.lock:
        session.require()
        cfg = session.profile.config()
        text = _english_item(req.text)
        result = asdict(_errors(lambda: compare(session.engine, cfg, req.slot, text)))
        result["item"] = _errors(lambda: session.engine.parse_item(text))  # the candidate as the page shows it
        if req.breakeven:
            res = _errors(lambda: breakeven(session.engine, cfg, req.slot, text, req.breakeven))
            result["breakeven"] = None if res is None else {"factor": res[0], "line": res[1]}
        return _json(result)


@app.get("/api/leagues")
def leagues_view():
    """The PoE2 leagues the trade site knows, the one chosen for prices and trade searches (None: poe.ninja's
    current league), and the one in use now."""
    try:
        names = [l["id"] for l in _trade_data("en", "leagues") if l.get("realm", "poe2") == "poe2"]
    except OSError:
        try:
            names = ninja.leagues()
        except OSError:
            names = []
    # prices do not touch the engine: fetched without holding the build (the first fetch takes a while)
    prices = session.prices() if session.engine is not None else None
    return {"leagues": names, "chosen": ninja.chosen_league(), "current": prices.league if prices else None}


class LeagueChoice(BaseModel):
    league: str | None = None  # None: back to poe.ninja's current league


@app.put("/api/leagues")
def leagues_choose(req: LeagueChoice):
    league = (req.league or "").strip() or None
    ninja.choose_league(league)
    with session.lock:
        session._prices = False  # prices of the new league on the next request
        session.cache = {k: v for k, v in session.cache.items() if k == "db"}  # what was priced in the old one
    return leagues_view()


class TradeRequest(BaseModel):
    slot: str
    mode: str = "balanced"
    threshold: float = 15.0  # how much better (score points, % of the build) an item must be to be offered
    status: str = "online"  # sellers online now; "available": also instant buyout listings


@app.post("/api/trade/search")
def trade_search(req: TradeRequest):
    """A better item for one slot on the trade site: the key mods, then an item made for the build; the cheapest
    listings of each search are put on the build by PoB, and those better by the threshold come first."""
    if req.mode not in MODES:
        raise HTTPException(400, f"неизвестная цель {req.mode!r}")
    if req.status not in trade.STATUSES:
        raise HTTPException(400, f"продавцы: {' или '.join(trade.STATUSES)}, а не {req.status!r}")
    with session.lock:
        session.require()
        e, prof = session.engine, session.profile
        item = next((i for i in e.equipped_item_details() if i["slot"] == req.slot), None)
        if item is None:
            raise HTTPException(404, f"в слоте {req.slot} ничего нет")
        cat = trade.category(item["type"], item["tags"])
        if cat is None or item["rarity"] not in AFFIX_LIMIT:
            raise HTTPException(400, "поиск замены — для редких и магических вещей экипировки")
        prices = session.prices()
        league = prices.league if prices else (session.bp.league or "Standard")
        level = int(e.info()["level"] or 1)
        cfg, weights = prof.config(), defence_weights(survivable_hits(e, prof))
        gear_cache = session.cache.get(("gear", req.mode))
        plan = next((p for p in gear_cache["slots"] if p["slot"] == req.slot), None) if gear_cache else None
        if plan is None:
            plan = asdict(plan_slot(e, session.db(), cfg, item, req.mode, weights, top=4,
                                    check_mana=not prof.mana_sustained))
        mods = trade.pick_mods(session.db(), plan, item["tags"], level)
        bare = e.what_if(config=cfg, remove_slot=req.slot)
        attributes = {k.lower(): bare.get(k, 0) for k in ("Str", "Dex", "Int")}
    if not mods:
        raise HTTPException(400, "не нашёл, по каким модам искать: PoB не видит у слота ценных модов")

    searches = []
    for q in trade.queries(mods, cat, level, attributes, req.status):
        entry = {"kind": q["kind"], "mods": q["mods"], "relaxed": False, "total": 0, "url": None, "items": [],
                 "error": None}
        try:
            found = trade.search(league, q["body"])
            for n, body in q["relaxed"]:  # nothing has them all: fewer of them
                if found.get("result"):
                    break
                found, entry["relaxed"] = trade.search(league, body), n
            entry["total"], entry["url"] = found.get("total", 0), trade.search_url(league, found["id"])
            entry["listings"] = trade.fetch(found["id"], found.get("result", [])[:trade.FETCH])
        except trade.TradeError as err:
            entry["error"] = str(err)
        searches.append(entry)

    with session.lock:
        session.require()
        if session.engine is not e:  # another build, or the same one read again: its numbers are not these
            raise HTTPException(409, "пока шёл поиск, билд открыли заново — повтори поиск")
        base = e.what_if(config=cfg)
        for entry in searches:
            for listing in entry.pop("listings", []):
                it, text = listing.get("item", {}), trade.item_text(listing.get("item", {}))
                row = {"name": trade.plain(it.get("name", "")), "base": trade.plain(it.get("baseType", "")),
                       "rarity": it.get("rarity", ""), "ilvl": it.get("ilvl"), "corrupted": bool(it.get("corrupted")),
                       "implicit": trade.mod_lines(it.get("implicitMods")) + trade.mod_lines(it.get("runeMods")),
                       "explicit": trade.mod_lines(it.get("fracturedMods")) + trade.mod_lines(it.get("explicitMods"))
                       + trade.mod_lines(it.get("desecratedMods")),
                       "price": trade.price(listing.get("listing"), prices),
                       "whisper": (listing.get("listing") or {}).get("whisper"),
                       "seller": ((listing.get("listing") or {}).get("account") or {}).get("name"),
                       "score": None, "changes": {}, "unmet": [], "better": False}
                try:
                    new = e.what_if(config=cfg, replace_item=(req.slot, text))
                except PobError as err:
                    row["error"] = f"PoB не прочитал предмет: {err}"
                    entry["items"].append(row)
                    continue
                changes = metric_changes(new, base)
                row["changes"], row["score"] = changes, report_score(SimpleNamespace(one=changes), req.mode, weights)
                row["unmet"] = [a for a in ("Str", "Dex", "Int")
                                if new.get(f"Req{a}", 0) - new.get(a, 0) > max(base.get(f"Req{a}", 0) - base.get(a, 0), 0)]
                row["better"] = row["score"] >= req.threshold and not row["unmet"]
                entry["items"].append(row)
            entry["items"].sort(key=lambda r: (not r["better"], (r["price"] or {}).get("ex") or 1e9))
    return _json({"slot": req.slot, "league": league, "threshold": req.threshold, "status": req.status,
                  "searches": searches})


def _profile_path() -> Path:
    return PROJECT_BUILDS / f"{session.path.stem}.profile.json"


def _profile_raw() -> dict:
    p = _profile_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    # No profile yet: offer what the build itself says, so a fresh build never inherits another build's answers.
    return {"main_skill": {}, "rage": session.bp.rage, "mana_sustained": False, "league": None,
            "corrections": [], "notes": []}


@app.put("/api/profile")
def save_profile(raw: dict):
    with session.lock:
        session.require()
        for c in raw.get("corrections", []):
            if not session.engine.can_parse_mod(c.get("mod", "")):
                raise HTTPException(400, f"PoB не понимает строку поправки: {c.get('mod')!r}")
        path = _profile_path()
        before = path.read_text(encoding="utf-8") if path.exists() else None
        if before:  # the levelling and quest answers are saved by their own pages
            raw = {k: v for k, v in json.loads(before).items() if k in ("leveling", "quests")} | raw
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            session.load(str(session.path))
        except (PobError, OSError, ValueError, TypeError, KeyError) as err:
            # a profile the build cannot open with is not kept: the previous one comes back
            if before is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(before, encoding="utf-8")
            _errors(lambda: session.load(str(session.path)))
            raise HTTPException(400, f"профиль не сохранён: {err}")
        return _json(_summary())


# ---------- every gem the game gives, for the hover card of any gem name (not only the open build's) ----------
_gem_texts: list = []


@app.get("/api/gems")
def gems_all():
    with session.lock:
        session.require()
        if not _gem_texts:  # the game's gems do not change while the server runs
            _gem_texts.extend({k: g[k] for k in ("name", "support", "description", "lines", "tags")}
                              for g in session.engine.gem_texts())
        return _gem_texts


# ---------- the campaign's rewards: which to take (poe2lab.analysis.quests) ----------
@app.get("/api/quests")
def quests_get(mode: str = "balanced", build: str | None = None):
    if mode not in MODES:
        raise HTTPException(400, f"неизвестная цель {mode!r}")
    with session.lock:
        session.require(build)
        return _json(session.cached(("quests", mode), lambda: quest_rewards.rewards(session.engine, session.profile, mode)))


class QuestAnswer(BaseModel):
    var: str
    value: str | bool


@app.post("/api/quests")
def quests_save(req: QuestAnswer, mode: str = "balanced", build: str | None = None):
    """The reward the player took (or not): kept in the build profile and set in PoB, so every number counts it."""
    with session.lock:
        session.require(build)
        if not quest_rewards.valid(session.engine.quest_rewards(), req.var, req.value):
            raise HTTPException(400, "нет такой награды или варианта")
        path = _profile_path()
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        raw["quests"] = (raw.get("quests") or {}) | {req.var: req.value}
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        session.bp.quests = raw["quests"]
        session.engine.set_config_input({req.var: req.value})
        session.cache.clear()  # every number moves with it
        session.ref = None  # a reference build opens with the profile again
        session.assistant = session.toolbox = None
        return _json(session.cached(("quests", mode), lambda: quest_rewards.rewards(session.engine, session.profile, mode)))


# ---------- levelling up to the build (poe2lab.analysis.leveling) ----------
class LevelingAnswers(BaseModel):
    way: str
    trade: bool = True
    pace: str = "fast"  # fast | safe
    novice: bool = False


def _leveling_view():
    """The ways the build's class can level, the player's answers (the build profile's "leveling") and the roadmap
    for them. It is about the build as its file has it - the guide - also when the player's character is in it;
    the character's level then marks where the player is."""
    if session.main is not None:
        _, engine, bp = _reference(RECORDED)
        here = session.engine.info()["level"]
    else:
        engine, bp, here = session.engine, session.bp, None
    answers = _profile_raw().get("leveling") if _profile_path().exists() else None
    ways = session.cached(("leveling-ways",), lambda: leveling.ways(engine))
    road = None
    if answers:
        key = ("leveling", json.dumps(answers, sort_keys=True))
        road = session.cached(key, lambda: leveling.roadmap(engine, bp.rage, bp.mana_sustained, answers, here))
    return _json({"ways": ways, "answers": answers, "roadmap": road, "characterLevel": here})


@app.get("/api/leveling")
def leveling_get(build: str | None = None):
    with session.lock:
        session.require(build)
        return _errors(_leveling_view)


@app.post("/api/leveling")
def leveling_save(req: LevelingAnswers, build: str | None = None):
    """The player's answers kept in the build profile, and the roadmap for them."""
    if req.pace not in ("fast", "safe"):
        raise HTTPException(400, f"неизвестный темп {req.pace!r}")
    with session.lock:
        session.require(build)
        path = _profile_path()
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        raw["leveling"] = req.model_dump()
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        return _errors(_leveling_view)


@app.post("/api/chat")
def chat(req: ChatRequest):
    cfg = LLMConfig.current()
    if cfg is None:
        raise HTTPException(400, "ИИ не настроен: выберите провайдера и введите ключ на вкладке «Ассистент»")
    with _chat_lock:  # one conversation at a time
        with session.lock:
            session.require()
            if session.assistant is None:
                target, target_text, target_names = _assistant_target()
                # the tools take the build's lock themselves: the model's answer is awaited without holding it
                session.toolbox = Toolbox(session.engine, session.profile, session.db(), target, lock=session.lock)
                names = i18n(req.lang)["names"] if req.lang != "en" else {}
                glossary = build_glossary(session.engine, names, target_names) if names else None
                session.assistant = Assistant(make_client(cfg), session.toolbox,
                                              build_context(session.engine, session.bp, glossary,
                                                            session.profile.config(), target_text),
                                              style=load_settings().get("style", "short"))
            assistant, toolbox = session.assistant, session.toolbox
        start = len(assistant.tool_log)
        try:
            answer = assistant.ask(req.message)
        except LLMError as err:
            raise HTTPException(502, str(err))
        return {"answer": answer, "tools": assistant.tool_log[start:], "proposals": toolbox.proposals}


_chat_lock = threading.Lock()


class PromptRequest(BaseModel):
    question: str
    size: str = "compact"  # compact | full
    style: str = "short"
    lang: str = "ru"


@app.post("/api/chat/prompt")
def chat_prompt(req: PromptRequest):
    """A prompt for any chat AI, no key needed: the question, the rules, the build and PoB's reports for its topic
    (poe2lab.assistant.prompt) - the player copies it into ChatGPT, DeepSeek, Claude, Gemini."""
    if not req.question.strip():
        raise HTTPException(400, "напиши вопрос")
    with session.lock:
        session.require()
        target, target_text, target_names = _assistant_target()
        names = i18n(req.lang)["names"] if req.lang != "en" else {}
        glossary = build_glossary(session.engine, names, target_names) if names else None
        return _json(prompt_builder.make(session.engine, session.bp, session.profile, session.db(), req.question,
                                         size=req.size, style=req.style, lang=req.lang, glossary=glossary,
                                         target=target, target_text=target_text))


def _assistant_target() -> tuple[dict | None, str | None, list[str]]:
    """The build the profile names as the target, loaded (as the comparison reference), its picture next to the
    character's for the assistant's context, and the names it brings (for their official translations);
    (None, None, []) without one or when it cannot be opened."""
    name = session.bp.target if session.bp else None
    if not name and session.main is None:
        return None, None, []
    try:  # with the player's character in the build and no target named, the build itself is the guide
        _, engine, bp = _reference(name or RECORDED)
    except HTTPException:
        return None, None, []
    from ..analysis.target import context_text, summary
    profile = MapProfile.for_level(engine.info()["level"], rage=bp.rage, mana_sustained=bp.mana_sustained)
    name = name or f"{session.path.stem} (гайд)"
    target = {"name": name, "engine": engine, "profile": profile}
    goal = summary(engine, profile.config(), name)
    names = goal["notables"] + goal["ascendancyNotables"] + goal["keystones"] + [s["name"] for s in goal["skills"]]
    return target, context_text(summary(session.engine, session.profile.config(), session.path.stem), goal), names


# ---------- the player's own AI app over MCP (poe2lab.mcpserver, poe2lab.mcpconnect) ----------
@app.get("/api/mcp")
def mcp_status():
    return mcpconnect.status()


@app.post("/api/mcp/claude-desktop")
def mcp_connect():
    try:
        return mcpconnect.connect()
    except mcpconnect.ConnectError as err:
        raise HTTPException(400, str(err))


@app.delete("/api/mcp/claude-desktop")
def mcp_disconnect():
    try:
        return mcpconnect.disconnect()
    except mcpconnect.ConnectError as err:
        raise HTTPException(400, str(err))


@app.post("/api/chat/reset")
def chat_reset():
    session.assistant = session.toolbox = None
    return {"ok": True}


@app.get("/api/glossary")
def glossary_view(lang: str = "ru"):
    """The beginner's glossary page: groups of terms in our own words (poe2lab.glossary)."""
    return {"groups": glossary.groups(lang), "terms": glossary.entries(lang)}


# ---------- craft journal: mods rolled in game -> the hidden mod weights (poe2lab.journal) ----------

recorder = journal.Recorder()
_parsed: dict = {}  # journal record id -> its parsed item: records never change, parsing them once is enough


_bare: dict = {}  # the mod data without a build: the journal does not need one open


def _journal_db() -> ModDB:
    if session.engine is not None:
        return session.db()
    if "db" not in _bare:
        _bare["db"] = ModDB.from_engine(PobEngine())
    return _bare["db"]


def _journal_rows():
    db = _journal_db()
    if "names" not in _bare:
        _bare["names"] = journal.Names(db)  # names do not depend on the build
    return journal.interpret(journal.entries(), db, _bare["names"], _parsed)


def _estimate_summary(est):
    return {k: v for k, v in est.items() if k != "weights"} if est else None


@app.get("/api/journal")
def journal_view(limit: int = 40):
    out = {"recording": recorder.on, "available": recorder.available(), "recordedNow": recorder.count,
           "hotkey": recorder.hotkey, "grade": recorder.grade,
           "estimate": _estimate_summary(journal.load_estimate()), "applied": crafting.WEIGHTS_FILE.is_file()}
    with session.lock:
        rows, samples = _journal_rows()
    classes = {}
    for s in samples:
        c = classes.setdefault(s.item_class, {"records": 0, "draws": 0})
        c["records"] += 1
        c["draws"] += len(s.added)
    shown = []
    for r in rows[::-1][:limit]:
        p = r["parsed"]
        shown.append({"id": r["id"], "t": r["t"], "source": r["source"], "how": r["how"], "detail": r["detail"],
                      "draws": r["draws"],
                      "rarity": p.rarity, "base": p.base, "itemLevel": p.item_level, "problems": p.problems,
                      "grade": r["grade"],
                      "mods": [{"side": m.side, "tier": m.tier, "kind": m.kind, "lines": list(m.mod.lines)}
                               for m in p.mods]})
    return _json(out | {"total": len(rows), "draws": sum(len(s.added) for s in samples), "classes": classes,
                        "entries": shown, "plan": journal.plan(rows, samples), "classNames": _class_names()})


def _class_names():
    if "classes" not in _bare:
        _bare["classes"] = journal.class_names()
    return _bare["classes"]


class RecordRequest(BaseModel):
    on: bool


@app.post("/api/journal/record")
def journal_record(req: RecordRequest):
    if req.on and not recorder.available():
        raise HTTPException(400, "запись буфера обмена работает только в Windows")
    recorder.start() if req.on else recorder.stop()
    return {"recording": recorder.on}


class GradeRequest(BaseModel):
    grade: str


@app.post("/api/journal/grade")
def journal_grade(req: GradeRequest):
    if req.grade not in journal.GRADES:
        raise HTTPException(400, f"неизвестный вид сфер: {req.grade}")
    recorder.grade = req.grade
    return {"grade": recorder.grade}


class JournalText(BaseModel):
    text: str


@app.post("/api/journal/add")
def journal_add(req: JournalText):
    if not journal.is_item_text(req.text):
        raise HTTPException(400, "это не текст предмета: в игре наведи на вещь и нажми Ctrl+Alt+C")
    return journal.add(req.text, "manual", recorder.grade)


@app.delete("/api/journal/entry/{entry_id}")
def journal_remove(entry_id: str):
    if not journal.remove(entry_id):
        raise HTTPException(404, "такой записи нет")
    return {"ok": True}


@app.post("/api/journal/estimate")
def journal_estimate():
    with session.lock:
        _, samples = _journal_rows()
        if not samples:
            raise HTTPException(400, "в журнале нет ни одной пробы — сначала запиши несколько вещей")
        result = journal.estimate(_journal_db(), samples)
    journal.save_estimate(result)
    return _json(_estimate_summary(result))


def _drop_craft_results():
    for key in [k for k in session.cache if isinstance(k, tuple) and k[0] == "craft"]:
        del session.cache[key]


@app.post("/api/journal/apply")
def journal_apply():
    est = journal.load_estimate()
    if not est:
        raise HTTPException(400, "сначала посчитай веса")
    crafting.WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    applied = dict(est["weights"])
    # measured thresholds of Greater / Perfect orbs, once there are enough draws to trust them
    applied["grades"] = {g: {"minLevel": journal.crafting_level(t),
                             "lowFamilies": True if t["lowFamilies"] is None else t["lowFamilies"]}
                         for g, t in (est.get("thresholds") or {}).items() if t["draws"] >= journal.MIN_GRADE_DRAWS}
    crafting.WEIGHTS_FILE.write_text(json.dumps(applied), encoding="utf-8")
    with session.lock:
        _drop_craft_results()
    return {"applied": True}


@app.delete("/api/journal/apply")
def journal_unapply():
    crafting.WEIGHTS_FILE.unlink(missing_ok=True)
    with session.lock:
        _drop_craft_results()
    return {"applied": False}


@app.get("/api/journal/export")
def journal_export():
    path = journal.journal_path()
    if not path.is_file():
        raise HTTPException(404, "журнал пуст")
    return FileResponse(path, filename="poe2lab-craft-journal.jsonl", media_type="application/jsonl")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/icons", StaticFiles(directory=icons.ICONS, check_dir=False), name="icons")


@app.get("/")
def index():
    # version static URLs by modification time so browsers never run a stale script
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for name in ("app.js", "i18n.js", "pob_labels.js", "treeart.js", "app.css"):
        html = html.replace(f"/static/{name}", f"/static/{name}?v={int((STATIC / name).stat().st_mtime)}")
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})
