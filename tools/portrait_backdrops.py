"""Build-time helpers for Buu's Fury dialogue portraits (64x64 8bpp linear, gold frame + backdrop + face).

Portrait table: ROM 0x6F393C, u32 pointers indexed by speaker id (0 and 7 = none, 1-6 = party slots resolved
through the current form, 8.. = fixed characters). Read by code at 0x08012118 via the literal at ROM 0x12194.
Each pointer -> WFZ container of 4096 bytes (type 0 stored also accepted by the loader - verify).
Frame = pixels identical in every portrait; window 56x56 at (4,4). Backdrops are synthesised from the colour
ramps the game uses (radial gradient, ordered dither), so nothing is copied out of the ROM into the repo.
"""
import struct, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import decompress_stream
import artclean as A

TABLE, LITERAL, FIRST, COUNT, BASE = 0x6F393C, 0x12194, 8, 155, 0x08000000
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0
KEYS = {'cyan': 73, 'red': 105, 'green': 49, 'yellow': 27, 'blue': 96, 'pink': 42, 'purple': 87, 'orange': 4}


def load_all(rom):
    out = []
    for k in range(COUNT):
        o = struct.unpack_from('<I', rom, TABLE + 4 * (FIRST + k))[0] - BASE
        t, s = struct.unpack_from('<II', rom, o)
        d = rom[o + 8:o + 8 + 4096] if t == 0 else bytes(decompress_stream(rom, o + 8, 4096)[0])
        out.append(np.frombuffer(d, np.uint8).reshape(64, 64))
    return np.array(out)


def frame_and_backdrops(rom):
    from collections import Counter
    a = load_all(rom); const = (a == a[0]).all(0); win = ~const
    pal = np.frombuffer(rom[0x701B0 + 768:0x701B0 + 1536], np.uint8).reshape(256, 3).astype(np.int64)
    plab = A.srgb_to_lab(pal)
    yy, xx = np.mgrid[0:64, 0:64]; r = np.hypot(yy - 31.5, xx - 31.5); rb = np.round(r).astype(int)
    border = np.zeros((64, 64), bool); border[4:7, 4:60] = True; border[4:60, 4:7] = True; border[4:60, 57:60] = True; border &= win
    bds = {}
    for name, key in KEYS.items():
        ids = [i for i, p in enumerate(a) if p[6, 6] == key]
        cnt = Counter(a[ids][:, border].ravel().tolist()); kab = plab[key][1:]
        bg = [k for k, c in cnt.most_common(12) if k not in (0, 1, 2, 208) and np.hypot(*(plab[k][1:] - kab)) < 45][:6]
        prof = {}
        for i in ids:
            m = np.isin(a[i], bg) & win & (r >= 18)            # the outer ring is where the backdrop is reliably visible
            for y, x in zip(*np.nonzero(m)): prof.setdefault(rb[y, x], []).append(plab[a[i][y, x]][0])
        rs = sorted(prof); Ls = np.array([np.median(prof[k]) for k in rs])
        Lmap = np.interp(r, rs, Ls)
        ramp = sorted([k for k in bg if plab[k][0] >= Ls.min() - 8], key=lambda k: plab[k][0])
        rl = np.array([plab[k][0] for k in ramp])
        img = a[0].copy()
        for y, x in zip(*np.nonzero(win)):
            L = Lmap[y, x]; j = int(np.searchsorted(rl, L))
            if j <= 0: img[y, x] = ramp[0]
            elif j >= len(rl): img[y, x] = ramp[-1]
            else:
                t = (L - rl[j - 1]) / (rl[j] - rl[j - 1]); img[y, x] = ramp[j] if t > BAYER[y % 4, x % 4] else ramp[j - 1]
        bds[name] = img
    return const, bds


def compose(face_idx, backdrop, const):
    """face_idx: 56x56 (or smaller) index image, 0 = transparent. Returns a 64x64 portrait."""
    out = backdrop.copy(); h, w = face_idx.shape
    y0, x0 = 4 + (56 - h), 4 + (56 - w) // 2                   # bottom-aligned in the window
    sub = out[y0:y0 + h, x0:x0 + w]; m = face_idx != 0; sub[m] = face_idx[m]
    out[const] = backdrop[const]                                 # frame always on top
    return out
