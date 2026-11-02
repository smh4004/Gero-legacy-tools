"""Webfoot compression ("WFZ") used by Buu's Fury.

Ported from the ARM routine the game copies to IWRAM 0x03000040 (ROM 0x7B79E4).
Container: u32 type (0 = stored, 1/2 = compressed), u32 decompressed size, then a
32-bit-word bitstream (little-endian words, bits consumed MSB-first).
aPLib-like: 0=literal, 10=gamma match, 110=7-bit short match, 111=4-bit/special.
"""
import struct


class _Bits:
    def __init__(self, data, pos):
        self.d = data
        self.p = pos
        self.buf = 0
        self.left = 0

    def _word(self):
        w = struct.unpack_from('<I', self.d, self.p)[0]
        self.p += 4
        return w

    def bit(self):
        self.left -= 1
        if self.left < 0:
            self.buf = self._word()
            self.left = 31
        b = (self.buf >> 31) & 1
        self.buf = (self.buf << 1) & 0xFFFFFFFF
        return b

    def bits(self, n):
        if self.left == 0:
            self.buf = self._word()
            self.left = 32
        fp = min(n, self.left)
        r = (self.buf >> (32 - fp)) if fp else 0
        self.buf = (self.buf << fp) & 0xFFFFFFFF
        self.left -= fp
        n -= fp
        if n == 0:
            return r
        self.buf = self._word()
        self.left = 32 - n
        r = (self.buf >> self.left) + (r << n)
        self.buf = (self.buf << n) & 0xFFFFFFFF
        return r

    def gamma(self):
        v = 1
        while True:
            v = v * 2 + self.bit()
            if not self.bit():
                return v


def decompress_stream(data, pos, size, lit_bits=1, lit_base=0):
    b = _Bits(data, pos)
    out = bytearray()
    offbits = 8
    last = 1
    r3, r4 = lit_bits, lit_base

    def copy(off, n):
        for _ in range(n):
            out.append(out[-off])

    while True:
        if b.bit():                      # 0x...: literal
            out.append((b.bits(r3) + r4) & 0xFF)
            continue
        if b.bit():                      # 10: gamma match
            g = b.gamma()
            if g == 2:                   # repeat last offset
                copy(last, b.gamma())
                continue
            g -= 3
            last = b.bits(offbits) + (g << offbits)
            n = b.gamma()
            if last >= 0x10000:
                n += 3
            elif last >= 0x37FF:
                n += 2
            elif last >= 0x27F:
                n += 1
            elif last <= 0x7F:
                n += 4
            copy(last, n)
            continue
        if not b.bit():                  # 110: short match / control
            v = b.bits(7)
            if v == 0:
                k = b.bits(2)
                if k == 0:
                    break                # end of stream
                offbits = b.bits(k + 3)
                continue
            last = v
            copy(last, b.bits(2) + 2)
            continue
        v = b.bits(4) - 1                # 111
        if v == 0:
            out.append(0)
        elif v > 0:
            out.append(out[-v])
        elif not b.bit():                # literal mode change
            r4 = 0
            r3 = 7 + b.bit()
            if r3 != 8:
                r4 = b.bits(8)
        else:                            # raw 256-byte blocks
            while True:
                for _ in range(256):
                    out.append(b.bits(8))
                if not b.bit():
                    break
    return bytes(out), b.p


def unpack(data, off):
    """Decode the container at ROM offset `off`. Returns (bytes, end_offset)."""
    typ, size = struct.unpack_from('<II', data, off)
    if typ == 0:
        return data[off + 8:off + 8 + size], off + 8 + size
    out, end = decompress_stream(data, off + 8, size)
    return out, end


def compress_literal(data):
    """Minimal WFZ encoder: switch to 8-bit literals, emit every byte as a literal, then the end marker.
    No matching, so output is ~1.1x the input - enough where the game insists on a compressed stream
    (e.g. animated-tile frames). Returns the raw bitstream (no container header)."""
    bits = []
    put = lambda v, n: bits.extend(((v >> (n - 1 - i)) & 1) for i in range(n))
    put(0b001, 3); put(0, 4); put(0, 1); put(1, 1)          # special (001), v=-1, mode change, 8-bit literals
    for b in data:
        put(1, 1); put(b, 8)
    put(0b000, 3); put(0, 7); put(0, 2)                      # control (000), v=0, k=0 -> end
    while len(bits) % 32: bits.append(0)
    out = bytearray()
    for i in range(0, len(bits), 32):
        w = 0
        for b in bits[i:i + 32]: w = (w << 1) | b
        out += struct.pack('<I', w)
    return bytes(out)
