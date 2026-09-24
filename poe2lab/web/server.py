"""Local web interface: one loaded build, heavy analyses cached, everything served as JSON to a static page."""
import json
import re
import threading
from dataclasses import asdict, replace
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..analysis.changes import capture as capture_build, diff as build_diff
from ..analysis.items import breakeven, compare
from ..analysis.skills import build_view as skill_build_view, leveling_view as skill_leveling_view
from ..analysis.uniques import suggest as suggest_uniques
from ..analysis.report import MODES, build_report, defence_weights
from ..analysis.gradients import metric_changes
from ..analysis.tree import analyse as analyse_tree
from ..analysis.tree import optimize as optimize_tree
from ..analysis.slots import craft_path, plan_all, plan_slot
from ..analysis.sockets import plan_sockets
from ..analysis.sources import describe as describe_sources
from ..analysis.threats import MapProfile, survivable_hits
from ..analysis.versus import versus
from ..assistant import (Assistant, LLMConfig, LLMError, Toolbox, build_context, build_glossary, list_models,
                         make_client)
from ..assistant.agent import STYLES
from ..assistant.providers import BY_ID, PROVIDERS, key_hint, load_settings, save_settings
from ..data.moddb import ModDB
from ..economy.ninja import PriceBook
from ..engine import PobError
from .. import crafting, feedback, gamedata, icons, library, lootfilter, pobapp
from ..i18n import dictionary as translation_dictionary
from ..i18n import pob_line, stat_templates
from ..knowledge import collect as collect_mechanics
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
        self.path = resolve_build(name)
        self.mtime = self.path.stat().st_mtime
        self.engine, self.bp = open_build(self.path, group, skill)
        self.level = self.engine.info()["level"]
        self.plan = None
        self.cache.clear()
        self.assistant = self.toolbox = None

    def file_changed(self) -> bool:
        try:
            return self.path is not None and self.path.stat().st_mtime > self.mtime
        except OSError:
            return False

    def cached(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    def db(self) -> ModDB:
        return self.cached("db", lambda: ModDB.from_engine(self.engine))

    def prices(self) -> PriceBook | None:
        if self._prices is False:
            try:
                self._prices = PriceBook.load(self.bp.league if self.bp else None)
            except OSError:
                self._prices = None
        return self._prices


session = Session()
app = FastAPI(title="poe2lab")
app.add_middleware(GZipMiddleware, minimum_size=4096)  # the RU dictionary is several MB

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
    code: str  # PoB code or a pobb.in link


@app.post("/api/builds")
def add_build(req: AddBuildRequest):
    try:
        return {"name": library.add(req.name, req.code)}
    except library.LibraryError as err:
        raise HTTPException(400, str(err))


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
        if session.ref is not None and session.ref[0] == name:
            session.ref = None
        if session.path is not None and session.path.stem == name:  # the open build is gone: close it
            session.path = session.engine = session.bp = None
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
            "kind": "pob" if session.path.suffix.lower() == ".xml" else "code"}


@app.post("/api/load")
def load(req: LoadRequest):
    with session.lock:
        _errors(lambda: session.load(req.name, req.group, req.skill))
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
            try:
                library.replace(name, req.code)
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
            for s in craft_path(e, db, prof.config(), mode, weights, steps=6, check_mana=check_mana):
                mod = by_id.get(s.mod_id)
                path.append(asdict(s) | {"sources": describe_sources(db, essences, mod, s.item_type, prices) if mod else []})
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


@app.get("/api/mechanics")
def mechanics(build: str | None = None):
    with session.lock:
        session.require(build)
        m = session.cached("mechanics", lambda: collect_mechanics(session.engine, _game_texts("ru")))
        return _json({"gaps": m.gaps, "skills": m.skills, "uniques": m.uniques})


@app.get("/api/skills")
def skills_view(view: str = "build", scope: str = "level", build: str | None = None):
    """The build's skills: each with its support gems and the links between skills ("build"), or when each gem can
    be had and what to socket meanwhile while levelling ("leveling")."""
    if view not in ("build", "leveling", "uniques"):
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
                data = data | {"level": session.level}
        else:
            data = session.cached(("skills", "leveling"), lambda: skill_leveling_view(e, cfg))
        return _json(data)


def _reference(name: str):
    """The reference build (a guide to compare against), kept loaded in its own engine while it is in use."""
    if name == session.path.stem:
        raise HTTPException(400, "эталон — это другой билд, не открытый")
    if session.ref is None or session.ref[0] != name:
        session.ref = None  # free the previous reference first
        engine, bp = _errors(lambda: open_build(resolve_build(name)))
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
        return _json(result | {"plan": _plan_view()})


# ---- tree plans: edits of the passive tree in the engine only; the build file is never changed ----

def _plan_start():
    if session.plan is None:
        session.engine.tree_snapshot("plan-base")
        session.plan = {"budget": session.engine.tree_points(),
                        "base": session.engine.what_if(config=session.profile.config()), "log": []}


def _plan_changed():
    """Every analysis now sees the planned tree: drop cached results (the mod database does not depend on it)."""
    session.cache = {k: v for k, v in session.cache.items() if k == "db"}
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


@app.post("/api/tree/add")
def tree_add(req: TreeEdit):
    with session.lock:
        session.require()
        _plan_start()
        names = _errors(lambda: session.engine.tree_add(req.id))
        session.plan["log"].append({"action": "add", "target": req.name, "nodes": names})
        _plan_changed()
        return _json(_plan_view())


@app.post("/api/tree/remove")
def tree_remove(req: TreeEdit):
    with session.lock:
        session.require()
        _plan_start()
        names = _errors(lambda: session.engine.tree_remove(req.id))
        session.plan["log"].append({"action": "remove", "target": req.name, "nodes": names})
        _plan_changed()
        return _json(_plan_view())


@app.post("/api/tree/reset")
def tree_reset():
    with session.lock:
        session.require()
        if session.plan is not None:
            session.engine.tree_restore("plan-base")
            session.plan = None
            _plan_changed()
        return {"ok": True}


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
        engine, bp = session.engine, session.bp
        # the profile's corrections live in PoB's Custom Modifiers; the copied profile re-applies them
        engine.set_custom_mods(CORRECTION_BLOCK, [])
        try:
            code = engine.export_code()
        finally:
            engine.set_custom_mods(CORRECTION_BLOCK, [c.line for c in bp.corrections])
        try:
            name = library.add(req.name or f"{session.path.stem} план", code)
        except library.LibraryError as err:
            raise HTTPException(400, str(err))
        src = _profile_path()
        if src.exists():
            (PROJECT_BUILDS / f"{name}.profile.json").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return {"name": name}


class FeedbackRequest(BaseModel):
    message: str
    contact: str = ""
    images: list[str] = []  # data: URLs of pasted or chosen screenshots
    tab: str = ""
    mode: str = ""
    lang: str = ""


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
    try:
        feedback.send(feedback.compose(req.message, req.contact, req.images, build, profile, context))
    except feedback.FeedbackError as err:
        raise HTTPException(400, str(err))
    return {"ok": True}


@app.get("/api/craft")
def craft(slot: str, need: int = 3, grade: str = "", item_level: int = 82, mode: str = "balanced",
          build: str | None = None):
    """Ways to craft the slot's item from a white or blue base: strategies played out on the base's mod pool, with
    the chance, the currency and its price (see poe2lab.crafting)."""
    grade = {"greater": "Greater ", "perfect": "Perfect "}.get(grade.lower(), "")
    item_level = max(1, min(int(item_level), 100))
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
            targets = crafting.pick_targets(db, plan, item["tags"], item_level)
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
            pool = crafting.Pool(db, item["tags"], item_level)
            desecrated = crafting.Pool(db, item["tags"], item_level, sets=("Desecrated",))
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
                    "estimatedWeights": not crafting.WEIGHTS_FILE.is_file()}

        return _json(session.cached(("craft", slot, need, grade, item_level, mode), compute))


@app.get("/api/lootfilter")
def loot_filter(mode: str = "balanced", build: str | None = None):
    if mode not in MODES:
        raise HTTPException(400, f"неизвестная цель {mode!r}")
    with session.lock:
        session.require(build)
        return _json(_loot(mode) | {"dir": str(lootfilter.filters_dir()), "localFilters": lootfilter.local_filters(),
                                    "onlineFilters": lootfilter.online_filters()})


def _loot(mode: str) -> dict:
    """Rules and filter block for the open build (caller holds the session lock)."""
    def compute():
        e, prof = session.engine, session.profile
        weights = defence_weights(survivable_hits(e, prof))
        rules = lootfilter.slot_rules(e, session.db(), prof.config(), mode, weights)
        return {"rules": rules, "block": lootfilter.render(rules, session.path.stem)}

    return session.cached(("lootfilter", mode), compute)


class LootFilterSave(BaseModel):
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
        block = _loot(req.mode)["block"]
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


@app.post("/api/compare")
def compare_item(req: CompareRequest):
    with session.lock:
        session.require()
        cfg = session.profile.config()
        result = asdict(_errors(lambda: compare(session.engine, cfg, req.slot, req.text)))
        if req.breakeven:
            res = _errors(lambda: breakeven(session.engine, cfg, req.slot, req.text, req.breakeven))
            result["breakeven"] = None if res is None else {"factor": res[0], "line": res[1]}
        return _json(result)


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
        _profile_path().write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        _errors(lambda: session.load(str(session.path)))
        return _json(_summary())


@app.post("/api/chat")
def chat(req: ChatRequest):
    cfg = LLMConfig.current()
    if cfg is None:
        raise HTTPException(400, "ИИ не настроен: выберите провайдера и введите ключ на вкладке «Ассистент»")
    with session.lock:
        session.require()
        if session.assistant is None:
            session.toolbox = Toolbox(session.engine, session.profile, session.db())
            names = i18n(req.lang)["names"] if req.lang != "en" else {}
            glossary = build_glossary(session.engine, names) if names else None
            session.assistant = Assistant(make_client(cfg), session.toolbox,
                                          build_context(session.engine, session.bp, glossary),
                                          style=load_settings().get("style", "short"))
        start = len(session.assistant.tool_log)
        try:
            answer = session.assistant.ask(req.message)
        except LLMError as err:
            raise HTTPException(502, str(err))
        return {"answer": answer, "tools": session.assistant.tool_log[start:], "proposals": session.toolbox.proposals}


@app.post("/api/chat/reset")
def chat_reset():
    session.assistant = session.toolbox = None
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/icons", StaticFiles(directory=icons.ICONS, check_dir=False), name="icons")


@app.get("/")
def index():
    # version static URLs by modification time so browsers never run a stale script
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for name in ("app.js", "i18n.js", "pob_labels.js", "app.css"):
        html = html.replace(f"/static/{name}", f"/static/{name}?v={int((STATIC / name).stat().st_mtime)}")
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})
