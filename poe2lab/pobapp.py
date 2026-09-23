"""The Path of Building window, for updating a build from the game: find PoB, see whether it already runs, start it
with the build open, or bring it forward.

Two kinds of PoB count. The player's own install (the PoE2 installer puts it in %APPDATA%; its builds live in
Documents\\Path of Building (PoE2)) comes first. Otherwise the copy poe2lab calculates with (pob2/): started from
its folder, PoB runs in its developer mode, keeps settings and builds in pob2/src and saves the open build on exit.
poe2lab lists the builds of both."""
import ctypes
import os
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import psutil

from .pobfiles import REPO_ROOT

BUNDLED_EXE = REPO_ROOT / "pob2" / "runtime" / "Path{space}of{space}Building-PoE2.exe"
EXE_NAMES = {"path of building-poe2.exe", "path{space}of{space}building-poe2.exe"}


@dataclass
class PobApp:
    exe: Path
    user_dir: Path  # Settings.xml and Builds/
    bundled: bool

    @property
    def builds_dir(self) -> Path:
        return self.user_dir / "Builds"


def _documents() -> Path:
    try:
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:  # CSIDL_PERSONAL
            return Path(buf.value)
    except (AttributeError, OSError):
        pass
    return Path.home() / "Documents"


def _installed_dirs() -> list[Path]:
    """Folders of PoB-PoE2 installs: the installer's registry entry and its default place."""
    dirs = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                          (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                          (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")):
            try:
                root = winreg.OpenKey(hive, key)
            except OSError:
                continue
            for i in range(winreg.QueryInfoKey(root)[0]):
                try:
                    sub = winreg.OpenKey(root, winreg.EnumKey(root, i))
                    name = str(winreg.QueryValueEx(sub, "DisplayName")[0])
                    if "Path of Building" in name and "PoE2" in name.replace(" ", ""):
                        dirs.append(Path(str(winreg.QueryValueEx(sub, "InstallLocation")[0]).strip('"')))
                except OSError:
                    continue
    except ImportError:  # not Windows
        pass
    if os.environ.get("APPDATA"):
        dirs.append(Path(os.environ["APPDATA"]) / "Path of Building Community (PoE2)")
    return dirs


def apps() -> list[PobApp]:
    """Every PoB-PoE2 found, the player's own install first."""
    out = []
    for d in _installed_dirs():
        exe = next((p for p in (d / "Path of Building-PoE2.exe",) if p.is_file()), None)
        if exe and all(a.exe != exe for a in out):
            # an installed PoB keeps data in Documents; a portable one (no installed.cfg) next to itself
            user = _documents() / "Path of Building (PoE2)" if (d / "installed.cfg").exists() else d
            out.append(PobApp(exe, user, bundled=False))
    if BUNDLED_EXE.is_file():
        out.append(PobApp(BUNDLED_EXE, REPO_ROOT / "pob2" / "src", bundled=True))
    return out


def app_for(build_file: Path | None) -> PobApp | None:
    """The PoB whose Builds folder holds this build, else the first one found."""
    found = apps()
    if build_file is not None:
        for a in found:
            try:
                build_file.resolve().relative_to(a.builds_dir.resolve())
                return a
            except ValueError:
                continue
    return found[0] if found else None


def running() -> psutil.Process | None:
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() in EXE_NAMES:
            return p
    return None


def _open_on_start(app: PobApp, build_file: Path):
    """PoB reopens the build its Settings.xml names: point it at this one (PoB is not running, so it will not
    overwrite the file before reading it)."""
    settings = app.user_dir / "Settings.xml"
    if not settings.is_file():
        return  # a first start: PoB makes its own settings, and the player picks the build from its list
    tree = ET.parse(settings)
    root = tree.getroot()
    mode = root.find("Mode")
    if mode is None:
        mode = ET.SubElement(root, "Mode")
    for child in list(mode):
        mode.remove(child)
    mode.set("mode", "BUILD")
    ET.SubElement(mode, "Arg", string=str(build_file))
    ET.SubElement(mode, "Arg", string=build_file.stem)
    tree.write(settings, encoding="UTF-8", xml_declaration=True)


def focus(pid: int) -> bool:
    """Bring the process's window forward (Windows may only flash it in the taskbar instead)."""
    try:
        user32 = ctypes.windll.user32
    except AttributeError:
        return False
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def each(hwnd, _):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(each, None)
    if not found:
        return False
    hwnd = ctypes.c_void_p(found[0])
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    return bool(user32.SetForegroundWindow(hwnd))


def open_pob(build_file: Path | None = None) -> dict:
    """Start PoB (with this PoB-saved build open) or bring the running one forward."""
    proc = running()
    if proc is not None:
        focus(proc.pid)
        return {"state": "running"}
    app = app_for(build_file)
    if app is None:
        return {"state": "missing"}
    opened = False
    if build_file is not None and build_file.suffix.lower() == ".xml" and app_for(build_file) == app:
        try:
            build_file.resolve().relative_to(app.builds_dir.resolve())
            _open_on_start(app, build_file.resolve())
            opened = True
        except (ValueError, OSError, ET.ParseError):
            pass
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    # the bundled copy starts from the repository root, as PoB's own docs run it; an install from its folder
    cwd = app.exe.parent.parent if app.bundled else app.exe.parent
    subprocess.Popen([str(app.exe)], cwd=str(cwd), creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"state": "started", "bundled": app.bundled, "openedBuild": opened}
