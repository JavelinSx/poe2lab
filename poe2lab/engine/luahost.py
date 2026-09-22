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


class LuaError(RuntimeError):
    pass


def ensure_pob(pob_root: Path) -> None:
    """Fetch the PoB submodule if the repo was cloned without --recurse-submodules."""
    if (pob_root / "src" / "HeadlessWrapper.lua").exists():
        return
    if pob_root.resolve() != DEFAULT_POB_ROOT.resolve():
        raise FileNotFoundError(f"Path of Building not found in {pob_root}")
    print("Path of Building (pob2) is missing - fetching the git submodule, this happens once...")
    result = subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=REPO_ROOT,
                            capture_output=True, text=True)
    if result.returncode != 0 or not (pob_root / "src" / "HeadlessWrapper.lua").exists():
        raise RuntimeError("could not fetch the pob2 submodule; run `git submodule update --init` in "
                           f"{REPO_ROOT}\n{result.stderr.strip()}")


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

    def run(self, code: str):
        """Execute a chunk and return its first result passed through tostring (None if nil)."""
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
