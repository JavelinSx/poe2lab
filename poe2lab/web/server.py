"""Local web interface: one loaded build, heavy analyses cached, everything served as JSON to a static page."""
import json
import re
import threading
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..analysis.changes import capture as capture_build, diff as build_diff
from ..analysis.items import breakeven, compare
from ..analysis.skills import build_view as skill_build_view, leveling_view as skill_leveling_view
from ..analysis.uniques import suggest as suggest_uniques
from ..analysis.report import MODES, build_report, defence_weights
from ..analysis.report import score as report_score
from ..analysis.gradients import metric_changes
from ..analysis.tree import analyse as analyse_tree
from ..analysis.tree import ascendancy as tree_ascendancy
from ..analysis.tree import optimize as optimize_tree
from ..analysis.slots import AFFIX_LIMIT, craft_path, plan_all, plan_slot
from ..analysis.sockets import plan_sockets
from ..analysis.threats import MapProfile, survivable_hits
from ..analysis.versus import versus
from ..assistant import (Assistant, LLMConfig, LLMError, Toolbox, build_context, build_glossary, list_models,
                         make_client)
from ..assistant.agent import STYLES
from ..assistant.providers import BY_ID, PROVIDERS, key_hint, load_settings, save_settings
from ..data.moddb import ModDB
from ..economy import trade
from ..economy import ninja
from ..economy.ninja import PriceBook
from ..engine import PobEngine, PobError
from .. import crafting, feedback, gamedata, glossary, icons, itemtext, journal, library, lootfilter, pobapp
from ..i18n import _get as _trade_data
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
                # the league the player chose in the interface; else the build profile's; else poe.ninja's current
                self._prices = PriceBook.load(ninja.chosen_league() or (self.bp.league if self.bp else None))
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


def _english_item(text: str) -> str:
    """PoB reads item text in English only: an item copied from the Russian client is translated first."""
    if not itemtext.is_russian(text):
        return text
    db = session.db()
    if "names" not in _bare:
        _bare["names"] = journal.Names(db)
    uniques = session.cached("unique-catalog", session.engine.unique_catalog)
    try:
        return itemtext.to_english(text, db, _bare["names"], uniques)
    except itemtext.TranslationError as err:
        raise HTTPException(400, f"не смог прочитать предмет: {err}")


@app.post("/api/compare")
def compare_item(req: CompareRequest):
    with session.lock:
        session.require()
        cfg = session.profile.config()
        text = _english_item(req.text)
        result = asdict(_errors(lambda: compare(session.engine, cfg, req.slot, text)))
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
    with session.lock:
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
        build = session.path
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
        if session.path != build:
            raise HTTPException(409, "пока шёл поиск, открыли другой билд")
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
                                          build_context(session.engine, session.bp, glossary, session.profile.config()),
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
