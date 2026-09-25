"""Runs Lua inside PoB's bundled LuaJIT (runtime/lua51.dll).

PoB ships a patched LuaJIT that understands its `??` operator, so stock LuaJIT cannot parse PoB's sources.
Loading PoB's own lua51.dll through ctypes keeps the engine inside the Python process.
"""
import ctypes
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POB_ROOT = REPO_ROOT / "pob2"
# The PoB-PoE2 commit poe2lab is tested with (the pob2 submodule). Without git it is downloaded as an archive of this
# exact commit; tests check that it matches the submodule.
POB_REPO = "PathOfBuildingCommunity/PathOfBuilding-PoE2"
POB_COMMIT = "ce566eac45ea8a86477f513c7ee65a1ebe60014e"


class LuaError(RuntimeError):
    pass


def ensure_pob(pob_root: Path) -> None:
    """Fetch Path of Building if it is missing: the git submodule when the project is a git clone, otherwise (a
    downloaded ZIP of the project, no git) an archive of the pinned commit from GitHub."""
    if (pob_root / "src" / "HeadlessWrapper.lua").exists():
        return
    if pob_root.resolve() != DEFAULT_POB_ROOT.resolve():
        raise FileNotFoundError(f"Path of Building not found in {pob_root}")
    print("Path of Building (pob2) is missing - fetching it, this happens once...")
    err = ""
    if (REPO_ROOT / ".git").exists():
        try:
            result = subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=REPO_ROOT,
                                    capture_output=True, text=True)
            err = result.stderr.strip()
        except OSError as e:  # no git on this machine
            err = str(e)
    if not (pob_root / "src" / "HeadlessWrapper.lua").exists():
        _download_pob(pob_root)
    if not (pob_root / "src" / "HeadlessWrapper.lua").exists():
        raise RuntimeError(f"could not fetch Path of Building into {pob_root}\n{err}")


# PoB's longest file path below its folder (src/Data/StatDescriptions/Specific_Skill_Stat_Descriptions/...): with
# Windows' 260-character path limit the project folder itself has to stay shorter than this leaves room for.
POB_LONGEST_PATH = 110
WINDOWS_MAX_PATH = 259


def _download_pob(pob_root: Path) -> None:
    import io
    import shutil
    import tempfile
    import urllib.request
    import zipfile

    if os.name == "nt" and len(str(pob_root)) + 1 + POB_LONGEST_PATH > WINDOWS_MAX_PATH:
        raise RuntimeError(f"путь к папке проекта слишком длинный ({len(str(REPO_ROOT))} символов) для файлов Path of "
                           f"Building: переместите папку poe2lab ближе к корню диска, например в C:\\poe2lab")
    url = f"https://codeload.github.com/{POB_REPO}/zip/{POB_COMMIT}"
    print(f"downloading {url} (~200 MB)...")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "poe2lab"}), timeout=600) as res:
        data = res.read()
    # unpack where paths are short, then move the one top folder (PathOfBuilding-PoE2-<commit>) into place
    with tempfile.TemporaryDirectory(prefix="pob") as tmp:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(tmp)
        inner = next(Path(tmp).iterdir())
        if pob_root.exists():
            shutil.rmtree(pob_root)  # the empty submodule folder of a ZIP of the project
        shutil.move(str(inner), str(pob_root))


class LuaHost:
    def __init__(self, pob_root: Path = DEFAULT_POB_ROOT):
        pob_root = Path(pob_root).resolve()
        ensure_pob(pob_root)
        runtime = pob_root / "runtime"
        os.add_dll_directory(str(runtime))
        lua = ctypes.CDLL(str(runtime / "lua51.dll"))
        lua.luaL_newstate.restype = ctypes.c_void_p
        lua.luaL_openlibs.argtypes = [ctypes.c_void_p]
        lua.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lua.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
        lua.lua_tolstring.restype = ctypes.c_void_p
        lua.lua_settop.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lua.lua_gettop.argtypes = [ctypes.c_void_p]
        lua.lua_close.argtypes = [ctypes.c_void_p]
        self._lua = lua
        self._L = lua.luaL_newstate()
        lua.luaL_openlibs(self._L)

        # PoB resolves its data files relative to src/, so the process must run from there.
        os.chdir(pob_root / "src")
        rt = runtime.as_posix()
        self.run(
            f'package.path = "{rt}/lua/?.lua;{rt}/lua/?/init.lua;" .. package.path\n'
            f'package.cpath = "{rt}/?.dll;" .. package.cpath\n'
            "arg = {}\n"
            "_POE2LAB_LOG = {}\n"
            "print = function(...)\n"
            "  local parts = {}\n"
            "  for i = 1, select('#', ...) do parts[i] = tostring((select(i, ...))) end\n"
            "  _POE2LAB_LOG[#_POE2LAB_LOG + 1] = table.concat(parts, '\\t')\n"
            "end\n"
            "io.read = function() return nil end"
        )

    def _top_string(self):
        size = ctypes.c_size_t()
        ptr = self._lua.lua_tolstring(self._L, -1, ctypes.byref(size))
        return None if not ptr else ctypes.string_at(ptr, size.value).decode("utf-8", "replace")

    def close(self):
        """Free the Lua state and everything PoB holds in it (a loaded PoB is hundreds of MB)."""
        if self._L:
            self._lua.lua_close(self._L)
            self._L = None

    def __del__(self):
        # the last reference is gone (a build replaced by another one): give the memory back
        try:
            self.close()
        except Exception:
            pass

    def run(self, code: str):
        """Execute a chunk and return its first result passed through tostring (None if nil)."""
        if not self._L:
            raise LuaError("the Lua state is closed")
        base = self._lua.lua_gettop(self._L)
        wrapped = f"return (function(...)\n{code}\nend)()"
        rc = self._lua.luaL_loadstring(self._L, wrapped.encode("utf-8"))
        if rc == 0:
            rc = self._lua.lua_pcall(self._L, 0, 1, 0)
        result = self._top_string()
        self._lua.lua_settop(self._L, base)
        if rc != 0:
            raise LuaError(result)
        return result


def lua_string(text: str) -> str:
    """Quote arbitrary text as a Lua long-bracket literal."""
    level = 0
    while f"]{'=' * level}]" in text:
        level += 1
    eq = "=" * level
    return f"[{eq}[{text}]{eq}]"
