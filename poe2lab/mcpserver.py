"""poe2lab as an MCP server (Model Context Protocol): the assistant's tools (poe2lab.assistant.tools) for any AI app
on this computer that speaks MCP - Claude Desktop, Claude Code, Cursor, LM Studio... The app starts
`python -m poe2lab mcp` itself and talks to it over stdin/stdout; every number comes from Path of Building here.
It reads builds and never changes them: edits stay the interface's."""
import json
import threading
import urllib.request

from .analysis.threats import MapProfile
from .assistant.agent import build_context, build_glossary
from .assistant.tools import SPECS, Toolbox
from .engine import PobError
from .pobfiles import resolve_build
from .profile import open_build

UI_STATUS = "http://127.0.0.1:8765/api/status"  # the interface's open build, when it runs (start.bat's port)

INSTRUCTIONS = """poe2lab analyses Path of Exile 2 builds with Path of Building's own calculation engine (PoB-PoE2)
running on the player's computer.

Start with open_build: without a name it opens the build open in the poe2lab window, or name one from list_builds.
Its answer is the build's context: skills with the game's descriptions, uniques, what PoB does not model, the
player's confirmed facts, and the official names in the player's language. When a build has the player's own
character in it, the character is what the tools compute and the build is its guide (the target).

Rules:
- Every number (damage, defence, the effect of a mod or an item) comes from these tools; never estimate one. If a
  number cannot be computed, say so and mark any estimate as one.
- Whether a mod exists in PoE2 and where it comes from (affix, rune, unique, passive, ascendancy): find_mod only.
  evaluate_mods only shows that PoB understands a line.
- Mod lines are in PoB's English wording, e.g. "+30% to Chaos Resistance", "20% increased Attack Speed".
- Resistances come from build_report (resistances), not from the hit numbers.
- Corrupted items cannot be changed: for them, only what to look for in a replacement.
- Tell "broken in game" apart from "can be better". Do not advise dropping a mechanic the build is built around
  (crit, charges, rage...) from a snapshot of the character now; compare at the stage the build is going to.
- With a target (a guide): what matters now (evaluate_mods) versus at the end game (evaluate_mods_on_target).
- Answer in the player's language; when it is Russian, pass lang "ru" to open_build and use the official Russian
  names it lists. Only Path of Exile 2."""

# the assistant's tools, less the one that proposes a profile change: the interface confirms those, not this server
TOOL_SPECS = [s["function"] for s in SPECS if s["function"]["name"] != "propose_profile_change"]
OWN_TOOLS = [
    {"name": "list_builds",
     "description": "The builds in the poe2lab library: favourites first, whether the player's own character is in "
                    "the build (hasCharacter) and whether it has a profile of confirmed facts.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "open_build",
     "description": "Open a build for the other tools and get its context (skills, uniques, what PoB does not "
                    "model, the player's facts, official names). Without a name: the build open in the poe2lab "
                    "window. Call it before any other tool, and again to switch builds.",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string", "description": "a name from list_builds"},
         "lang": {"type": "string", "enum": ["ru", "en"], "description": "the player's language (default ru)"}}}},
]


class Workbench:
    """The build the AI app opened, with the assistant's toolbox on it. One build at a time; the PoB engine is
    single-threaded, so every use takes the lock."""

    def __init__(self):
        self.lock = threading.Lock()
        self.name: str | None = None
        self.toolbox: Toolbox | None = None

    def call(self, name: str, args: dict) -> tuple[str, bool]:
        """A tool's answer as text and whether it is an error."""
        try:
            if name == "list_builds":
                return _dump(self._list_builds()), False
            if name == "open_build":
                with self.lock:
                    return self._open_build(**args), False
        except (PobError, FileNotFoundError, ValueError, TypeError, OSError) as err:
            return _dump({"error": str(err)}), True
        if name not in {s["name"] for s in TOOL_SPECS}:
            return _dump({"error": f"unknown tool {name}"}), True
        if self.toolbox is None:
            return _dump({"error": "no build is open: call open_build first (list_builds names them)"}), True
        text = self.toolbox.call(name, args)  # takes the lock itself
        result = json.loads(text)
        return text, isinstance(result, dict) and "error" in result

    def _list_builds(self):
        from . import library
        return [{"name": b["name"], "favorite": b["favorite"], "hasCharacter": b["hasMain"], "hasProfile": b["hasProfile"],
                 "open": b["name"] == self.name} for b in library.entries()]

    def _open_build(self, name: str | None = None, lang: str = "ru") -> str:
        from . import library
        name = name or _ui_build()
        if not name:
            raise ValueError("no build is open in the poe2lab window: name one (list_builds)")
        if name not in {b["name"] for b in library.entries()}:  # the library's builds only, not any file
            raise ValueError(f"no build named {name!r} in poe2lab: see list_builds")
        self.toolbox = self.name = None  # the previous build's engine is freed before the next one loads
        path = resolve_build(name)
        main = library.main_path(path.stem)
        main = main if main.exists() else None
        engine, bp = open_build(main or path, profile_of=path if main else None)
        level = engine.info()["level"]
        profile = MapProfile.for_level(level, rage=bp.rage, mana_sustained=bp.mana_sustained)
        target, target_text, target_names = _target(bp.target, path if main else None, engine, profile, path.stem)
        self.toolbox = Toolbox(engine, profile, None, target, lock=self.lock)
        self.name = path.stem
        glossary = build_glossary(engine, _names(lang), target_names) if lang != "en" else None
        head = (f"Opened: {path.stem}" + (" (the player's character in it; the build is its guide)" if main else "")
                + ". Numbers are PoB's against " + ("map monsters (level 79)" if level >= 65 else
                                                      f"monsters of a level {level} area") + ".")
        return head + "\n\n" + build_context(engine, bp, glossary, profile.config(), target_text)


def _target(named: str | None, guide, engine, profile, own: str):
    """The build the player follows: the one the profile names, else - with the player's character in the build -
    the build itself (the guide). Loaded in its own engine; (None, None, []) without one."""
    if not named and guide is None:
        return None, None, []
    try:
        path = resolve_build(named) if named else guide
        t_engine, t_bp = open_build(path)
    except (PobError, FileNotFoundError, ValueError):
        return None, None, []
    from .analysis.target import context_text, summary
    t_profile = MapProfile.for_level(t_engine.info()["level"], rage=t_bp.rage, mana_sustained=t_bp.mana_sustained)
    t_name = named or f"{own} (гайд)"
    goal = summary(t_engine, t_profile.config(), t_name)
    names = goal["notables"] + goal["ascendancyNotables"] + goal["keystones"] + [s["name"] for s in goal["skills"]]
    return ({"name": t_name, "engine": t_engine, "profile": t_profile},
            context_text(summary(engine, profile.config(), own), goal), names)


def _names(lang: str) -> dict:
    from .gamedata import load_names
    from .i18n import dictionary
    try:
        return dictionary(lang)["names"]
    except (OSError, ValueError):  # no trade data offline: names from the installed game only
        return load_names(lang)


def _ui_build() -> str | None:
    """The build open in the poe2lab window, when it runs."""
    try:
        with urllib.request.urlopen(UI_STATUS, timeout=2) as res:
            return json.load(res).get("build")
    except (OSError, ValueError):
        return None


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def serve():
    """Run over stdin/stdout until the AI app closes the connection."""
    import anyio
    import mcp.types as types
    from mcp.server.lowlevel import Server
    from mcp.server.stdio import stdio_server

    bench = Workbench()
    readonly = types.ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
    tools = [types.Tool(name=s["name"], description=s["description"], input_schema=s["parameters"], annotations=readonly)
             for s in OWN_TOOLS + TOOL_SPECS]

    async def list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    async def call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        text, error = await anyio.to_thread.run_sync(bench.call, params.name, dict(params.arguments or {}))
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=error)

    from importlib.metadata import PackageNotFoundError, version
    try:
        own = version("poe2lab")
    except PackageNotFoundError:  # run from the source folder (PYTHONPATH), not installed
        own = "0"
    server = Server("poe2lab", version=own, instructions=INSTRUCTIONS,
                    website_url="https://github.com/JavelinSx/poe2lab", on_list_tools=list_tools, on_call_tool=call_tool)

    async def run():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(run)
