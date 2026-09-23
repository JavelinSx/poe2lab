"""Game icons: BC1 decoding and PNG output without an image library."""
import struct
import zlib

import pytest

from poe2lab import icons


def test_bc1_block_decodes_to_its_colours():
    red, blue = 0xF800, 0x001F  # RGB565
    block = struct.pack("<HHI", red, blue, 0b01 << 2)  # pixel 0 -> colour 0 (red), pixel 1 -> colour 1 (blue)
    rgba = icons.decode_bc1(block, 4, 4)
    assert tuple(rgba[0:4]) == (255, 0, 0, 255) and tuple(rgba[4:8]) == (0, 0, 255, 255)
    transparent = struct.pack("<HHI", blue, red, 0b11)  # c0 <= c1: index 3 is transparent
    assert tuple(icons.decode_bc1(transparent, 4, 4)[0:4]) == (0, 0, 0, 0)


def test_png_is_valid():
    data = icons.png(bytes([10, 20, 30, 255]) * 4, 2, 2)
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    length = struct.unpack(">I", data[8:12])[0]
    assert data[12:16] == b"IHDR" and struct.unpack(">II", data[16:24]) == (2, 2)
    assert struct.unpack(">I", data[16 + length:20 + length])[0] == zlib.crc32(data[12:16 + length]) & 0xFFFFFFFF


@pytest.mark.skipif(not icons.INDEX.is_file(), reason="icons not unpacked on this machine")
def test_unpacked_icons_cover_skills_and_passives():
    index = icons.load_index()
    for name in ("Walking Calamity", "Furious Slam", "Nimble Strength"):
        assert (icons.ICONS / index[name]).is_file()


def test_item_art_thumbnails():
    """Item art is uncompressed RGBA (DXGI 28): read as is and shrunk by a whole factor to fit the thumbnail."""
    import struct
    import zlib
    from poe2lab import icons as ic
    w, h = 200, 100
    header = bytearray(148)
    header[:4] = b"DDS "
    struct.pack_into("<II", header, 12, h, w)
    header[84:88] = b"DX10"
    struct.pack_into("<I", header, 128, 28)
    pixels = bytes([255, 0, 0, 255]) * (w * h)
    data = ic.item_png(bytes(header) + pixels)
    assert data.startswith(b"\x89PNG")
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (w // 3, h // 3) and max(width, height) <= ic.ITEM_SIDE
    first = lambda png: zlib.decompress(png[png.index(b"IDAT") + 4:-16])[1:5]  # first pixel after the filter byte
    assert first(data) == bytes([255, 0, 0, 255])  # the colour survives averaging
    header[128] = 87  # BGRA: channels swapped back
    assert first(ic.item_png(bytes(header) + pixels)) == bytes([0, 0, 255, 255])
