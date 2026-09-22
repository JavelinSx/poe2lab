"""Local web interface: one loaded build, heavy analyses cached, everything served as JSON to a static page."""
import json
import threading
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..analysis.items import breakeven, compare
from ..analysis.report import build_report, defence_weights
from ..analysis.slots import craft_path, plan_all
from ..analysis.sockets import plan_sockets
from ..analysis.sources import describe as describe_sources
from ..analysis.threats import MapProfile, survivable_hits
from ..assistant import Assistant, LLMConfig, LLMError, Toolbox, build_context, list_models, make_client
from ..assistant.providers import BY_ID, PROVIDERS, key_hint, load_settings, save_settings
from ..data.moddb import ModDB
from ..economy.ninja import PriceBook
from ..engine import PobError
from ..knowledge import collect as collect_mechanics
from ..pobfiles import PROJECT_BUILDS, list_pob_builds, resolve_build
from ..profile import BuildProfile, describe as describe_profile, open_build

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

    def require(self):
        if self.engine is None:
            raise HTTPException(409, "сначала откройте билд")

    @property
    def profile(self) -> MapProfile:
        return MapProfile(rage=self.bp.rage, mana_sustained=self.bp.mana_sustained)

    def load(self, name: str, group: int | None = None, skill: int | None = None):
        self.path = resolve_build(name)
        self.engine, self.bp = open_build(self.path, group, skill)
        self.cache.clear()
        self.assistant = self.toolbox = None

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


@app.get("/api/status")
def status():
    cfg = LLMConfig.current()
    return {"loaded": session.engine is not None, "build": session.path.stem if session.path else None,
            "llm": {"configured": cfg is not None, "model": cfg.model if cfg else None,
                    "provider": cfg.provider if cfg else None}}


class LLMSettings(BaseModel):
    provider: str
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # None/"" keeps the stored key
    clear_key: bool = False


def _llm_view() -> dict:
    s = load_settings()
    keys = s.get("keys") or {}
    return {
        "provider": s.get("provider"), "model": s.get("model"), "baseUrl": s.get("base_url"),
        "providers": [{"id": p.id, "name": p.name, "baseUrl": p.base_url, "defaultModel": p.default_model,
                       "needsKey": p.needs_key, "note": p.note, "keyHint": key_hint(keys.get(p.id))}
                      for p in PROVIDERS],
        "active": status()["llm"],
    }


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
    out = [{"name": p.stem, "kind": "pob", "file": str(p)} for p in list_pob_builds()]
    out += [{"name": p.stem, "kind": "code", "file": str(p)} for p in sorted(PROJECT_BUILDS.glob("*.txt"))]
    for b in out:
        b["hasProfile"] = (PROJECT_BUILDS / f"{b['name']}.profile.json").exists()
    return out


def _summary():
    e = session.engine
    return {"name": session.path.stem, "info": e.info(), "mainSkill": e.main_skill(), "groups": e.socket_groups(),
            "profile": describe_profile(session.bp), "profileRaw": _profile_raw(),
            "items": e.equipped_item_details()}


@app.post("/api/load")
def load(req: LoadRequest):
    with session.lock:
        _errors(lambda: session.load(req.name, req.group, req.skill))
        return _json(_summary())


@app.get("/api/build")
def build():
    with session.lock:
        session.require()
        return _json(_summary())


@app.get("/api/report")
def report(mode: str = "balanced"):
    with session.lock:
        session.require()
        return _json(session.cached(("report", mode), lambda: build_report(session.engine, session.profile, mode=mode)))


@app.get("/api/gear")
def gear(mode: str = "balanced"):
    with session.lock:
        session.require()

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
def mechanics():
    with session.lock:
        session.require()
        m = session.cached("mechanics", lambda: collect_mechanics(session.engine))
        return _json({"gaps": m.gaps, "skills": m.skills, "uniques": m.uniques})


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
    return {"main_skill": {}, "rage": None, "mana_sustained": False, "league": None, "corrections": [], "notes": []}


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
            session.assistant = Assistant(make_client(cfg), session.toolbox, build_context(session.engine, session.bp))
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


@app.get("/")
def index():
    # version static URLs by modification time so browsers never run a stale script
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for name in ("app.js", "i18n.js", "app.css"):
        html = html.replace(f"/static/{name}", f"/static/{name}?v={int((STATIC / name).stat().st_mtime)}")
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})
