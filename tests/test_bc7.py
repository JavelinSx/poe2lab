"""BC7 decoding (poe2lab.bc7): the partition tables agree with their anchors, and a hand-made mode 6 block decodes."""
from poe2lab import bc7


def test_tables_are_consistent():
    assert len(bc7.P2) == len(bc7.P3) == len(bc7.A2) == len(bc7.A3a) == len(bc7.A3b) == 64
    for i in range(64):
        assert bc7.P2[i] & 1 == 0 and bc7.P2[i] >> bc7.A2[i] & 1 == 1  # pixel 0 in subset 0, the anchor in subset 1
        assert bc7.P3[i][0] == 0 and bc7.P3[i][bc7.A3a[i]] == 1 and bc7.P3[i][bc7.A3b[i]] == 2


def test_mode6_solid_block():
    # mode 6: bit 6 set; both endpoints 127 (7 bits) with p-bit 1 -> 255 on every channel, all indices 0
    bits, pos = 1 << 6, 7
    for _ in range(8):  # R0 R1 G0 G1 B0 B1 A0 A1
        bits |= 127 << pos
        pos += 7
    bits |= 0b11 << pos  # the two p-bits
    px = bc7._block(bits.to_bytes(16, "little"))
    assert px == [(255, 255, 255, 255)] * 16
