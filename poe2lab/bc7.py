"""BC7 (DXGI 98/99) block decoding for the game's UI art (the atlas masters' portraits and tab icons), without an
image library. Follows the D3D11 BC7 format: 8 modes, 1-3 subsets, partition and anchor tables as published there."""

# 2 subsets: bit i of the mask = subset of pixel i (pixels row by row)
P2 = [0xCCCC, 0x8888, 0xEEEE, 0xECC8, 0xC880, 0xFEEC, 0xFEC8, 0xEC80, 0xC800, 0xFFEC, 0xFE80, 0xE800, 0xFFE8, 0xFF00,
      0xFFF0, 0xF000, 0xF710, 0x008E, 0x7100, 0x08CE, 0x008C, 0x7310, 0x3100, 0x8CCE, 0x088C, 0x3110, 0x6666, 0x366C,
      0x17E8, 0x0FF0, 0x718E, 0x399C, 0xAAAA, 0xF0F0, 0x5A5A, 0x33CC, 0x3C3C, 0x55AA, 0x9696, 0xA55A, 0x73CE, 0x13C8,
      0x324C, 0x3BDC, 0x6996, 0xC33C, 0x9966, 0x0660, 0x0272, 0x04E4, 0x4E40, 0x2720, 0xC936, 0x936C, 0x39C6, 0x639C,
      0x9336, 0x9CC6, 0x817E, 0xE718, 0xCCF0, 0x0FCC, 0x7744, 0xEE22]
P3 = [[int(c) for c in s.strip()] for s in """0011001102212222,0001001122112221,0000200122112211,0222002200110111,0000000011221122,
0011001100220022,0022002211111111,0011001122112211,0000000011112222,0000111111112222,0000111122222222,0012001200120012,
0112011201120112,0122012201220122,0011011211221222,0011200122002220,0001001101121122,0111001120012200,0000112211221122,
0022002200221111,0111011102220222,0001000122212221,0000001101220122,0000110022102210,0122012200110000,0012001211222222,
0110122112210110,0000011012211221,0022110211020022,0110011020022222,0011012201220011,0000200022112221,0000000211221222,
0222002200120011,0011001200220222,0120012001200120,0000111122220000,0120120120120120,0120201212010120,0011220011220011,
0011112222000011,0101010122222222,0000000021212121,0022112200221122,0022001100220011,0220122102201221,0101222222220101,
0000212121212121,0101010101012222,0222011102220111,0002111200021112,0000211221122112,0222011101110222,0002111211120002,
0110011001102222,0000000021122112,0110011022222222,0022001100110022,0022112211220022,0000000000002112,0002000100020001,
0222122202221222,0101222222222222,0111201122012220""".replace("\n", "").split(",")]
A2 = [15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 8, 2, 2, 8, 8, 15, 2, 8, 2, 2, 8, 8, 2, 2,
      15, 15, 6, 8, 2, 8, 15, 15, 2, 8, 2, 2, 2, 15, 15, 6, 6, 2, 6, 8, 15, 15, 2, 2, 15, 15, 15, 15, 15, 2, 2, 15]
A3a = [3, 3, 15, 15, 8, 3, 15, 15, 8, 8, 6, 6, 6, 5, 3, 3, 3, 3, 8, 15, 3, 3, 6, 10, 5, 8, 8, 6, 8, 5, 15, 15,
       8, 15, 3, 5, 6, 10, 8, 15, 15, 3, 15, 5, 15, 15, 15, 15, 3, 15, 5, 5, 5, 8, 5, 10, 5, 10, 8, 13, 15, 12, 3, 3]
A3b = [15, 8, 8, 3, 15, 15, 3, 8, 15, 15, 15, 15, 15, 15, 15, 8, 15, 8, 15, 3, 15, 8, 15, 8, 3, 15, 6, 10, 15, 15, 10, 8,
       15, 3, 15, 10, 10, 8, 9, 10, 6, 15, 8, 15, 3, 6, 6, 8, 15, 3, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 3, 15, 15, 8]
WEIGHTS = {2: [0, 21, 43, 64], 3: [0, 9, 18, 27, 37, 46, 55, 64],
           4: [0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64]}
# mode: subsets, partition bits, rotation bits, index-selection bits, colour bits, alpha bits, endpoint p-bits,
# shared p-bits, index bits, second index bits
MODES = [(3, 4, 0, 0, 4, 0, 1, 0, 3, 0), (2, 6, 0, 0, 6, 0, 0, 1, 3, 0), (3, 6, 0, 0, 5, 0, 0, 0, 2, 0),
         (2, 6, 0, 0, 7, 0, 1, 0, 2, 0), (1, 0, 2, 1, 5, 6, 0, 0, 2, 3), (1, 0, 2, 0, 7, 8, 0, 0, 2, 2),
         (1, 0, 0, 0, 7, 7, 1, 0, 4, 0), (2, 6, 0, 0, 5, 5, 1, 0, 2, 0)]


def _expand(v: int, bits: int) -> int:
    v <<= 8 - bits
    return v | v >> bits


def _block(b: bytes) -> list[tuple[int, int, int, int]]:
    """One 16-byte block -> 16 RGBA pixels (row by row)."""
    x = int.from_bytes(b, "little")
    mode = next((m for m in range(8) if x >> m & 1), 8)
    if mode == 8:
        return [(0, 0, 0, 0)] * 16
    ns, pb, rb, isb, cb, ab, epb, spb, ib, ib2 = MODES[mode]
    pos = mode + 1

    def take(n):
        nonlocal pos
        v = x >> pos & ((1 << n) - 1)
        pos += n
        return v

    part, rot, isel = take(pb), take(rb), take(isb)
    ends = [[[0, 0, 0, 255] for _ in range(2)] for _ in range(ns)]
    for c in range(3):
        for s in range(ns):
            for e in range(2):
                ends[s][e][c] = take(cb)
    if ab:
        for s in range(ns):
            for e in range(2):
                ends[s][e][3] = take(ab)
    cbits, abits = cb, ab
    if epb:
        for s in range(ns):
            for e in range(2):
                p = take(1)
                for c in range(4 if ab else 3):
                    ends[s][e][c] = ends[s][e][c] << 1 | p
        cbits, abits = cb + 1, (ab + 1 if ab else 0)
    elif spb:
        for s in range(ns):
            p = take(1)
            for e in range(2):
                for c in range(3):
                    ends[s][e][c] = ends[s][e][c] << 1 | p
        cbits = cb + 1
    for s in range(ns):
        for e in range(2):
            for c in range(3):
                ends[s][e][c] = _expand(ends[s][e][c], cbits)
            ends[s][e][3] = _expand(ends[s][e][3], abits) if abits else 255
    if ns == 1:
        subset, anchors = [0] * 16, {0}
    elif ns == 2:
        subset = [P2[part] >> i & 1 for i in range(16)]
        anchors = {0, A2[part]}
    else:
        subset = P3[part]
        anchors = {0, A3a[part], A3b[part]}
    idx = [take(ib - 1 if i in anchors else ib) for i in range(16)]
    idx2 = [take(ib2 - 1 if i == 0 else ib2) for i in range(16)] if ib2 else None
    out = []
    for i in range(16):
        e0, e1 = ends[subset[i]]
        if idx2 is None:
            wc = wa = WEIGHTS[ib][idx[i]]
        elif isel:  # mode 4, swapped: the 3-bit set colours, the 2-bit set alpha
            wc, wa = WEIGHTS[ib2][idx2[i]], WEIGHTS[ib][idx[i]]
        else:
            wc, wa = WEIGHTS[ib][idx[i]], WEIGHTS[ib2][idx2[i]]
        px = [((64 - wc) * e0[c] + wc * e1[c] + 32) >> 6 for c in range(3)]
        px.append(((64 - wa) * e0[3] + wa * e1[3] + 32) >> 6)
        if rot:
            px[3], px[rot - 1] = px[rot - 1], px[3]
        out.append(tuple(px))
    return out


def decode(data: bytes, width: int, height: int) -> bytearray:
    """BC7 blocks -> RGBA rows."""
    rgba = bytearray(width * height * 4)
    bw = (width + 3) // 4
    for by in range((height + 3) // 4):
        for bx in range(bw):
            o = (by * bw + bx) * 16
            px = _block(data[o:o + 16])
            for i, p in enumerate(px):
                x, y = bx * 4 + i % 4, by * 4 + i // 4
                if x < width and y < height:
                    k = (y * width + x) * 4
                    rgba[k:k + 4] = bytes(p)
    return rgba
