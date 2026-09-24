"""Craft journal: items copied in game while recording, turned into draws of the hidden mod weights, and the
weights estimated from them.

PoE2 does not ship mod weights (the client's weight columns only say whether a mod can roll), so the only way to
know them is to watch mods roll. The player crafts or loots as usual and presses Ctrl+Alt+C on each item; while
recording, poe2lab reads the clipboard (only texts that are items are kept) and writes the item to a local file.

The advanced copy (Ctrl+Alt+C) names each mod's affix, side and tier: `{ Префикс "Крепкий" (Уровень: 9) }`. The
affix name finds the exact mod in the game's mod table (in either language), so no stat text is translated.

Each record becomes a draw when it can be read as one:
- the first copy of a magic item, or of a rare with up to 4 mods (a drop, an alchemy): all its mods were drawn
  one by one from an empty item, order unknown;
- a copy that is the previous copy of the same item (same base and item level) plus a mod - augmentation, regal,
  exaltation - or with one mod swapped - chaos: the new mod was drawn given the others.
Items with essence, desecrated, fractured or crafted mods, uniques, corrupted and unidentified items are kept in
the journal but not counted: their mods did not roll freely.

A draw picks mod m with chance w(m) / (sum of w over the mods allowed then: a family not yet on the item, a side
with room). The weights are modelled as w(m) = exp(a[family] + b * level / 100): one number per mod family and a
shared fall-off with the tier's level. The prior is the assumption crafting used so far (every family alike, a tier
halving every 25 levels), so with few draws the estimate stays near it and moves as draws come in."""
import ctypes
import ctypes.wintypes
import itertools
import json
import math
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import gamedata
from .crafting import SIDE_LIMIT, TIER_HALF_LEVEL
from .data.moddb import Mod, ModDB


def _user_dir() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(root) / "poe2lab"


def journal_path() -> Path:
    return _user_dir() / "craft_journal.jsonl"


def estimate_path() -> Path:
    return _user_dir() / "craft_estimate.json"


# ---------- the journal file ----------

def entries() -> list[dict]:
    """All records, oldest first: {"id", "t" (unix time), "text", "source": "clipboard" | "manual"}."""
    try:
        lines = journal_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue  # a line cut short by a crash: the rest of the journal still reads
    return out


_write = threading.Lock()


def add(text: str, source: str = "manual") -> dict:
    entry = {"id": f"{time.time_ns():x}", "t": time.time(), "text": text.replace("\r\n", "\n").strip(),
             "source": source}
    with _write:
        journal_path().parent.mkdir(parents=True, exist_ok=True)
        with journal_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def remove(entry_id: str) -> bool:
    with _write:
        all_ = entries()
        kept = [e for e in all_ if e.get("id") != entry_id]
        journal_path().write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in kept), encoding="utf-8")
    return len(kept) < len(all_)


# ---------- recording the clipboard (Windows) ----------

ITEM_START = ("Item Class:", "Класс предмета:")


def is_item_text(text: str | None) -> bool:
    return bool(text) and text.lstrip().startswith(ITEM_START)


def _read_clipboard() -> str | None:
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    for _ in range(5):  # another program may hold the clipboard for a moment
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return None
    try:
        handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


# F2 while recording: one press = one advanced copy (Ctrl+Alt+C) of the item under the cursor, as trade helpers do.
# poe2lab only answers the player's own key press; it never presses anything by itself.
HOTKEY_VK = 0x71  # F2
GAME_TITLES = ("Path of Exile",)
KEY_GAP = 0.025  # seconds between the copy's key events: longer than a frame at 60 fps
_KEYS = [(0x1D, 0), (0x38, 0), (0x2E, 0), (0x2E, 2), (0x38, 2), (0x1D, 2)]  # Ctrl, Alt, C down; then up (scan codes)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUTUNION)]


def copy_inputs() -> list:
    """Ctrl+Alt+C as keyboard input by scan code (games read scan codes)."""
    return [_INPUT(type=1, ki=_KEYBDINPUT(0, scan, 0x8 | up, 0, 0)) for scan, up in _KEYS]  # 0x8: by scan code


def is_game_title(title: str) -> bool:
    return any(t in title for t in GAME_TITLES)


def _foreground_title() -> str:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


class Recorder:
    """While on: watches the clipboard (each new item text goes to the journal) and, with the game in front, turns
    F2 into an advanced copy. Only on Windows."""

    def __init__(self):
        self.on = False
        self.count = 0  # items recorded since it was switched on
        self.hotkey = None  # "F2" when the key is ours, "busy" when another program holds it
        self._stop = threading.Event()
        self._thread = None

    @staticmethod
    def available() -> bool:
        return os.name == "nt"

    def start(self):
        if self.on or not self.available():
            return
        if self._thread and self._thread.is_alive():
            self._thread.join(1)  # the previous run lets F2 go first
        self.on, self.count = True, 0
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="craft-journal")
        self._thread.start()

    def stop(self):
        self.on = False
        self._stop.set()

    def _copy(self):
        if not is_game_title(_foreground_title()):
            return  # F2 outside the game does nothing
        # one key at a time, a few frames apart: the game reads the keyboard once a frame, and a press and release
        # of Alt inside one frame left it seeing Alt held - the advanced tooltip stayed pinned
        for key in copy_inputs():
            ctypes.windll.user32.SendInput(1, ctypes.byref(key), ctypes.sizeof(_INPUT))
            time.sleep(KEY_GAP)

    def _run(self):
        user32 = ctypes.windll.user32
        seq = user32.GetClipboardSequenceNumber
        # the hotkey belongs to the thread that registers it: this loop reads its messages
        self.hotkey = "F2" if user32.RegisterHotKey(None, 1, 0x4000, HOTKEY_VK) else "busy"  # 0x4000: no auto-repeat
        msg = ctypes.wintypes.MSG()
        last = seq()  # what is on the clipboard already is not a new copy
        try:
            while not self._stop.wait(0.03):
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE
                    if msg.message == 0x0312:  # WM_HOTKEY
                        self._copy()
                now = seq()
                if now == last:
                    continue
                last = now
                try:
                    text = _read_clipboard()
                except OSError:
                    continue
                if is_item_text(text):
                    add(text, "clipboard")
                    self.count += 1
        finally:
            if self.hotkey == "F2":
                user32.UnregisterHotKey(None, 1)
            self.hotkey = None


# ---------- reading an item's text ----------

RARITY = {"normal": "normal", "обычный": "normal", "magic": "magic", "волшебный": "magic", "rare": "rare",
          "редкий": "rare", "unique": "unique", "уникальный": "unique"}
HEADER = re.compile(
    r'^\{\s*(?:(?P<kind>Fractured|Desecrated|Crafted|Расколотое|Очернённое|Ремесленное)\s+)?'
    r'(?P<side>Prefix Modifier|Suffix Modifier|Свойство-префикс|Свойство-суффикс|Префикс|Суффикс)\s+'
    r'"(?P<name>[^"]+)"(?:\s*\((?:Tier|Уровень|Ранг|Ур\.)\s*:\s*(?P<tier>\d+)[^)]*\))?')
KIND = {"Fractured": "fractured", "Расколотое": "fractured", "Desecrated": "desecrated", "Очернённое": "desecrated",
        "Crafted": "crafted", "Ремесленное": "crafted"}
UNREVEALED = ("Desecrated Prefix", "Desecrated Suffix", "Очернённый префикс", "Очернённый суффикс")
CORRUPTED = ("Corrupted", "Осквернено")
UNIDENTIFIED = ("Unidentified", "Неопознано")


def _variants(name: str) -> list[str]:
    """Russian affix names carry every grammatical gender: <if:MS>{Крепкий}<elif:FS>{Крепкая}..."""
    found = re.findall(r"\{([^{}]+)\}", name)
    return found or [name]


class Names:
    """Affix names (English and Russian) -> mod ids, and base names (both languages) -> the English base name."""

    def __init__(self, db: ModDB):
        _ensure_tables()
        balance = gamedata.RAW / "data/balance"
        en = list(gamedata.read_table(balance / "mods.datc64", ["Id", "Name"]))
        ru = list(gamedata.read_table(balance / "russian/mods.datc64", ["Name"])) \
            if (balance / "russian/mods.datc64").is_file() else []
        self.affix: dict[str, set[str]] = {}
        for i, row in enumerate(en):
            names = [row["Name"]] + (_variants(ru[i]["Name"]) if i < len(ru) else [])
            for n in names:
                n = n.strip().lower()
                if n:
                    self.affix.setdefault(n, set()).add(row["Id"])
        ru_names = gamedata.load_names("ru")
        self.base = {}
        for en_name in db.bases:
            self.base[en_name.lower()] = en_name
            if ru_names.get(en_name):
                self.base[ru_names[en_name].lower()] = en_name
        self.base_by_length = sorted(self.base, key=len, reverse=True)


def _ensure_tables():
    """The Russian mod table is not in older unpacks: unpack it when the journal first needs it."""
    need = [p for p in ("data/balance/mods.datc64", "data/balance/russian/mods.datc64")
            if not (gamedata.RAW / p).is_file()]
    game = gamedata.game_dir()
    if need and game and gamedata.BUN.is_file():
        subprocess.run([str(gamedata.BUN), "extract-files", "--regex", str(game), str(gamedata.RAW),
                        r"^data/balance/(russian/)?mods\.datc64$"], capture_output=True, text=True)


@dataclass
class ItemMod:
    mod: Mod
    side: str
    tier: int | None
    kind: str  # "" / fractured / desecrated / crafted / essence


@dataclass
class Parsed:
    rarity: str = ""
    base: str = ""  # English base name
    item_level: int = 0
    mods: list[ItemMod] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # why it cannot be read (fully)
    skip: str = ""  # why it is not counted as draws although read
    advanced: bool = False

    @property
    def key(self):
        return self.base, self.item_level


def parse(text: str, db: ModDB, names: Names) -> Parsed:
    p = Parsed()
    lines = [l.strip() for l in text.replace("\r\n", "\n").split("\n")]
    head = []  # the name lines: after the rarity line, up to the first separator
    for i, line in enumerate(lines):
        low = line.lower()
        if ":" in line and low.split(":")[0] in ("rarity", "редкость"):
            p.rarity = RARITY.get(line.split(":", 1)[1].strip().lower(), "")
            for rest in lines[i + 1:]:
                if rest.startswith("--------"):
                    break
                head.append(rest)
        elif ":" in line and low.split(":")[0] in ("item level", "уровень предмета"):
            digits = re.findall(r"\d+", line)
            p.item_level = int(digits[0]) if digits else 0
    if not p.rarity:
        p.problems.append("нет строки редкости — это не текст предмета из игры")
        return p
    for candidate in head[::-1]:  # a rare's base is its own line; a magic item's is inside its name
        low = candidate.lower()
        if low in names.base:
            p.base = names.base[low]
            break
    if not p.base:
        joined = " ".join(head).lower()
        p.base = next((names.base[n] for n in names.base_by_length if n in joined), "")
    if not p.base:
        p.problems.append("не узнал базу: " + " / ".join(head))
    if not p.item_level:
        p.problems.append("нет уровня предмета")
    if any(l in CORRUPTED for l in lines):
        p.skip = "с порчей"
    if any(l in UNIDENTIFIED for l in lines):
        p.skip = "не опознан"
    if any(l.startswith(UNREVEALED) for l in lines):
        p.skip = "есть нераскрытое осквернение"
    if p.rarity == "unique":
        p.skip = "уникальный"
    if p.problems:
        return p
    tags = set(db.bases[p.base]["tags"])
    for line in lines:
        m = HEADER.match(line)
        if not m:
            continue
        p.advanced = True
        side = "Prefix" if m["side"].lower().startswith(("prefix", "префикс", "свойство-префикс")) else "Suffix"
        ids = names.affix.get(m["name"].strip().lower(), set())
        options = [x for x in db.mods if x.id in ids and x.type == side and x.weight_for(tags) > 0]
        if not options:  # an essence's or a desecrated mod: not in the base's normal pool
            options = [x for x in db.mods if x.id in ids and x.type == side]
        tier = int(m["tier"]) if m["tier"] else None
        if tier and len(options) > 1:
            by_tier = [x for x in options if _tier_of(db, x, tags) == tier]
            options = by_tier or options
        if not options:
            p.problems.append(f"не нашёл мод «{m['name']}»")
            continue
        mod = options[0]
        kind = KIND.get(m["kind"] or "", "")
        if not kind and ("Essence" in mod.id or mod.set != "Item"):
            kind = "essence" if "Essence" in mod.id else mod.set.lower()
        p.mods.append(ItemMod(mod, side, tier, kind))
    if not p.advanced and p.rarity in ("magic", "rare"):
        p.problems.append("простое копирование: нажимай Ctrl+Alt+C, чтобы были видны тиры и стороны модов")
    if not p.skip and any(x.kind for x in p.mods):
        p.skip = "есть моды не случайного ролла (" + ", ".join(sorted({x.kind for x in p.mods if x.kind})) + ")"
    return p


def _tier_of(db: ModDB, mod: Mod, tags) -> int:
    tiers = db.tiers_of(mod, tags)
    return next((i + 1 for i, t in enumerate(tiers) if t.id == mod.id), 0)


# ---------- records -> draws ----------

@dataclass
class Sample:
    """Mods drawn onto an item: `added` in unknown order, given `given` already there."""
    tags: tuple
    item_level: int
    rarity: str  # the limits in force while drawing: magic (1 per side) or rare (3)
    given: list[Mod]
    added: list[Mod]
    item_class: str


def interpret(records: list[dict], db: ModDB, names: Names, cache: dict | None = None):
    """Each record with how it counts, and the draws. Records are read in order. Players craft in batches (six
    bases transmuted, then all six augmented...), so every item seen stays open: a copy continues the most recent
    open item of the same base and item level it can come from - one or two mods added (augmentation, regal,
    exalt) or one swapped on a rare (chaos). A copy with exactly the text of an open item is a repeat; two items
    may well roll the same mod, so the same mods alone are not."""
    cache = {} if cache is None else cache
    state: dict[tuple, list[dict]] = {}  # (base, item level) -> open items: {"p": Parsed, "text": str}
    out, samples = [], []
    for r in records:
        if r["id"] not in cache:
            cache[r["id"]] = parse(r["text"], db, names)
        p = cache[r["id"]]
        items = state.setdefault(p.key, [])
        how, drawn, parent = _read(p, r["text"].strip(), items, db)
        if drawn:
            samples.append(drawn)
        if not p.problems and how[0] != "repeat":
            if parent is not None:
                parent["p"], parent["text"] = p, r["text"].strip()
            else:
                items.append({"p": p, "text": r["text"].strip()})
        out.append({"id": r["id"], "t": r["t"], "source": r.get("source", ""), "parsed": p, "how": how[0],
                    "detail": how[1], "draws": len(drawn.added) if drawn else 0})
    return out, samples


STEP = {("magic", "magic"): "augment", ("magic", "rare"): "regal", ("rare", "rare"): "exalt"}


def _read(p: Parsed, text: str, items: list[dict], db: ModDB):
    """How a record counts: (code, detail), its draws and the open item it continues. Codes: unread, skip, white,
    repeat, augment, regal, exalt, chaos, fresh_magic, fresh_rare, rare_unknown, nothing."""
    if p.problems:
        return ("unread", "; ".join(p.problems)), None, None
    if any(it["text"] == text for it in items):
        return ("repeat", ""), None, None
    if p.skip:
        return ("skip", p.skip), None, None
    if p.rarity == "normal":
        return ("white", ""), None, None
    base = db.bases[p.base]
    tags, cls = tuple(base["tags"]), base["type"]
    now = {x.mod.id: x.mod for x in p.mods}
    for it in reversed(items):
        prev = it["p"]
        if prev.skip or prev.rarity not in ("magic", "rare"):
            continue
        before = {x.mod.id for x in prev.mods}
        added = [m for i, m in now.items() if i not in before]
        removed = [i for i in before if i not in now]
        given = [m for i, m in now.items() if i in before]
        if (prev.rarity, p.rarity) in STEP and not removed and 1 <= len(added) <= 2:
            code = STEP[(prev.rarity, p.rarity)]
            return (code, len(added)), Sample(tags, p.item_level, p.rarity, given, added, cls), it
        if (prev.rarity, p.rarity) == ("rare", "rare") and len(removed) == 1 and len(added) == 1:
            return ("chaos", 1), Sample(tags, p.item_level, "rare", given, added, cls), it
    mods = list(now.values())
    if p.rarity == "magic" and 1 <= len(mods) <= 2:
        return ("fresh_magic", len(mods)), Sample(tags, p.item_level, "magic", [], mods, cls), None
    if p.rarity == "rare" and 1 <= len(mods) <= 4:
        return ("fresh_rare", len(mods)), Sample(tags, p.item_level, "rare", [], mods, cls), None
    if p.rarity == "rare":
        return ("rare_unknown", len(mods)), None, None
    return ("nothing", ""), None, None


# ---------- estimating the weights ----------

PRIOR_SLOPE = -math.log(2) * 100 / TIER_HALF_LEVEL  # b in w = exp(a + b * level / 100): halving every 25 levels
PRIOR_SD_FAMILY = 1.5  # a family's weight within ~x4.5 of the average, a priori
PRIOR_SD_SLOPE = 1.5


def family(m: Mod) -> tuple:
    return m.group, m.patterns


class Model:
    def __init__(self, db: ModDB, samples: list[Sample]):
        self.db = db
        self.samples = samples
        self.pools = {}
        self.families = {}
        for s in samples:
            for m in self._pool(s):
                self.families.setdefault(family(m), len(self.families))
        self.a = [0.0] * len(self.families)
        self.b = PRIOR_SLOPE

    def _pool(self, s: Sample) -> list[Mod]:
        key = (s.tags, s.item_level)
        if key not in self.pools:
            self.pools[key] = self.db.rollable(s.tags, s.item_level)
        return self.pools[key]

    def _draw(self, pool, have: list[Mod], rarity: str, pick: Mod):
        """log p(pick) and its gradient pieces: the allowed mods' probabilities."""
        limit = SIDE_LIMIT[rarity]
        fams = {family(m) for m in have}
        room = {k for k in ("Prefix", "Suffix") if sum(m.type == k for m in have) < limit}
        allowed = [m for m in pool if m.type in room and family(m) not in fams]
        ws = [math.exp(self.a[self.families[family(m)]] + self.b * m.level / 100) for m in allowed]
        total = sum(ws)
        if pick not in allowed or total <= 0:
            return None
        w = math.exp(self.a[self.families[family(pick)]] + self.b * pick.level / 100)
        return math.log(w / total), allowed, [x / total for x in ws]

    def _sample(self, s: Sample):
        """log-likelihood of one sample (summed over the orders its mods may have come in) and, per order, the
        draws with their weight in that sum - for the gradient."""
        pool = self._pool(s)
        orders = []
        for order in itertools.permutations(s.added):
            have, logp, draws = list(s.given), 0.0, []
            for pick in order:
                d = self._draw(pool, have, s.rarity, pick)
                if d is None:
                    logp = None
                    break
                logp += d[0]
                draws.append((pick, d[1], d[2]))
                have.append(pick)
            if logp is not None:
                orders.append((logp, draws))
        if not orders:
            return None, []
        top = max(lp for lp, _ in orders)
        z = sum(math.exp(lp - top) for lp, _ in orders)
        return top + math.log(z), [(math.exp(lp - top) / z, draws) for lp, draws in orders]

    def fit(self, iterations: int = 40):
        """Maximum a posteriori by diagonal Newton steps; returns the per-family standard deviations."""
        n = len(self.families)
        sd = [PRIOR_SD_FAMILY] * n
        for _ in range(iterations):
            ga, ha = [0.0] * n, [0.0] * n
            gb, hb = 0.0, 0.0
            for s in self.samples:
                _, orders = self._sample(s)
                for weight, draws in orders:
                    for pick, allowed, probs in draws:
                        i = self.families[family(pick)]
                        ga[i] += weight
                        gb += weight * pick.level / 100
                        mean_level = sum(p * m.level / 100 for m, p in zip(allowed, probs))
                        share = {}
                        for m, p in zip(allowed, probs):
                            j = self.families[family(m)]
                            share[j] = share.get(j, 0.0) + p
                        for j, q in share.items():
                            ga[j] -= weight * q
                            ha[j] += weight * q * (1 - q)
                        gb -= weight * mean_level
                        hb += weight * sum(p * (m.level / 100 - mean_level) ** 2 for m, p in zip(allowed, probs))
            step = 0.0
            for j in range(n):
                g = ga[j] - self.a[j] / PRIOR_SD_FAMILY ** 2
                h = ha[j] + 1 / PRIOR_SD_FAMILY ** 2
                d = max(-1.0, min(1.0, g / h))
                self.a[j] += d
                step = max(step, abs(d))
                sd[j] = 1 / math.sqrt(h)
            g = gb - (self.b - PRIOR_SLOPE) / PRIOR_SD_SLOPE ** 2
            h = hb + 1 / PRIOR_SD_SLOPE ** 2
            self.b += max(-1.0, min(1.0, g / h))
            if step < 1e-3:
                break
        return sd

    def weight(self, m: Mod) -> float:
        i = self.families.get(family(m))
        return math.exp((self.a[i] if i is not None else 0.0) + self.b * m.level / 100)


def estimate(db: ModDB, samples: list[Sample]) -> dict:
    """The fitted weights and, per item class, how each family's chance moved from the assumption."""
    model = Model(db, samples)
    sd = model.fit()
    drawn = {}
    for s in samples:
        for m in s.added:
            drawn[family(m)] = drawn.get(family(m), 0) + 1
    families = []
    names = {}
    for m in db.mods:
        names.setdefault(family(m), " / ".join(m.lines))
    for f, i in model.families.items():
        families.append({"family": names.get(f, f[0]), "group": f[0], "factor": math.exp(model.a[i]),
                         "spread": math.exp(sd[i]) - 1, "seen": drawn.get(f, 0)})
    families.sort(key=lambda x: (-x["seen"], x["family"]))
    classes = {}
    for s in samples:
        c = classes.setdefault(s.item_class, {"records": 0, "draws": 0})
        c["records"] += 1
        c["draws"] += len(s.added)
    weights = {m.id: model.weight(m) for m in db.mods if m.set == "Item"}
    return {"time": time.time(), "draws": sum(len(s.added) for s in samples), "samples": len(samples),
            "halfLevel": -math.log(2) * 100 / model.b if model.b < 0 else None,
            "families": families, "classes": classes, "weights": weights}


def save_estimate(result: dict):
    estimate_path().parent.mkdir(parents=True, exist_ok=True)
    estimate_path().write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


def load_estimate() -> dict | None:
    try:
        return json.loads(estimate_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
