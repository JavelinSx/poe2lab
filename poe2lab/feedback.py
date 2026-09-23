"""Bug reports from the UI: the player's message, screenshots and the build they were looking at, sent to the
project's feedback relay (worker/feedback.js), which mails them to the author.

Nothing secret lives here: the relay holds the mail key, fixes the recipient and rate-limits senders. This side
only checks sizes and types, so the player gets a clear message instead of a refusal from the relay."""
import base64
import binascii
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from .engine.pobcode import encode_pob_code
from .pobfiles import REPO_ROOT

# the deployed worker/ (see worker/README.md); POE2LAB_FEEDBACK_URL overrides it, e.g. for a test relay
RELAY_URL = "https://poe2lab-feedback.poe2lab.workers.dev/feedback"
MAX_MESSAGE = 5000
MAX_CONTACT = 200
MAX_IMAGES = 3
MAX_IMAGE = 3 * 1024 * 1024
COOLDOWN = 30  # seconds between reports from this machine
IMAGE_MAGIC = {"png": b"\x89PNG", "jpg": b"\xff\xd8\xff", "webp": b"RIFF"}
USER_AGENT = "poe2lab/0.1 (feedback)"

_last_sent = 0.0


class FeedbackError(ValueError):
    pass


def relay_url() -> str:
    return os.environ.get("POE2LAB_FEEDBACK_URL") or RELAY_URL


def version() -> str:
    """The commit this copy runs (a ZIP download has no git: then just the package version)."""
    try:
        res = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            return f"0.1.0+{res.stdout.strip()}"
    except (OSError, subprocess.SubprocessError):
        pass
    return "0.1.0"


def build_code(path: Path) -> str:
    """The build file as a PoB code: builds added in poe2lab already are codes, PoB's own saves are XML."""
    text = path.read_text(encoding="utf-8")
    return encode_pob_code(text) if path.suffix.lower() == ".xml" else text.strip()


def image(data_url: str, n: int) -> dict:
    """A pasted or chosen screenshot (a data: URL from the page) checked by its bytes, not by its name."""
    head, _, data = str(data_url).partition(",")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise FeedbackError(f"скрин {n}: не картинка") from None
    kind = next((k for k, magic in IMAGE_MAGIC.items() if raw.startswith(magic)), None)
    if kind is None or not head.startswith("data:image/"):
        raise FeedbackError(f"скрин {n}: нужен PNG, JPG или WebP")
    if len(raw) > MAX_IMAGE:
        raise FeedbackError(f"скрин {n} больше 3 МБ — обрежь его до нужной части экрана")
    return {"type": kind, "data": base64.b64encode(raw).decode("ascii")}


def compose(message: str, contact: str, images: list[str], build: dict, profile: dict | None,
            context: dict) -> dict:
    message = (message or "").strip()
    if len(message) < 5:
        raise FeedbackError("опиши, что не так (хотя бы пару слов)")
    if len(message) > MAX_MESSAGE:
        raise FeedbackError(f"сообщение длиннее {MAX_MESSAGE} символов")
    if len(contact or "") > MAX_CONTACT:
        raise FeedbackError("контакт слишком длинный")
    if len(images) > MAX_IMAGES:
        raise FeedbackError(f"не больше {MAX_IMAGES} скринов")
    return {"message": message, "contact": (contact or "").strip(), "build": build, "profile": profile,
            "context": context | {"version": version()},
            "images": [image(d, i + 1) for i, d in enumerate(images)]}


def send(report: dict):
    """Post the report to the relay; FeedbackError with a message for the player when it does not go through."""
    global _last_sent
    url = relay_url()
    if not url:
        raise FeedbackError("отправка отзывов не настроена в этой копии poe2lab")
    wait = COOLDOWN - (time.monotonic() - _last_sent)
    if _last_sent and wait > 0:
        raise FeedbackError(f"отзыв только что ушёл — следующий можно через {int(wait) + 1} с")
    req = urllib.request.Request(url, data=json.dumps(report).encode("utf-8"), method="POST", headers={
        "Content-Type": "application/json", "X-Poe2lab-Feedback": "1", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            res.read()
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read().decode("utf-8")).get("error", "")
        except (ValueError, OSError):
            detail = ""
        if err.code == 429:
            raise FeedbackError("слишком много отзывов подряд — попробуй через минуту") from None
        raise FeedbackError(f"сервер отзывов ответил {err.code}" + (f": {detail}" if detail else "")) from None
    except OSError as err:
        raise FeedbackError(f"нет связи с сервером отзывов: {err}") from None
    _last_sent = time.monotonic()
