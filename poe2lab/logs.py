"""poe2lab's own log: what went wrong and when, kept on this computer (next to poe2lab's settings) for the player
to send with a report. Rotated: one file of up to LOG_SIZE and BACKUPS older ones. Nothing secret goes in: keys and
the player's contacts are never logged, and the home folder in paths reads "~" when the log is read to be sent."""
import logging
import logging.handlers
import os
from pathlib import Path

LOG_SIZE = 1024 * 1024
BACKUPS = 2
TAIL = 32 * 1024  # what goes with a report (the relay takes up to 64 KB of context.json, JSON escaping included)

log = logging.getLogger("poe2lab")


def log_dir() -> Path:
    """POE2LAB_LOG_DIR (tests), else poe2lab's settings folder (APPDATA on Windows, ~/.config elsewhere)."""
    if os.environ.get("POE2LAB_LOG_DIR"):
        return Path(os.environ["POE2LAB_LOG_DIR"])
    root = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(root) / "poe2lab" / "logs"


def log_file() -> Path:
    return log_dir() / "poe2lab.log"


def setup() -> logging.Logger:
    """The file handler, once per process; the log keeps working (to the console) when the folder cannot be made."""
    if any(getattr(h, "_poe2lab", False) for h in log.handlers):
        return log
    log.setLevel(logging.INFO)
    try:
        log_dir().mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(log_file(), maxBytes=LOG_SIZE, backupCount=BACKUPS,
                                                       encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler._poe2lab = True
    log.addHandler(handler)
    return log


def tail(limit: int = TAIL) -> str:
    """The end of the log (the previous file's end too when the current one is short), the home folder as "~"."""
    text = ""
    for path in (log_file().with_name(log_file().name + ".1"), log_file()):
        try:
            text += path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    text = text[-limit:]
    if len(text) == limit and "\n" in text:
        text = text[text.index("\n") + 1:]  # from a whole line
    home = str(Path.home())
    return text.replace(home, "~").replace(home.replace("\\", "/"), "~")
