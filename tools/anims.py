"""Buu's Fury actor / animation tables.

Actor list: 298 pointers at ROM 0x6B6BD8 (actor id = index).
Actor record (P): +0 u32 flags (low byte = number of animation slots N, high byte = actor class),
  +0x14..+0x50 four (x, y, w, h) s32 boxes (one per direction), +0x54 N animation pointers (0 = empty slot).
Animation: u32 frame_count, then frame_count * 4 frame pointers (frame-major, 4 directions per frame).
Frame: u32 piece_count, then pieces of 16 bytes: [s8 x, s8 y, u8 w, u8 h][u32 box2][u32 OAM attr][u32 WFZ tile block ptr].
"""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import decompress_stream
import numpy as np

SZ = {0: [(8, 8), (16, 16), (32, 32), (64, 64)], 1: [(16, 8), (32, 8), (32, 16), (64, 32)], 2: [(8, 16), (8, 32), (16, 32), (32, 64)]}
ACTOR_LIST, ACTOR_COUNT, BASE = 0x6B6BD8, 298, 0x08000000


class Actors:
    def __init__(self, rom):
        self.rom = rom
        self._tiles = {}

    def u32(self, a): return struct.unpack_from('<I', self.rom, a)[0]
    def s8(self, a): return struct.unpack_from('<b', self.rom, a)[0]
    def ok(self, p): return BASE <= p < BASE + len(self.rom)

    def actor(self, i):
        p = self.u32(ACTOR_LIST + 4 * i) - BASE
        flags = self.u32(p)
        n = flags & 0xFF
        slots = [self.u32(p + 0x54 + 4 * k) for k in range(n)]
        return dict(id=i, addr=p, flags=flags, cls=flags >> 24, n=n, slots=slots)

    def anim(self, ptr):
        if not self.ok(ptr): return None
        a = ptr - BASE
        n = self.u32(a)
        if not (0 < n < 64): return None
        fr = [[self.u32(a + 4 + 4 * (k * 4 + d)) for d in range(4)] for k in range(n)]
        return fr

    def piece_img(self, attr, tptr):
        key = (attr, tptr)
        if key in self._tiles: return self._tiles[key]
        a0, a1 = attr & 0xFFFF, attr >> 16
        sh, sz = (a0 >> 14) & 3, (a1 >> 14) & 3
        if sh == 3 or not self.ok(tptr): return None
        w, h = SZ[sh][sz]
        o = tptr - BASE
        try:
            d, _ = decompress_stream(self.rom, o + 8, self.u32(o + 4))
        except Exception:
            return None
        tw = w // 8; idx = np.zeros((h, w), np.uint8)
        for t in range(min(len(d) // 64, tw * (h // 8))):
            idx[(t // tw) * 8:(t // tw) * 8 + 8, (t % tw) * 8:(t % tw) * 8 + 8] = np.frombuffer(d[64 * t:64 * t + 64], np.uint8).reshape(8, 8)
        if a1 & 0x1000: idx = idx[:, ::-1]          # hflip
        if a1 & 0x2000: idx = idx[::-1, :]          # vflip
        self._tiles[key] = idx
        return idx

    def frame(self, ptr, canvas=(64, 64), origin=(32, 48)):
        """Compose a frame's pieces onto a canvas; origin = actor position (feet)."""
        img = np.zeros((canvas[1], canvas[0]), np.uint8)
        if not self.ok(ptr): return img
        f = ptr - BASE
        n = self.u32(f)
        if not (0 < n <= 16): return img
        for k in range(n):
            q = f + 4 + 16 * k
            x, y = self.s8(q), self.s8(q + 1)
            attr, tp = self.u32(q + 8), self.u32(q + 12)
            pi = self.piece_img(attr, tp)
            if pi is None: continue
            X, Y = origin[0] + x, origin[1] + y
            h, w = pi.shape
            ys, xs = slice(max(0, Y), min(canvas[1], Y + h)), slice(max(0, X), min(canvas[0], X + w))
            sub = pi[ys.start - Y:ys.stop - Y, xs.start - X:xs.stop - X]
            tgt = img[ys, xs]; m = sub != 0; tgt[m] = sub[m]
        return img
