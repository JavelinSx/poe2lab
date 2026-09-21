import os
import time
from concurrent.futures import ProcessPoolExecutor

import psutil

from .luahost import DEFAULT_POB_ROOT
from .pob import PobEngine

WORKER_RAM_BYTES = 400 * 2**20

_engine: PobEngine | None = None


def _init_worker(pob_root, build_code, main_skill):
    global _engine
    _engine = PobEngine(pob_root)
    _engine.load_code(build_code)
    if main_skill:
        _engine.set_main_skill(*main_skill)


def _call(method, args, kwargs):
    return getattr(_engine, method)(*args, **kwargs)


def _ping():
    time.sleep(0.05)
    return os.getpid()


def default_worker_count() -> int:
    by_cpu = max(1, (os.cpu_count() or 2) - 1)
    by_ram = max(1, int(psutil.virtual_memory().available * 0.7) // WORKER_RAM_BYTES)
    return min(by_cpu, by_ram)


class EnginePool:
    """Worker processes, each holding a warm PoB with the same build loaded."""

    def __init__(self, build_code: str, workers: int | None = None, main_skill: tuple[int, int] | None = None,
                 pob_root=DEFAULT_POB_ROOT):
        """main_skill: (socket_group_index, active_skill_index), as in PobEngine.set_main_skill."""
        self.workers = workers or default_worker_count()
        self._executor = ProcessPoolExecutor(
            self.workers, initializer=_init_worker, initargs=(str(pob_root), build_code, main_skill)
        )
        self._warm_up()

    def _warm_up(self):
        # Workers spawn lazily; keep pinging until every one has started and loaded the build.
        seen = set()
        while len(seen) < self.workers:
            seen.update(f.result() for f in [self._executor.submit(_ping) for _ in range(self.workers)])

    def map(self, method: str, calls: list[dict]) -> list:
        """Run engine.<method>(**kwargs) for every kwargs dict in `calls`, preserving order."""
        chunk = max(1, len(calls) // (self.workers * 4))
        return list(self._executor.map(_call, [method] * len(calls), [()] * len(calls), calls, chunksize=chunk))

    def close(self):
        self._executor.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
