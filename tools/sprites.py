"""Insert new sprite animations into Buu's Fury (format in RE_NOTES "Actors and animations").

Animation = u32 frame_count, then frame_count x 4 frame pointers (dir 0 down, 1 up, 2 side, 3 = side mirrored).
Frame = u32 piece_count, pieces of 16 bytes: [s8 x, s8 y, u8 w, u8 h][same 4 bytes][u32 OAM attr0|attr1<<16][u32 tile ptr].
Pieces are placed relative to the actor origin, which sits 8 px right of the piece's left edge for a 16-wide sprite and
8 px above its bottom (x = 8 - w/2 for a centred piece, y = 8 - h). Dir 3 mirrors dir 2: x3 = 16 - w - x2, attr1 |= 0x1000.
Tiles are stored uncompressed (WFZ type 0), 8bpp, 1D mapping order; colours are OBJ palette indices.
"""
import json, struct
import numpy as np

SHAPE = {(8, 8): (0, 0), (16, 16): (0, 1), (32, 32): (0, 2), (64, 64): (0, 3), (16, 8): (1, 0), (32, 8): (1, 1),
         (32, 16): (1, 2), (64, 32): (1, 3), (8, 16): (2, 0), (8, 32): (2, 1), (16, 32): (2, 2), (32, 64): (2, 3)}
BASE = 0x08000000


def tiles_8bpp(idx):
    h, w = idx.shape
    out = bytearray()
    for ty in range(h // 8):
        for tx in range(w // 8):
            out += idx[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].astype(np.uint8).tobytes()
    return bytes(out)


class Inserter:
    def __init__(self, rom, at):
        self.rom, self.cur = rom, at

    def put(self, data):
        a = self.cur; self.rom[a:a + len(data)] = data; self.cur = (a + len(data) + 3) & ~3
        return BASE + a

    def piece(self, img, mirror=False, dx=0, dy=0):
        """img: h x w index array (an OBJ size). Returns the 16-byte piece."""
        h, w = img.shape
        sh, sz = SHAPE[(w, h)]
        tile = self.put(struct.pack('<II', 0, w * h) + tiles_8bpp(img))
        x = 8 - w // 2 + dx; y = 8 - h + dy
        a1 = (sz << 14)
        if mirror: x = 16 - w - x; a1 |= 0x1000
        a0 = (sh << 14) | 0x2000                       # 8bpp
        box = struct.pack('<bbBB', x, y, w, h)
        return box + box + struct.pack('<HHI', a0, a1, tile), tile

    def frame(self, img, mirror=False):
        """Crop the cell to its art and cover it with as few/small OBJ pieces as possible (VRAM budget per frame).
        The cell's bottom-centre stays the actor origin. Identical frames are written once (frame cache)."""
        key = (img.shape, img.tobytes(), mirror, getattr(self, 'oy', 0))
        cache = self.__dict__.setdefault('_frames', {})
        if key not in cache: cache[key] = self._frame(img, mirror)
        return cache[key]

    def _frame(self, img, mirror=False):
        ch, cw = img.shape
        ys, xs = np.nonzero(img)
        if not len(ys): ys, xs = np.array([ch - 1]), np.array([cw // 2])
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        pieces = cover(x1 - x0, y1 - y0)
        # the engine draws ONE piece per character frame and reserves 1 KB of VRAM (32x32 8bpp) for it: anything
        # bigger is cut off or overwrites the next actor's tiles, so refuse it here instead of shipping a clipped sprite
        assert pieces and len(pieces) == 1 and pieces[0][2] * pieces[0][3] <= 1024 and \
            pieces[0][2] >= x1 - x0 and pieces[0][3] >= y1 - y0, \
            'sprite frame %dx%d does not fit one 32x32 piece (art must be shrunk to fit, see artclean.place_in_cell)' \
            % (x1 - x0, y1 - y0)
        out = []
        for (px, py, w, h) in pieces:
            sub = np.zeros((h, w), np.uint8)
            part = img[y0 + py:min(y1, y0 + py + h), x0 + px:min(x1, x0 + px + w)]
            sub[:part.shape[0], :part.shape[1]] = part
            # offsets relative to the 16-wide/8-below origin convention, measured from the cell's bottom centre
            dx = (x0 + px) - (cw // 2 - 8) - (8 - w // 2)
            dy = (y0 + py) - (ch - 8) - (8 - h) + getattr(self, 'oy', 0)   # oy: cell bottom below origin+8
            pc, _ = self.piece(sub, mirror, dx, dy)
            if mirror:                                   # mirror the whole layout, not just each piece
                x = 16 - w - ((x0 + px) - (cw // 2 - 8))
                pc = struct.pack('<bbBB', x, pc[1] if pc[1] < 128 else pc[1] - 256, w, h) * 2 + pc[8:]
            out.append(pc)
        self.budget_max = max(getattr(self, 'budget_max', 0), sum(w * h for _, _, w, h in pieces))
        return self.put(struct.pack('<I', len(out)) + b''.join(out))

    def anim(self, frames_by_dir):
        """frames_by_dir: [down_frames, up_frames, side_frames] (lists of index arrays, same length)."""
        n = len(frames_by_dir[0])
        ptrs = []
        for k in range(n):
            d, u, s = frames_by_dir[0][k], frames_by_dir[1][k], frames_by_dir[2][k]
            ptrs += [self.frame(d), self.frame(u), self.frame(s), self.frame(s, mirror=True)]
        return self.put(struct.pack('<I', n) + struct.pack('<%dI' % len(ptrs), *ptrs))


def cover(w, h, multi=False):
    """Smallest OBJ shape covering a w x h box. Character/NPC actors only ever use ONE piece per frame (no BF
    class 2/4 frame has more, and a second piece is not drawn), so multi-piece layouts are opt-in."""
    best = None
    for (W, H) in SHAPE:
        if W >= w and H >= h and (best is None or W * H < best[0]): best = (W * H, [(0, 0, W, H)])
    if not multi and best: return best[1]
    for split in ('v', 'h'):
        for (W1, H1) in SHAPE:
            for (W2, H2) in SHAPE:
                if split == 'v' and W1 >= w and W2 >= w and H1 + H2 >= h and H1 < h:
                    cand = (W1 * H1 + W2 * H2, [(0, 0, W1, H1), (0, H1, W2, H2)])
                elif split == 'h' and H1 >= h and H2 >= h and W1 + W2 >= w and W1 < w:
                    cand = (W1 * H1 + W2 * H2, [(0, 0, W1, H1), (W1, 0, W2, H2)])
                else: continue
                if best is None or cand[0] < best[0]: best = cand
    return best[1]


def set_slot(rom, actor_id, slot, anim_ptr, actor_list=0x6B6BD8):
    p = struct.unpack_from('<I', rom, actor_list + 4 * actor_id)[0] - BASE
    n = struct.unpack_from('<I', rom, p)[0] & 0xFF
    assert slot < n
    struct.pack_into('<I', rom, p + 0x54 + 4 * slot, anim_ptr)


CUR_ACTOR = None
FRAME_HOOK = None                    # debug: called with (key, frame of BF OBJ indices) for every frame built

# ---------- actor table relocation + new actors ----------
ACTOR_LIST, ACTOR_COUNT = 0x6B6BD8, 298
ACTOR_LITERALS = (0x3C0, 0x1715C)        # both hold list+4; code reads [lit + 4*idx - 0x28] (game idx = actor id + 10)


def sheet_frames(clean_dir, sid):
    import os
    from PIL import Image
    out = []; n = 0
    while os.path.exists(os.path.join(clean_dir, '%s_%02d.png' % (sid, n))):
        out.append(np.array(Image.open(os.path.join(clean_dir, '%s_%02d.png' % (sid, n))))); n += 1
    return out


def by_direction(frames, mode=None):
    """Sheets are ordered DOWN frames, UP frames, RIGHT frames (equal thirds). A sheet that isn't a multiple of 3 is
    treated as single-view and reused for every direction; mode 'side' / 'front' forces that (e.g. a 3-frame side-only KO)."""
    if mode is None and len(frames) % 3 == 0 and frames:
        k = len(frames) // 3; return [frames[:k], frames[k:2 * k], frames[2 * k:]]
    return [frames, frames, frames]


def slot_frames(clean_dir, spec):
    """Slot spec: 'SHEET', 'SHEET@a:b' (frames a..b-1 of each direction), with an optional '!side' / '!front' suffix
    for single-view sheets. Returns [down, up, side] frame lists or None."""
    mode = None
    if '!' in spec: spec, mode = spec.split('!')
    raw = None                                     # 'SHEET#a:b' = frames a..b-1 of the sheet itself, before the split
    if '#' in spec:
        spec, r = spec.split('#'); a_, b_ = r.split(':'); raw = slice(int(a_), int(b_))
    sl = None
    if '@' in spec:
        spec, r = spec.split('@'); a, b = r.split(':'); sl = slice(int(a), int(b))
    fr = sheet_frames(clean_dir, spec)
    if raw: fr = fr[raw]
    if not fr: return None
    dirs = by_direction(fr, mode)
    return [d[sl] for d in dirs] if sl else dirs


def stretch(dirs, n):
    """Repeat frames evenly so each direction has n frames (the replaced slot's own count: fight code may time hits
    and effects by frame index)."""
    if not n or len(dirs[0]) >= n: return dirs
    k = len(dirs[0]); idx = [i * k // n for i in range(n)]
    return [[d[i] for i in idx] for d in dirs]


def build_actors(rom, cfg, clean_dir, at, l2=None, colour_ctx=None, proto=None):
    """cfg: {name: {"template": actor id, "slots": {slot: sheet id}}}. Moves the actor table to `at`, appends one
    actor per entry (record cloned from the template, animation slots replaced), returns ({name: actor id}, end)."""
    ins = Inserter(rom, at + 4 * (ACTOR_COUNT + len(cfg)) + 16)
    table = list(struct.unpack_from('<%dI' % ACTOR_COUNT, rom, ACTOR_LIST))
    ids = {}; anims = {}
    global CUR_ACTOR
    for name, a in cfg.items():
        if name.startswith('_'): continue
        CUR_ACTOR = name
        target = a.get('replace')                          # modify an existing actor instead of adding one
        if 'proto_actor' in a:                             # whole actor copied from the Prototype D cart
            if proto is None: continue
            rec = proto_actor(ins, proto, a['proto_actor']); n = rec[0]
        else:
            if 'template_orig' in a:                       # BF's own record, even if that actor was replaced above
                tp = struct.unpack_from('<I', rom, ACTOR_LIST + 4 * a['template_orig'])[0] - BASE
            else:
                tp = table[target if target is not None else a['template']] - BASE
            flags = struct.unpack_from('<I', rom, tp)[0]; n = flags & 0xFF
            rec = bytearray(rom[tp:tp + 0x54 + 4 * n])
        if not a.get('halo'):                              # record +0x50 = per-slot halo/attachment table (Other World)
            struct.pack_into('<I', rec, 0x50, 0)
        recol = None; rkey = json.dumps(a.get('recolor'), sort_keys=True)
        if a.get('recolor'):                               # alternate outfit: region-aware index swaps (tools/recolor.py)
            import recolor as _rc
            recol = _rc.make(a['recolor'])
        if 'log2_record' in a and l2 is not None:          # animations taken from a LoG2 actor
            usable, pal_rgb = colour_ctx(a.get('act'))
            cmap = log2_colour_map(l2, usable, pal_rgb); cache = {}
            edit = None
            if a.get('log2_edit'):                         # {"onearm": [mode per direction], "ssj": bool, "skip": [anims]}
                import onearm                              # applies to the actor's own log2_record only
                ed = a['log2_edit']; modes, skip, ssj = ed.get('onearm'), ed.get('skip', []), ed.get('ssj')
                def edit(r, k, d, img, base=log2_rec(l2, a['log2_record'])):
                    if r != base: return None, img
                    m = 'none' if (k in skip or not modes) else modes[d]
                    key = (m, ssj)
                    if img is not None:
                        img = onearm.remove_arm(img, m)
                        if ssj: img = onearm.ssj_hair(img)
                    return key, img
            for slot, k in a.get('log2_slots', {}).items():
                if int(slot) >= n: continue                # the template has fewer slots (e.g. Goku 106 has 16)
                old = struct.unpack_from('<I', rec, 0x54 + 4 * int(slot))[0]
                want = struct.unpack_from('<I', rom, old - BASE)[0] if a.get('stretch') and old else 0
                src = a['log2_record']
                if str(k).startswith('r'): src, k = str(k).split(':', 1)    # "r51:3@0:2" = LoG2 actor 51, anim 3
                k, sl = (str(k).split('@') + [None])[:2]
                sl = slice(*map(int, sl.split(':'))) if sl else None
                ptr = log2_anim(ins, l2, log2_rec(l2, src), int(k), cmap, cache, want, sl, edit, a.get('log2_scale', {}).get(str(src)), recol)
                if ptr: struct.pack_into('<I', rec, 0x54 + 4 * int(slot), ptr)
        if 'raw_frames' in a:                              # frames given as arrays of BF OBJ indices (tools/doors.py:
            ins.oy = a.get('origin_dy', 0)                 # map door regions already draw with the BF OBJ palette)
            for slot, dirs in a['raw_frames'].items():
                if int(slot) >= n: continue
                struct.pack_into('<I', rec, 0x54 + 4 * int(slot), ins.anim(dirs))
            ins.oy = 0
        for d, box in a.get('boxes', {}).items():          # per-direction (x, y, w, h) box override
            struct.pack_into('<4i', rec, 0x14 + 16 * int(d), *box)
        for slot, spec in a.get('slots', {}).items():
            if int(slot) >= n: continue                    # the template has fewer slots
            old = struct.unpack_from('<I', rec, 0x54 + 4 * int(slot))[0]
            want = struct.unpack_from('<I', rom, old - BASE)[0] if (target is not None or a.get('stretch')) and old else 0
            key = (spec, want, rkey)
            if key not in anims:
                dirs = slot_frames(clean_dir, spec)
                if dirs and recol: dirs = [[recol(f) for f in dd] for dd in dirs]
                if dirs and FRAME_HOOK:
                    for di, dd in enumerate(dirs):
                        for fi, f in enumerate(dd): FRAME_HOOK(('sheet', spec, di, fi), f)
                anims[key] = ins.anim(stretch(dirs, want)) if dirs else None
            if anims[key]: struct.pack_into('<I', rec, 0x54 + 4 * int(slot), anims[key])
        if target is not None:
            table[target] = ins.put(bytes(rec)); ids[name] = target
        else:
            ids[name] = len(table); table.append(ins.put(bytes(rec)))
    rom[at:at + 4 * len(table)] = struct.pack('<%dI' % len(table), *table)
    for lit in ACTOR_LITERALS:
        struct.pack_into('<I', rom, lit, BASE + at + 4)
    return ids, ins.cur


# ---------- LoG2 actors ----------
L2_BASE, L2_PAL = 0x08800000, 0x3ECD1C
L2_ACTORS = 0x3B4F30             # LoG2 actor list (154 records)


def log2_rec(l2, ref):
    """A LoG2 actor record: "0x..." = slice offset of the record, "rN" = entry N of the actor list."""
    if str(ref).startswith('r'): return struct.unpack_from('<I', l2, L2_ACTORS + 4 * int(str(ref)[1:]))[0] - L2_BASE
    return int(ref, 16)


def log2_colour_map(l2, usable, pal_rgb):
    """LoG2 OBJ index -> BF OBJ index (CIE94 nearest among `usable`)."""
    import artclean as A
    pl = np.frombuffer(l2[L2_PAL + 768:L2_PAL + 1536], np.uint8).reshape(256, 3).astype(np.int64)
    ul = A.srgb_to_lab(pal_rgb[usable])
    m = np.array(usable)[A.de94(A.srgb_to_lab(pl)[:, None], ul[None]).argmin(1)]
    m[0] = 0
    return m.astype(np.uint8)


def log2_anim(ins, l2, rec, k, cmap, cache, want=0, sl=None, edit=None, scale=None, recol=None):
    """Convert LoG2 animation k of the actor record at slice offset `rec` into a BF animation. Returns ptr or 0.
    sl = frames a..b-1 only (a slice with a step, e.g. 3:-5:-1, plays them backwards); want = repeat frames evenly to
    that count (the replaced BF slot's own frame count). edit(k, d, pixels) -> (key, pixels): optional pixel edit of each
    frame (LoG2 colour indices, h x w) before conversion, e.g. tools/onearm.py. scale: shrink each frame by this factor
    (majority vote per block) and fit it into one 32x32 piece (big LoG2 actors such as Cell are 64x64; BF characters
    get 1 KB of OBJ VRAM per frame)."""
    from wfz import decompress_stream
    u = lambda o: struct.unpack_from('<I', l2, o)[0]
    dirs = [u(rec + 0x4C + 16 * k + 4 * d) for d in range(4)]
    if not any(dirs): return 0
    us = sorted(set(x for x in dirs if x)); gaps = [b - a for a, b in zip(us, us[1:])]
    n = min(gaps) // 12 if gaps else 1          # directions are consecutive runs; some share one run (e.g. a KO)
    if not gaps:                                # one run for every direction: count frames until the next record
        n = 1
        while n < 12:
            r = us[0] - L2_BASE + 12 * n; x, y, w, h = struct.unpack_from('<bbBB', l2, r)
            tp = u(r + 8)
            if not (w and h and w * h <= 4096 and L2_BASE <= tp < L2_BASE + len(l2)): break
            n += 1
    idx = list(range(n))[sl] if sl else list(range(n))
    if want and len(idx) < want: idx = [idx[i * len(idx) // want] for i in range(want)]
    ptrs = []
    for f in idx:
        for d in range(4):
            r = (dirs[d] or dirs[2] or us[0]) - L2_BASE + 12 * f
            x, y, w, h = struct.unpack_from('<bbBB', l2, r)
            attr, tp = struct.unpack_from('<II', l2, r + 4)
            assert scale or w * h <= 1024, 'LoG2 frame %dx%d at %x is over the 1 KB one-piece budget' % (w, h, r)
            ek = edit(rec, k, d, None)[0] if edit else None
            key = (tp, ek, scale, id(recol))
            if key not in cache:
                o = tp - L2_BASE; t, size = struct.unpack_from('<II', l2, o)
                data = l2[o + 8:o + 8 + size] if t == 0 else bytes(decompress_stream(l2, o + 8, size)[0])
                px = np.frombuffer(data, np.uint8).copy()
                img = px[:w * h].reshape(h // 8, w // 8, 8, 8).transpose(0, 2, 1, 3).reshape(h, w)
                if ek is not None: img = edit(rec, k, d, img)[1]
                fbox = (x, y, w, h)
                if scale:
                    img, fbox = _shrink_fit(img, x, y, scale)
                hh, ww = img.shape
                bf = cmap[img]                                   # BF OBJ indices
                if recol: bf = recol(bf)
                if FRAME_HOOK: FRAME_HOOK(('l2', k, d, f), bf)
                data = bf.reshape(hh // 8, 8, ww // 8, 8).transpose(0, 2, 1, 3).reshape(-1).tobytes()
                cache[key] = (ins.put(struct.pack('<II', 0, len(data)) + data), fbox)
            tptr, fbox = cache[key]
            if scale: attr = (attr & 0x30000000) | 0x80002000        # one 32x32 8bpp piece, keep the flip bits
            box = struct.pack('<bbBB', *fbox)
            ptrs.append(ins.put(struct.pack('<I', 1) + box + box + struct.pack('<II', attr, tptr)))
    return ins.put(struct.pack('<I', len(idx)) + struct.pack('<%dI' % len(ptrs), *ptrs))


def _shrink_fit(img, x, y, s):
    """Shrink a LoG2 frame (colour indices, 0 = clear) by factor s with a majority vote per source block, then cut the
    32x32 window around its content. Returns (32x32 image, (x, y, 32, 32) box relative to the origin)."""
    h, w = img.shape
    oh, ow = max(1, int(round(h * s))), max(1, int(round(w * s)))
    out = np.zeros((oh, ow), np.uint8)
    for j in range(oh):
        for i in range(ow):
            blk = img[int(j / s):max(int(j / s) + 1, int((j + 1) / s)), int(i / s):max(int(i / s) + 1, int((i + 1) / s))]
            v = blk[blk > 0]
            if len(v) * 2 >= blk.size:
                vals, cnt = np.unique(v, return_counts=True); out[j, i] = vals[cnt.argmax()]
    ox, oy = int(round(x * s)), int(round(y * s))              # the shrunk frame's top-left, relative to the origin
    ys, xs = np.nonzero(out)
    if not len(ys): return np.zeros((32, 32), np.uint8), (-16, -24, 32, 32)
    # 32x32 window: bottom-aligned to the feet, centred on the content
    y1 = ys.max() + 1; y0 = max(0, y1 - 32)
    cx = (xs.min() + xs.max() + 1) // 2; x0 = max(0, min(cx - 16, ow - 32)) if ow >= 32 else cx - 16
    win = np.zeros((32, 32), np.uint8)
    for j in range(32):
        for i in range(32):
            sy, sx = y0 + j, x0 + i
            if 0 <= sy < oh and 0 <= sx < ow: win[j, i] = out[sy, sx]
    return win, (ox + x0, oy + y0, 32, 32)


# ---------- Prototype D actors ----------
PROTO_ACTOR_LIST = 0x6A1BBC      # Prototype D (DBZ3_cart27): 280 actors, same record / animation / frame format as retail


def proto_actor(ins, P, i):
    """Copy actor i of Prototype D: the record, its animations, frames and WFZ tile blocks (verbatim: the prototype
    master palette equals retail's, so colour indices carry over). Returns the record (pointers rebased)."""
    from wfz import decompress_stream
    u = lambda o: struct.unpack_from('<I', P, o)[0]
    p = u(PROTO_ACTOR_LIST + 4 * i) - BASE; n = u(p) & 0xFF
    rec = bytearray(P[p:p + 0x54 + 4 * n])
    struct.pack_into('<I', rec, 0x50, 0)                   # no halo table
    for o in range(4, 0x10, 4):                            # any other pointer field would point into the prototype
        assert not (BASE <= struct.unpack_from('<I', rec, o)[0] < BASE + len(P)), 'proto actor %d: pointer at +%x' % (i, o)
    tiles = ins.__dict__.setdefault('_proto_tiles', {}); frames = ins.__dict__.setdefault('_proto_frames', {})
    def tile(tp):
        if tp not in tiles:
            o = tp - BASE; t, size = u(o), u(o + 4)
            end = decompress_stream(P, o + 8, size)[1] if t else o + 8 + size
            tiles[tp] = ins.put(P[o:end])
        return tiles[tp]
    def frame(fp):
        if fp not in frames:
            o = fp - BASE; k = u(o); body = bytearray(P[o:o + 4 + 16 * k])
            for j in range(k): struct.pack_into('<I', body, 4 + 16 * j + 12, tile(u(o + 4 + 16 * j + 12)))
            frames[fp] = ins.put(bytes(body))
        return frames[fp]
    for s in range(n):
        ap = u(p + 0x54 + 4 * s)
        if not ap: continue
        o = ap - BASE; k = u(o)
        ptrs = [frame(u(o + 4 + 4 * j)) if u(o + 4 + 4 * j) else 0 for j in range(4 * k)]
        struct.pack_into('<I', rec, 0x54 + 4 * s, ins.put(struct.pack('<I', k) + struct.pack('<%dI' % len(ptrs), *ptrs)))
    return rec
