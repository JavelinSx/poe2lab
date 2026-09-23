"""Skill, passive and item pictures from the installed game, as small PNG files the UI can show next to names.

Skill and passive icons are 64x64 DDS textures, BC1-compressed (DXGI 71/72); item art (uniques and the bases of
gear) is uncompressed RGBA (DXGI 28/29), shrunk here to thumbnails. Both are simple enough to decode without an
image library, and PNG is written with zlib. Other formats are skipped (the name just has no picture)."""
import json
import re
import struct
import subprocess
import zlib
from pathlib import Path

from .gamedata import BUN, GAME_CACHE, RAW, GameDataError, game_dir, read_table

ICONS = GAME_CACHE / "icons"
INDEX = ICONS / "index.json"
# table -> (name column, icon column): names are the English display names PoB uses
SOURCES = {"activeskills": ("DisplayName", "Icon"), "passiveskills": ("Name", "Icon")}
BC1_FORMATS = {71, 72}  # BC1_UNORM, BC1_UNORM_SRGB
RGBA_FORMATS = {28: False, 29: False, 87: True, 91: True}  # R8G8B8A8 (UNORM/SRGB); B8G8R8A8: channels swapped
ITEM_SIDE = 96  # item thumbnails: the longer side at most this many pixels
# item art of gear worth a picture (not currencies, maps, quest items)
ITEM_ART = re.compile(r"^art/2ditems/(armours|weapons|rings|amulets|belts|offhand|quivers|jewels|flasks|charms)/|"
                      r"^art/2ditems/gems/.*support")  # support gems: skills already have icons of their own


def _rgb565(c: int) -> tuple[int, int, int]:
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def decode_bc1(data: bytes, width: int, height: int) -> bytearray:
    """BC1 blocks (8 bytes per 4x4 pixels) -> RGBA bytes, row by row."""
    out = bytearray(width * height * 4)
    bw, bh = max(1, (width + 3) // 4), max(1, (height + 3) // 4)
    for by in range(bh):
        for bx in range(bw):
            off = (by * bw + bx) * 8
            c0, c1, bits = struct.unpack_from("<HHI", data, off)
            p0, p1 = _rgb565(c0), _rgb565(c1)
            if c0 > c1:
                palette = [p0 + (255,), p1 + (255,),
                           tuple((2 * a + b) // 3 for a, b in zip(p0, p1)) + (255,),
                           tuple((a + 2 * b) // 3 for a, b in zip(p0, p1)) + (255,)]
            else:
                palette = [p0 + (255,), p1 + (255,), tuple((a + b) // 2 for a, b in zip(p0, p1)) + (255,), (0, 0, 0, 0)]
            for py in range(4):
                y = by * 4 + py
                if y >= height:
                    break
                for px in range(4):
                    x = bx * 4 + px
                    if x >= width:
                        continue
                    idx = (bits >> (2 * (py * 4 + px))) & 3
                    o = (y * width + x) * 4
                    out[o:o + 4] = bytes(palette[idx])
    return out


def png(rgba: bytes, width: int, height: int) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    rows = b"".join(b"\x00" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def dds_to_png(raw: bytes) -> bytes | None:
    """The top mip of a BC1 DDS texture as PNG; None for other formats."""
    if raw[:4] != b"DDS ":
        return None
    height, width = struct.unpack_from("<II", raw, 12)
    fourcc = raw[84:88]
    if fourcc == b"DX10":
        if struct.unpack_from("<I", raw, 128)[0] not in BC1_FORMATS:
            return None
        start = 148
    elif fourcc == b"DXT1":
        start = 128
    else:
        return None
    return png(decode_bc1(raw[start:], width, height), width, height)


def _shrink(rgba: bytes, width: int, height: int) -> tuple[bytes, int, int]:
    """Box-average down by a whole factor so the longer side fits ITEM_SIDE."""
    k = max(1, -(-max(width, height) // ITEM_SIDE))
    if k == 1:
        return rgba, width, height
    w, h = width // k, height // k
    out = bytearray(w * h * 4)
    n = k * k
    for y in range(h):
        rows = [rgba[((y * k + dy) * width) * 4:((y * k + dy) * width + w * k) * 4] for dy in range(k)]
        for x in range(w):
            acc = [0, 0, 0, 0]
            for row in rows:
                block = row[x * k * 4:(x * k + k) * 4]
                for c in range(4):
                    acc[c] += sum(block[c::4])
            o = (y * w + x) * 4
            out[o:o + 4] = bytes(v // n for v in acc)
    return bytes(out), w, h


def item_png(raw: bytes) -> bytes | None:
    """Item art (an uncompressed RGBA DDS) as a thumbnail PNG; None for other formats."""
    if raw[:4] != b"DDS " or raw[84:88] != b"DX10":
        return None
    fmt = struct.unpack_from("<I", raw, 128)[0]
    if fmt not in RGBA_FORMATS:
        return dds_to_png(raw)
    height, width = struct.unpack_from("<II", raw, 12)
    rgba = raw[148:148 + width * height * 4]
    if len(rgba) < width * height * 4:
        return None
    if RGBA_FORMATS[fmt]:  # BGRA -> RGBA
        swapped = bytearray(rgba)
        swapped[0::4], swapped[2::4] = rgba[2::4], rgba[0::4]
        rgba = bytes(swapped)
    return png(*_shrink(rgba, width, height))


def item_art() -> dict[str, str]:
    """English name -> texture path for uniques (their own art) and gear bases, from the unpacked tables."""
    balance = RAW / "data/balance"
    vis = [r["DDSFile"] for r in read_table(balance / "itemvisualidentity.datc64", ["DDSFile"])]
    words = [r["Text"] for r in read_table(balance / "words.datc64", ["Text"])]
    art = {}
    for r in read_table(balance / "uniquestashlayout.datc64", ["WordsKey", "ItemVisualIdentity"]):
        w, v = r["WordsKey"], r["ItemVisualIdentity"]
        if w is not None and v is not None and w < len(words) and v < len(vis) and words[w].strip():
            art.setdefault(words[w].strip(), vis[v])
    for r in read_table(balance / "baseitemtypes.datc64", ["Name", "ItemVisualIdentityKey"]):
        v = r["ItemVisualIdentityKey"]
        if v is not None and v < len(vis) and r["Name"].strip() and ITEM_ART.match(vis[v].lower()):
            art.setdefault(r["Name"].strip(), vis[v])
    return {name: path for name, path in art.items() if path.lower().endswith(".dds")}


def _file_name(icon_path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", icon_path.lower().removesuffix(".dds")).strip("_") + ".png"


def build(game: Path | None = None) -> dict:
    """Unpack the icons the skill and passive tables point at and convert them; writes the name -> file index."""
    game = game or game_dir()
    if game is None or not BUN.is_file():
        raise GameDataError("нужны установленная игра и tools/ooz/bun_extract_file.exe")
    wanted: dict[str, str] = {}  # English name -> icon path in the game
    for table, (name_col, icon_col) in SOURCES.items():
        for row in read_table(RAW / "data/balance" / f"{table}.datc64", [name_col, icon_col]):
            name, icon = row[name_col].strip(), row[icon_col].strip()
            if name and icon.lower().endswith(".dds"):
                wanted.setdefault(name, icon)
    items = item_art() if (RAW / "data/balance/uniquestashlayout.datc64").is_file() else {}
    for name, path in items.items():
        wanted.setdefault(name, path)
    item_paths = {p.lower() for p in items.values()}
    paths = sorted({p.lower() for p in wanted.values()})
    # thousands of paths do not fit a Windows command line: the extractor reads them from stdin instead
    res = subprocess.run([str(BUN), "extract-files", str(game), str(RAW)], input="\n".join(paths) + "\n",
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise GameDataError(f"bun_extract_file: {res.stderr.strip() or res.stdout.strip()}")
    ICONS.mkdir(parents=True, exist_ok=True)
    converted: dict[str, str] = {}
    index, skipped = {}, 0
    for name, icon in wanted.items():
        key = icon.lower()
        if key not in converted:
            src = RAW / key
            convert = item_png if key in item_paths else dds_to_png
            data = convert(src.read_bytes()) if src.is_file() else None
            converted[key] = ""
            if data:
                converted[key] = _file_name(key)
                (ICONS / converted[key]).write_bytes(data)
            else:
                skipped += 1
        if converted[key]:
            index[name] = converted[key]
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    if items:
        (ICONS / "items.ok").write_text(str(len(items)), encoding="utf-8")  # see gamedata.stale
    return {"icons": len(set(index.values())), "names": len(index), "items": len(items), "skipped": skipped}


def load_index() -> dict[str, str]:
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
