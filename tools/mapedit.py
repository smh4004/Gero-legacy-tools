"""Edit a BF map's pixels and write it back as a new map record (used for the title logo; reusable for any map).

load(rom, M) decodes every layer of the map record at ROM offset M into an 8bpp index canvas (tile-exact, via the map's
tile list / pages / chunks). save(rom, M, canvases, at) re-tiles the canvases: identical 8x8 tiles (including h/v flips)
are shared, pages and the tile list are written uncompressed (WFZ type 0), each layer gets new chunks and a new header,
and a copy of the map record is written with the new pointers. Returns (new M bus address, end offset). Animated tiles
are not supported (asserted). See RE_NOTES "Maps" for the record layout.
"""
import struct, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import unpack

BASE = 0x08000000


def _u32(r, o): return struct.unpack_from('<I', r, o)[0]


def _wfz(r, ptr): return np.frombuffer(bytes(unpack(r, ptr - BASE)[0]), np.uint8)


def tiles_of(r, M):
    raw = _wfz(r, _u32(r, M + 0x4C)).view('<u2').astype(np.int64)
    ids = np.cumsum(raw + 1) - 1
    table = _u32(r, M + 0x50) - BASE
    out = np.zeros((len(ids), 8, 8), np.uint8); pages = {}
    for k, gid in enumerate(ids):
        p = int(gid) >> 8
        if p not in pages: pages[p] = _wfz(r, _u32(r, table + 4 * p))
        t = int(gid) & 0xFF
        if 64 * t + 64 <= len(pages[p]): out[k] = pages[p][64 * t:64 * t + 64].reshape(8, 8)
    return out


def load(r, M):
    """-> {layer: (canvas uint8 HxW, header words list)} for the non-empty layers of map record M (ROM offset)."""
    assert _u32(r, M + 0x10) == 0, 'animated tiles not supported'
    tiles = tiles_of(r, M); out = {}
    for i in range(4):
        hp = _u32(r, M + 0x18 + 4 * i)
        if not hp: continue
        h = hp - BASE; hw = list(struct.unpack_from('<6I', r, h)); w, ht = hw[5] & 0xFF, (hw[5] >> 8) & 0xFF
        if not w: continue
        can = np.zeros((ht * 256, w * 256), np.uint8)
        for ci in range(w * ht):
            cp = _u32(r, h + 0x18 + 4 * ci)
            ch = _wfz(r, cp)[:2048].view('<u2').reshape(32, 32)
            cy, cx = (ci // w) * 256, (ci % w) * 256
            for ty in range(32):
                for tx in range(32):
                    v = int(ch[ty, tx]); t = v & 0x3FF
                    if t == 0 or t >= len(tiles): continue
                    tl = tiles[t]
                    if v & 0x400: tl = tl[:, ::-1]
                    if v & 0x800: tl = tl[::-1, :]
                    can[cy + ty * 8:cy + ty * 8 + 8, cx + tx * 8:cx + tx * 8 + 8] = tl
        out[i] = (can, hw)
    return out


def save(r, M, layers, at):
    """layers: {i: (canvas, header words)} as from load(), canvases edited. r: bytearray. Writes at offset `at`."""
    cur = [at]
    def put(data):
        a = cur[0]; r[a:a + len(data)] = data; cur[0] = (a + len(data) + 3) & ~3
        return BASE + a
    w = list(struct.unpack_from('<21I', r, M))
    uniq = [np.zeros((8, 8), np.uint8)]; index = {uniq[0].tobytes(): (0, 0)}   # slot 0 = empty tile
    def slot(tl):
        for flip, t in ((0, tl), (0x400, tl[:, ::-1]), (0x800, tl[::-1, :]), (0xC00, tl[::-1, ::-1])):
            k = t.tobytes()
            if k in index: s, f = index[k]; return s | (f ^ flip)
        index[tl.tobytes()] = (len(uniq), 0); uniq.append(tl.copy()); return len(uniq) - 1
    new_hdr = {}
    for i, (can, hw) in layers.items():
        cw, chh = hw[5] & 0xFF, (hw[5] >> 8) & 0xFF
        chunks = []
        for ci in range(cw * chh):
            cy, cx = (ci // cw) * 256, (ci % cw) * 256
            m = np.zeros((32, 32), np.uint16)
            for ty in range(32):
                for tx in range(32):
                    m[ty, tx] = slot(can[cy + ty * 8:cy + ty * 8 + 8, cx + tx * 8:cx + tx * 8 + 8])
            d = m.astype('<u2').tobytes()
            chunks.append(put(struct.pack('<II', 0, len(d)) + d))
        new_hdr[i] = put(struct.pack('<6I', *hw) + struct.pack('<%dI' % len(chunks), *chunks))
    assert len(uniq) <= 896, 'too many tiles (%d) for BG VRAM' % len(uniq)
    pages = []
    for p in range(0, len(uniq), 256):
        blk = b''.join(t.tobytes() for t in uniq[p:p + 256])
        pages.append(put(struct.pack('<II', 0, len(blk)) + blk))
    ids = np.arange(len(uniq), dtype=np.int64)
    ids = (ids // 256) * 256 + ids % 256                       # page<<8 | tile
    deltas = np.diff(np.concatenate([[-1], ids])) - 1
    tl = deltas.astype('<u2').tobytes()
    w[19] = put(struct.pack('<II', 0, len(tl)) + tl)
    w[20] = put(struct.pack('<%dI' % len(pages), *pages))
    for i, hp in new_hdr.items(): w[6 + i] = hp
    newM = cur[0]
    if w[18]: w[18] = BASE + newM                              # self pointer (0 in some scene maps)
    put(struct.pack('<21I', *w))
    return BASE + newM, cur[0]
