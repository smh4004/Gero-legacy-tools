"""OBJ VRAM check (2026-11-03, user: "make sure nothing appears garbled"). Reads one emulator moment (IWRAM, EWRAM from
0x02020000, OBJ VRAM 0x06010000-0x06017FFF, OAM) and checks the sprite memory the way BF manages it:

BF's OBJ VRAM allocator (IWRAM 0x03001C4C, sub_0801124C) hands out all 1,024 OBJ tiles in 64-byte units: a block table
of 10-byte entries at +0x694 (+0 used, +2 start, +4 size in units, +6 / +7 previous / next block in VRAM order,
+8 next free), the free list head at +0, the registered sprite objects at +4 (count) / +8 (pointers). When it runs out it
evicts objects and compacts (sub_08011732), so a sprite is garbled only if
  A. the block table is broken (overlap, gap, outside OBJ VRAM),
  B. a visible OAM sprite draws tiles that aren't inside one allocated block (stale tiles after a move, or a failed
     allocation: tile index -1), or
  C. a registered object's tiles in VRAM differ from its frame data (its buffer obj+0x44, length obj+0x48) for two
     samples in a row with the same frame (something else wrote over them; the first sample can be an upload in flight).
Also reports the peak use: allocated bytes, free bytes, largest free block.
usage: from vramcheck import sample_lines, check   (tools/vramaudit.py, the playthrough)"""
import struct

ALLOC = 0x03001C4C
EW0 = 0x02020000                       # EWRAM dumped from here (frame buffers live at 0x0202xxxx-0x0203xxxx)
SIZES = {(0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64), (1, 0): (16, 8), (1, 1): (32, 8),
         (1, 2): (32, 16), (1, 3): (64, 32), (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64)}


def sample_lines(tag):
    """Harness lines that dump one sample named tag."""
    return ['dump %s_iw 3000000 8000' % tag, 'dump %s_ew %x 20000' % (tag, EW0), 'dump %s_vr 6010000 8000' % tag,
            'dump %s_oam 7000000 400' % tag, 'dump %s_pal 5000200 200' % tag]


_DEC = {}


def frame_data(rom, frame):
    """The bytes a frame uploads: its pieces' tile blocks ([u32 type 0 raw / 1 WFZ][u32 size][data]) one after another."""
    if frame in _DEC: return _DEC[frame]
    o = frame - 0x08000000; out = b''
    try:
        n = struct.unpack_from('<I', rom, o)[0]
        if not 1 <= n <= 32: return None
        for k in range(n):
            bp = struct.unpack_from('<I', rom, o + 8 + 12 * k + 8)[0] - 0x08000000
            t, size = struct.unpack_from('<II', rom, bp)
            if t == 0: out += rom[bp + 8:bp + 8 + size]
            else:
                import wfz
                out += bytes(wfz.decompress_stream(rom, bp + 8, size)[0])[:size]
    except Exception: return None
    _DEC[frame] = out
    return out


def load(d, tag):
    import os
    p = os.path.join(d, '%s_pal.bin' % tag)
    return tuple(open(os.path.join(d, '%s_%s.bin' % (tag, k)), 'rb').read() for k in ('iw', 'ew', 'vr', 'oam')) + \
        ((open(p, 'rb').read(),) if os.path.exists(p) else ())


def blocks(iw):
    a = ALLOC - 0x03000000
    out = []
    for i in range(128):
        e = a + 0x694 + 10 * i
        used = iw[e]
        if used not in (0, 1): continue
        start, size = struct.unpack_from('<HH', iw, e + 2)
        if size == 0: continue
        out.append((start * 2, size * 2, used, i))           # in 32-byte tiles
    return sorted(out)


def objects(iw):
    a = ALLOC - 0x03000000
    n = struct.unpack_from('<i', iw, a + 4)[0]
    return [struct.unpack_from('<I', iw, a + 8 + 4 * k)[0] for k in range(max(0, min(n, 128)))]


def check(sample, rom, prev=None):
    """sample = (iw, ew, vr, oam). Returns (problems, stats, state for the next call)."""
    iw, ew, vr, oam = sample[:4]
    if len(sample) > 4 and len(set(struct.unpack('<256H', sample[4]))) < 8:
        return [], {'used': 0, 'free': 0, 'largest_free': 32768, 'objects': 0, 'faded': True}, None   # faded: nothing shows
    def rd(addr, n):
        if 0x03000000 <= addr < 0x03008000: return iw[addr - 0x03000000:addr - 0x03000000 + n]
        if EW0 <= addr < 0x02040000: return ew[addr - EW0:addr - EW0 + n]
        if 0x08000000 <= addr < 0x09000000 and rom is not None: return rom[addr - 0x08000000:addr - 0x08000000 + n]
        return None
    probs = []
    bl = blocks(iw)
    # A. the block table tiles OBJ VRAM exactly: contiguous, no overlap, inside 0..1023
    pos = 0
    for s, n, used, i in bl:
        if s != pos: probs.append('A: block table gap/overlap at tile %d (block %d starts %d)' % (pos, i, s))
        pos = max(pos, s + n)
    if pos != 1024: probs.append('A: block table ends at tile %d, not 1024' % pos)
    usedb = [(s, s + n) for s, n, u, _ in bl if u == 1]
    state = {}
    free = [n for s, n, u, _ in bl if u == 0]
    # B. visible OAM sprites draw from allocated tiles only
    for k in range(128):
        a0, a1, a2 = struct.unpack_from('<HHH', oam, 8 * k)
        if (a0 >> 8) & 3 == 2: continue                       # hidden
        y = a0 & 0xFF; x = a1 & 0x1FF
        shape, size = a0 >> 14, a1 >> 14
        if (shape, size) not in SIZES: continue
        w, h = SIZES[(shape, size)]
        if y >= 160 and y + h <= 256: continue                 # off screen (below)
        if x >= 240 and x + w <= 512: continue                 # off screen (right)
        bpp8 = (a0 >> 13) & 1
        tiles = (w // 8) * (h // 8) * (2 if bpp8 else 1)
        t0 = a2 & 0x3FF
        if not any(s <= t0 and t0 + tiles <= e for s, e in usedb):
            px = vr[t0 * 32:min(0x8000, (t0 + tiles) * 32)]
            if not any(px): continue                           # all transparent: shows nothing
            # BF itself lets a sprite on its way out (a damage number) keep drawing tiles it has just freed; that only
            # shows garbage once something else writes there. So: report a sprite that draws unallocated tiles in two
            # samples running and whose pixels changed in between (another sprite's data arrived under it)
            key = ('B', t0, tiles, x, y)
            state[key] = hash(px)
            char = (a2 >> 10) & 3 == 3                         # field characters draw at priority 3 (RE_NOTES clipping)
            if prev and key in prev and (char or prev[key] != state[key]):
                probs.append('B: OAM %d (x %d y %d %dx%d) draws tiles %d-%d outside any allocated block' % (k, x, y, w, h, t0, t0 + tiles - 1))
    # C. registered objects with a frame (a ROM frame record; 0 = none / being removed): VRAM == their frame data
    for o in objects(iw):
        hdr = rd(o, 0x4C)
        if not hdr or len(hdr) < 0x4C: continue
        tile, res = struct.unpack_from('<HH', hdr, 0xC)
        frame, buf, ln = struct.unpack_from('<I', hdr, 0x30)[0], struct.unpack_from('<I', hdr, 0x44)[0], struct.unpack_from('<I', hdr, 0x48)[0]
        if not (0 < ln <= res <= 0x8000) or tile * 32 + ln > 0x8000: continue
        if not 0x08000000 <= frame < 0x09000000: continue      # no frame shown (dead / not drawn) or a non-frame object
        data = rd(buf, ln)                                         # the object's decoded frame (its per-object buffer,
        if not data or len(data) != ln: continue                   # after any recolour; the raw ROM data can differ)
        if not any(s <= tile and tile + (res + 31) // 32 <= e for s, e in usedb):
            probs.append('C: object %08X tiles %d+%d bytes not inside an allocated block' % (o, tile, res))
        cur = vr[tile * 32:tile * 32 + ln]
        # Not every difference is garbage: BF can show another frame of the same character for a while (hit-stun, an
        # upload still queued) or animate a few tiles itself. Garbage brings colours the character doesn't have: count
        # the differing pixels whose colour index isn't in this frame at all (another sprite's or random data).
        own = set(data) | {0}
        foreign = sum(1 for i in range(ln) if cur[i] != data[i] and cur[i] not in own) if cur != data else 0
        bad = foreign >= 8
        state[o] = (frame, bad)
        if bad and prev and prev.get(o) == (frame, True):     # and it stays: two samples running, same frame
            diff = foreign
            probs.append('C: object %08X (class %08X) tiles %d: %d of %d pixels in colours its frame %08X does not use' %
                         (o, struct.unpack_from('<I', hdr, 0)[0], tile, diff, ln, frame))
    stats = {'used': sum(e - s for s, e in usedb) * 32, 'free': sum(free) * 32, 'largest_free': max(free + [0]) * 32,
             'objects': len(objects(iw))}
    return probs, stats, state
