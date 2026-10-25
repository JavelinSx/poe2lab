"""Analysis results kept on disk between runs. A result is found again only by the exact state it was worked out
from - the build as it is in the engine, the files it was read from, the enemy, poe2lab's and PoB's code - so a
restart opens a build that has not changed without counting it all again, and any change counts it anew. Results
that used poe.ninja's prices are kept for PRICED_SECONDS only (the prices move); the folder keeps the newest
MAX_BYTES, the rest goes.

POE2LAB_RESULTS: another folder; empty - nothing is kept (the tests)."""
import functools
import hashlib
import logging
import os
import pickle
import threading
import time
from pathlib import Path

from .pobfiles import REPO_ROOT

log = logging.getLogger(__name__)

PRICED_SECONDS = 12 * 3600
MAX_BYTES = 400 * 2**20
MISS = object()
_written = 0


def root() -> Path | None:
    value = os.environ.get("POE2LAB_RESULTS")
    if value is None:
        return REPO_ROOT / "data" / "cache" / "results"
    return Path(value) if value else None


@functools.lru_cache(maxsize=1)
def code_version() -> str:
    """poe2lab's code and data files and PoB's (pob2/src): their names, sizes and times - an edit or an update of
    either counts every result anew."""
    h = hashlib.sha256()
    pob = REPO_ROOT / "pob2" / "src"
    for top, patterns in ((REPO_ROOT / "poe2lab", ("*",)), (pob, ("*.lua", "*.zst"))):  # not PoB's saved builds
        for path in sorted(p for pattern in patterns for p in top.rglob(pattern)):
            if "__pycache__" in path.parts or (pob / "Builds") in path.parents or not path.is_file():
                continue
            st = path.stat()
            h.update(f"{path.relative_to(REPO_ROOT)}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


def _file(state: str, key) -> Path | None:
    folder = root()
    if folder is None:
        return None
    return folder / f"{hashlib.sha256((state + '|' + repr(key)).encode()).hexdigest()}.pkl"


def get(state: str, key):
    """(the result kept for `key` in this state, whether it used prices), or MISS."""
    path = _file(state, key)
    if path is None or not path.is_file():
        return MISS
    try:
        with path.open("rb") as f:
            entry = pickle.load(f)
        if entry["key"] != repr(key) or (entry["priced"] and time.time() - entry["time"] > PRICED_SECONDS):
            return MISS
        os.utime(path)  # the newest are kept
        return entry["value"], entry["priced"]
    except Exception as err:  # noqa: BLE001 - a broken or outdated file is only a miss
        log.info("result cache: %s unreadable (%s)", path.name, err)
        return MISS


def put(state: str, key, value, priced: bool = False):
    """Keep the result; one that cannot be written (e.g. it holds the engine) is just not kept."""
    global _written
    path = _file(state, key)
    if path is None:
        return
    try:
        data = pickle.dumps({"key": repr(key), "priced": priced, "time": time.time(), "value": value},
                            protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as err:  # noqa: BLE001
        log.info("result cache: %r not kept (%s)", key, err)
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")  # results written side by side
        tmp.write_bytes(data)
        os.replace(tmp, path)
    except OSError as err:
        log.warning("result cache: %s", err)
        return
    _written += len(data)
    if _written > MAX_BYTES // 10:
        _written = 0
        prune()


def prune(limit: int = MAX_BYTES):
    """The newest results up to `limit` bytes stay."""
    folder = root()
    if folder is None or not folder.is_dir():
        return
    files = sorted(((p.stat().st_mtime, p.stat().st_size, p) for p in folder.glob("*.pkl")), reverse=True)
    total = 0
    for _, size, path in files:
        total += size
        if total > limit:
            try:
                path.unlink()
            except OSError:
                pass


def clear():
    folder = root()
    for path in folder.glob("*.pkl") if folder and folder.is_dir() else []:
        try:
            path.unlink()
        except OSError:
            pass
