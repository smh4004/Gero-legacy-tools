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


class _BitWriter:
    def __init__(self):
        self.words = bytearray(); self.cur = 0; self.n = 0

    def put(self, v, n):
        for i in range(n - 1, -1, -1):
            self.cur = (self.cur << 1) | ((v >> i) & 1); self.n += 1
            if self.n == 32:
                self.words += struct.pack('<I', self.cur); self.cur = 0; self.n = 0

    def gamma(self, v):                              # v >= 2: the bits after its leading 1, each followed by "more"
        bits = bin(v)[3:]
        for i, b in enumerate(bits):
            self.put(int(b), 1); self.put(1 if i < len(bits) - 1 else 0, 1)

    def done(self):
        if self.n: self.words += struct.pack('<I', self.cur << (32 - self.n))
        return bytes(self.words)


def _glen(v):                                        # bits gamma(v) takes
    return 2 * (v.bit_length() - 1)


def _adj(off):                                       # the decoder's length bonus for a gamma match at this offset
    if off >= 0x10000: return 3
    if off >= 0x37FF: return 2
    if off >= 0x27F: return 1
    if off <= 0x7F: return 4
    return 0


def compress(data, window=0x7FFF, tries=48):
    """LZ encoder for WFZ (greedy with one step of lookahead; offsets up to `window`, 8 offset bits). Uses 8-bit
    literals, the 7-bit zero / near-copy codes, 7-bit short matches, gamma matches and repeat-last-offset matches.
    Returns the raw bitstream (no container header): decompress_stream(out, 0, len(data)) == data."""
    data = bytes(data); n = len(data)
    w = _BitWriter()
    w.put(0b001, 3); w.put(0, 4); w.put(0, 1); w.put(1, 1)          # 8-bit literals
    heads = {}
    last = 1

    def best_at(i, last):
        """-> (bits saved vs literals, length, kind, offset) of the best match starting at i."""
        best = (0, 0, None, 0)
        cands = []
        if i >= last: cands.append(i - last)
        if i + 2 < n:
            cands += heads.get(data[i:i + 3], [])[-tries:]
        if i >= 1 and i + 1 < n:                     # short 2-byte matches near by
            for o in range(1, min(127, i) + 1):
                if data[i - o] == data[i] and data[i - o + 1] == data[i + 1]: cands.append(i - o)
        seen = set()
        for p in reversed(cands):
            off = i - p
            if off in seen or off <= 0 or off > window: continue
            seen.add(off)
            L = 0
            while i + L < n and data[p + L] == data[i + L]: L += 1   # (overlapping copies are fine)
            if L < 2: continue
            opts = []
            if off == last: opts.append((2 + 2 + _glen(L), L, 'rep'))
            if off <= 127:
                l5 = min(L, 5); opts.append((12, l5, 'short'))
            a = _adj(off); g = (off >> 8) + 3
            if L - a >= 2: opts.append((2 + _glen(g) + 8 + _glen(L - a), L, 'gamma'))
            for cost, ln, kind in opts:
                save = 9 * ln - cost
                if save > best[0]: best = (save, ln, kind, off)
        return best

    i = 0
    while i < n:
        save, L, kind, off = best_at(i, last)
        if L and i + 1 < n:                          # one step of lookahead: a literal now, a better match next?
            s2 = best_at(i + 1, last)
            if s2[0] > save + 9: save, L, kind = 0, 0, None
        if kind and save > 2:
            if kind == 'rep':
                w.put(0b01, 2); w.gamma(2); w.gamma(L)
            elif kind == 'short':
                w.put(0b000, 3); w.put(off, 7); w.put(L - 2, 2); last = off
            else:
                w.put(0b01, 2); w.gamma((off >> 8) + 3); w.put(off & 0xFF, 8); w.gamma(L - _adj(off)); last = off
            step = L
        else:
            b = data[i]; step = 1
            near = next((o for o in range(1, min(14, i) + 1) if data[i - o] == b), 0)
            if b == 0: w.put(0b001, 3); w.put(1, 4)                  # special v=0: a zero
            elif near: w.put(0b001, 3); w.put(near + 1, 4)           # special v: copy one byte from v back
            else: w.put(1, 1); w.put(b, 8)
        for j in range(i, min(i + step, n - 2)):
            heads.setdefault(data[j:j + 3], []).append(j)
        i += step
    w.put(0b000, 3); w.put(0, 7); w.put(0, 2)                        # end
    return w.done()


def container(data, typ=1):
    """A WFZ container (type 1, as BF's sprite frames) of data, compressed; stored (type 0) when that is smaller."""
    c = compress(data)
    if len(c) + 8 >= len(data) + 8: return struct.pack('<II', 0, len(data)) + bytes(data)
    return struct.pack('<II', typ, len(data)) + c
