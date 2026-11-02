"""Copy a Legacy of Goku 2 map into the Buu's Fury ROM (same engine, same map format; see RE_NOTES "Maps").

Map record at M (21 words): +0 pre-struct ptr (0x18 bytes, two function pointers), +4 blend, +0x10/+0x14 animated tiles,
+0x18..+0x24 layer headers, +0x28/+0x2C/+0x30 extra regions (count, 0x18-byte records, WFZ mask), +0x34 size,
+0x38/+0x3C collision masks, +0x44 effect id (forced to 0/1, see import_map), +0x48 self pointer, +0x4C tile list, +0x50 page table.
Code pointers are translated LoG2 -> BF (matched by how often each appears in the two games' map records).
BG tile colours are remapped from LoG2's BG palette to the nearest BF BG colours (CIE94), and the remapped tile pages
are stored uncompressed (WFZ type 0).
"""
import struct, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import decompress_stream
import artclean as A

L2B, BFB = 0x08800000, 0x08000000
FN = {0x0880C2A3: 0x08007675, 0x0880DA33: 0x080072CD, 0x0880D91F: 0x0800776D, 0x088056D9: 0x08008087}
L2_PAL, BF_PAL = 0x3ECD1C, 0x701B0


def wfz_len(rom, off):
    t, size = struct.unpack_from('<II', rom, off)
    if t == 0: return 8 + size
    _, end = decompress_stream(rom, off + 8, size)
    return (end - off + 3) & ~3


def wfz_data(rom, off):
    t, size = struct.unpack_from('<II', rom, off)
    return rom[off + 8:off + 8 + size] if t == 0 else bytes(decompress_stream(rom, off + 8, size)[0])


class Writer:
    def __init__(self, rom, at):
        self.rom, self.cur = rom, at
    def put(self, data):
        a = self.cur; self.rom[a:a + len(data)] = data; self.cur = (a + len(data) + 3) & ~3
        return BFB + a


def bg_remap(l2, bf):
    pl = np.frombuffer(l2[L2_PAL:L2_PAL + 768], np.uint8).reshape(256, 3).astype(np.int64)
    pb = np.frombuffer(bf[BF_PAL:BF_PAL + 768], np.uint8).reshape(256, 3).astype(np.int64)
    ll, lb = A.srgb_to_lab(pl), A.srgb_to_lab(pb[1:])
    m = 1 + A.de94(ll[:, None], lb[None]).argmin(1)
    m[0] = 0
    return m.astype(np.uint8)


def obj_remap(l2, bf):
    """LoG2 OBJ palette index -> nearest BF OBJ colour (CIE94). The two games' OBJ palettes differ almost everywhere
    (2 of 256 slots match), so LoG2 map OBJ regions (props, lab doors, pods) drew in wrong colours (user report
    2026-11-02: pink-and-green boulders, a grey sign in chapter 2). Candidates skip the slots any act repaints for new
    art (log4/art/palette_plan.json) so the props look the same in every world."""
    import json
    pl = np.frombuffer(l2[L2_PAL + 768:L2_PAL + 1536], np.uint8).reshape(256, 3).astype(np.int64)
    pb = np.frombuffer(bf[BF_PAL + 768:BF_PAL + 1536], np.uint8).reshape(256, 3).astype(np.int64)
    cand = list(range(1, 256))
    plan = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'log4', 'art', 'palette_plan.json')
    if os.path.exists(plan):
        P = json.load(open(plan)); bad = set(P['global_free']).union(*[set(a['free']) for a in P['acts'].values()])
        cand = [i for i in cand if i not in bad]
    cand = np.array(cand)
    m = cand[A.de94(A.srgb_to_lab(pl)[:, None], A.srgb_to_lab(pb[cand])[None]).argmin(1)]
    m[0] = 0
    return m.astype(np.uint8)


def import_map(bf_rom, l2, M, free_at):
    """bf_rom: bytearray (expanded). Returns (new M bus address, end offset)."""
    w = list(struct.unpack_from('<21I', l2, M))
    o = lambda p: p - L2B
    W = Writer(bf_rom, free_at)
    remap = bg_remap(l2, bf_rom)
    nw = list(w)
    if L2B <= w[0] < L2B + len(l2):
        pre = list(struct.unpack_from('<6I', l2, o(w[0])))
    else:                                                # no pre-struct (e.g. LoG2 8:60, the unnamed pod room): an
        pre = [0x0880C2A3, 0x0880D91F, 0, 0, 0, 0]      # engine warp door with an empty rect, which never fires
    pre = [FN.get(v, v) for v in pre]
    if any(v >= 0x08800000 for v in pre[:2]):            # a LoG2-only door class (e.g. 11:4): an empty-rect warp instead
        pre = [0x08007675, 0x0800776D, 0, 0, 0, 0]
    nw[0] = W.put(struct.pack('<6I', *pre))
    if w[4]:                                             # animated tiles: defs {u8 frames, u8 ntiles, u16 dest slot, frame ptrs}
        from wfz import compress_literal                 # frame = {u32 duration, raw WFZ stream}; colours remapped, re-encoded
        defs = []; fcache = {}
        for k in range(w[4]):
            d = o(struct.unpack_from('<I', l2, o(w[5]) + 4 * k)[0])
            fr, nt, dest = struct.unpack_from('<BBH', l2, d)
            fps = []
            for i in range(fr):
                p = struct.unpack_from('<I', l2, d + 4 + 4 * i)[0]
                if (p, nt) not in fcache:
                    dur = struct.unpack_from('<I', l2, o(p))[0]
                    px = np.frombuffer(decompress_stream(l2, o(p) + 4, nt * 64)[0], np.uint8)
                    fcache[(p, nt)] = W.put(struct.pack('<I', dur) + compress_literal(remap[px].tobytes()))
                fps.append(fcache[(p, nt)])
            defs.append(W.put(struct.pack('<BBH', fr, nt, dest) + struct.pack('<%dI' % fr, *fps)))
        nw[5] = W.put(struct.pack('<%dI' % len(defs), *defs))
    for k in range(4):                                   # layers
        h = w[6 + k]
        if not h: continue
        hw = list(struct.unpack_from('<6I', l2, o(h))); dims = hw[5]; n = (dims & 0xFF) * ((dims >> 8) & 0xFF)
        chunks = struct.unpack_from('<%dI' % n, l2, o(h) + 0x18)
        newc = [W.put(l2[o(c):o(c) + wfz_len(l2, o(c))]) if c else 0 for c in chunks]   # 0 = empty chunk
        hw[0] = FN[hw[0]]
        nw[6 + k] = W.put(struct.pack('<6I', *hw) + struct.pack('<%dI' % n, *newc))
    if w[10]:                                            # OBJ regions: graphic recoloured LoG2 -> BF OBJ palette
        nw[11] = W.put(l2[o(w[11]):o(w[11]) + 0x18 * w[10]])
        g = np.frombuffer(wfz_data(l2, o(w[12])), np.uint8)
        g = obj_remap(l2, bf_rom)[g].tobytes()
        nw[12] = W.put(struct.pack('<II', 0, len(g)) + g)
    for k in (14, 15):                                   # collision masks
        if w[k]: nw[k] = W.put(l2[o(w[k]):o(w[k]) + wfz_len(l2, o(w[k]))])
    # tile list: ids index a game-wide page table (high byte = page). Keep only the pages this map uses, renumbered,
    # and keep only the tiles it uses inside them; the list is rewritten uncompressed.
    tl = np.frombuffer(wfz_data(l2, o(w[19])), '<u2'); ids = np.cumsum(tl.astype(np.int64) + 1) - 1
    used_pages = sorted(set((ids >> 8).tolist()))
    newid = []; pages_out = []
    for pg in used_pages:
        tiles = [int(i) & 0xFF for i in ids if (i >> 8) == pg]
        d = np.frombuffer(wfz_data(l2, o(struct.unpack_from('<I', l2, o(w[20]) + 4 * pg)[0])), np.uint8)
        page = np.zeros(256 * 64, np.uint8)
        for j, t in enumerate(tiles): page[j * 64:(j + 1) * 64] = remap[d[t * 64:(t + 1) * 64]]
        npg = len(pages_out); pages_out.append(page[:len(tiles) * 64].tobytes())
        newid += [(npg << 8) | j for j in range(len(tiles))]
    order = np.argsort(ids, kind='stable')          # ids are increasing already; keep the original order
    newid = np.array(newid, np.int64)
    deltas = np.diff(np.concatenate([[-1], newid])) - 1
    tlb = deltas.astype('<u2').tobytes()
    nw[19] = W.put(struct.pack('<II', 0, len(tlb)) + tlb)
    newp = [W.put(struct.pack('<II', 0, len(pg_)) + pg_) for pg_ in pages_out]
    nw[20] = W.put(struct.pack('<%dI' % len(newp), *newp))
    # +0x44: per-map effect id (likely). LoG2 3:7's value 5 hangs Buu's Fury on load (black screen; BF's own 6:10 uses
    # 5 with its own data); 1 is what every working import has, so anything else is set to 1
    if nw[17] not in (0, 1): nw[17] = 1
    newM = W.cur; nw[18] = BFB + newM
    W.put(struct.pack('<21I', *nw))
    return BFB + newM, W.cur
