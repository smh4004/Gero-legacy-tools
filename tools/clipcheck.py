"""Clipping check for LoG4 builds: every character placement is played in the emulator and inspected.

For each area that log4/areas.json touches, the player is warped in (to each door arrival point, and next to every NPC
spawn) and four frames are captured with the harness ("lshot": all layers / sprites only / backgrounds only / none).
A placement FAILS when
  - hidden:  a character's pixels are covered by the map (full frame shows exactly the background there), or
  - feet:    a character's feet stand off the walkable floor (map +0x38 mask: props and walls are holes), e.g. an NPC
             spawned inside a barrel or a wall - checked twice: on screen, and as a zero-tolerance footprint against the
             mask for every spawn and door arrival point, or
  - arrival: the player does not appear at the door's arrival point, or
  - door:    walking into a warp door's rect in its direction does not lead to its destination (the player starts
             just outside the rect: doors fire when entered, not when the player is already standing inside).
Characters = OAM entries with priority 3 (field sprites), at least 16 px tall (HUD and doors are prio 1/2). Each is paired
with the engine's 16x8 shadow under it when there is one: that is the ground point (hovering characters float above it).
Screen -> map coordinates come from registering the backgrounds-only frame against a render of the map.

How the warps work: a test copy of the ROM gives area 1:1 an extra warp exit (after its real ones) around the spot where
the opening leaves the player (fires on DOWN; dest byte 0 = DOWN key + arrival facing, byte 3 = room 1). The game
is booted once from power-on (START/A presses) into 1:61 (where the opening ends) and saved; each case patches that warp's destination and arrival
point in the ROM file and presses DOWN from the saved state.

usage: python3 tools/clipcheck.py <built rom> [--areas log4/areas.json] [--out dir] [--harness tools/harness]
Exit status 1 when anything fails; the report and annotated frames are in the out dir.
"""
import json, os, struct, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import areas as A, maprender
from mapimport import wfz_data

BASE = 0x08000000
OBJ_SIZE = {(0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64), (1, 0): (16, 8), (1, 1): (32, 8),
            (1, 2): (32, 16), (1, 3): (64, 32), (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64)}
FEET_TOLERANCE = 3          # feet pixels allowed off the floor mask (edge rounding)
HIDDEN_TOLERANCE = 0
BOOT = (['30 -', '4 START', '30 -', '4 A'] * 60) + (['30 -', '4 A'] * 220) + ['200 -']   # title, new game, whole opening


def u32(r, o): return struct.unpack_from('<I', r, o)[0]


def _door_idx():
    p = os.path.join(HERE, '..', 'log4', 'art', 'actor_ids.json')
    if not os.path.exists(p): return set()
    return {v + 9 for k, v in json.load(open(p)).items() if k.startswith('door_')}


DOOR_IDX = _door_idx()


class Rom:
    def __init__(self, data):
        self.r = bytearray(data)
        self.table = u32(self.r, 0x8A58) - BASE
        self.count = A.area_count(self.r)

    def entry(self, w, a): return A.entry(self.r, w, a, self.table, self.count)

    def map_of(self, w, a):
        st = u32(self.r, self.entry(w, a) + 0x2C) - BASE
        return u32(self.r, st) - 4 - BASE

    def spawns(self, w, a):
        """NPC spawn positions, without door panels (tools/doors.py actors sit on the wall by design)."""
        e = self.entry(w, a); n = self.r[e + 4]; lst = u32(self.r, e + 0x14)
        out = []
        for k in range(n if lst else 0):
            o = u32(self.r, lst - BASE + 4 * k) - BASE
            if u32(self.r, o) == 0x08017DA3 and u32(self.r, o + 16) not in DOOR_IDX:
                pos = u32(self.r, o + 8); out.append((pos & 0xFFFF, pos >> 16))
        return out

    def exits(self, w, a):
        e = self.entry(w, a); n = self.r[e + 3]; ex = u32(self.r, e + 0x10)
        out = []
        for k in range(n if ex else 0):
            o = u32(self.r, ex - BASE + 8 * k + 4) - BASE
            fn = u32(self.r, o); rect = struct.unpack_from('<4H', self.r, o + 8)
            if fn == 0x08007675:
                dest, arr = u32(self.r, o + 16), u32(self.r, o + 20)
                key, face = dest & 0xF, (dest >> 4) & 0xF
                out.append(dict(kind='warp', rect=rect, to=((dest >> 8) & 0xFF, (dest >> 16) & 0xFF),
                                arrival=(arr & 0xFFFF, arr >> 16), dir=key, face=face - 1 if face else key,
                                room=dest >> 24))
            else:
                out.append(dict(kind='other', rect=rect))
        return out

    def walk_mask(self, M):
        m = np.frombuffer(wfz_data(self.r, u32(self.r, M + 0x38) - BASE), np.uint8)
        bits = np.unpackbits(m, bitorder='little').reshape(-1, 256)       # rows of 256 tiles, 1 = walkable
        return bits


def sprite_masks(oam, vram, upto):
    """Opaque-pixel masks (160x240) of OAM entries 0..upto (regular sprites, 1D tile mapping)."""
    SZ = {(0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64), (1, 0): (16, 8), (1, 1): (32, 8),
          (1, 2): (32, 16), (1, 3): (64, 32), (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64)}
    out = {}
    for i in range(upto + 1):
        a0, a1, a2 = struct.unpack_from('<HHH', oam, 8 * i)
        if (a0 >> 8) & 3 == 2 or (a0 >> 8) & 1: continue           # hidden or affine
        w, h = SZ.get((a0 >> 14, a1 >> 14), (0, 0))
        if not w: continue
        bpp8 = bool(a0 & 0x2000); t = a2 & 0x3FF
        img = np.zeros((h, w), bool)
        for k in range((w // 8) * (h // 8)):
            base = t * 32 + k * (64 if bpp8 else 32)
            if bpp8: px = np.frombuffer(vram[base:base + 64], np.uint8).reshape(8, 8)
            else:
                b = np.frombuffer(vram[base:base + 32], np.uint8)
                px = np.stack([b & 15, b >> 4], 1).reshape(8, 8)
            ty, tx = divmod(k, w // 8); img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8] = px != 0
        if a1 & 0x1000: img = img[:, ::-1]
        if a1 & 0x2000: img = img[::-1]
        x = a1 & 0x1FF; y = a0 & 0xFF
        x = x - 512 if x >= 240 else x; y = y - 256 if y >= 160 else y
        m = np.zeros((160, 240), bool)
        ys, xs = max(0, y), max(0, x); ye, xe = min(160, y + h), min(240, x + w)
        if ye > ys and xe > xs: m[ys:ye, xs:xe] = img[ys - y:ye - y, xs - x:xe - x]
        out[i] = dict(mask=m, prio=(a2 >> 10) & 3, size=(w, h), bpp8=bpp8)
    return out


def walkin_visibility(out, name, k):
    """Player visibility on one walk-in sample: (pixels covered by another sprite, pixels covered by the map).
    The player = the first 8bpp prio-3 character sprite after the HUD (HUD = prio 1)."""
    oam = open(os.path.join(out, '%s_w%02d_oam.bin' % (name, k)), 'rb').read()
    vram = open(os.path.join(out, '%s_w%02d_vram.bin' % (name, k)), 'rb').read()
    L = lambda t: np.array(Image.open(os.path.join(out, '%s_w%02d_%s.png' % (name, k, t))).convert('RGB')).astype(int)
    full, obj, bg = L('full'), L('obj'), L('bg')
    masks = sprite_masks(oam, vram, 127)
    pl = next((i for i, s in sorted(masks.items()) if s['prio'] == 3 and s['bpp8'] and s['size'] != (16, 8)), None)
    if pl is None: return None
    me = masks[pl]['mask']
    over = np.zeros_like(me)
    for i, s in masks.items():
        if i < pl and s['prio'] != 1 and s['size'] != (16, 8): over |= s['mask']
    covered = int((me & over).sum())
    visible = me & ~over
    visible[124:152] = False      # the area-name banner shown for a few seconds after arriving (UI, not the map)
    # hidden by the map = the full frame shows exactly the background there (blended light layers don't count)
    by_map = int((visible & (np.abs(full - bg).sum(2) == 0) & (np.abs(obj - bg).sum(2) > 0)).sum())
    return covered, by_map


WALKIN_TOLERANCE = 6       # pixels of the player that may be covered while walking into a door
ARRIVAL_STEP = 14          # after a warp the player keeps walking ~14 px in the arrival facing direction (measured)
STEP = {0: (0, 1), 1: (0, -1), 2: (-1, 0), 3: (1, 0)}


def feet_after_arrival(ax, ay, dirn):
    """Arrival point -> where the player's feet (bottom centre of the sprite) settle: origin + (8, 8) + the step."""
    dx, dy = STEP[dirn]
    return ax + 8 + dx * ARRIVAL_STEP, ay + 8 + dy * ARRIVAL_STEP


def door_approach(mask, rect, dirn):
    """A start point for walking into a door the way a player would: arrival origin (sx, sy) on clear floor just outside
    the rect (allowing for the arrival step down), a sideways walk of `steps` frames (~1 px/frame) to line up with the
    walkable opening, then walking in the door's direction. Yields (sx, sy, side_key, steps) candidates, nearest first
    (the mask is only an approximation of the engine's collision, so the caller tries several, like a player would)."""
    x0, y0, x1, y1 = rect
    clear = lambda fx, fy: all(walkable(mask, fx + dx, fy) for dx in (-6, 0, 6))
    def lane(fx, fa, fb):                      # vertical run of feet positions all clear
        return all(clear(fx, fy) for fy in range(min(fa, fb), max(fa, fb) + 1, 4))
    # the walkable opening only needs to reach 8 px into the rect: an animated door (tools/doors.py) makes the
    # doorway floor solid just past where the player stops, and the warp fires when he is stopped there
    inner = y1 - 8 if dirn == 1 else y0 + 8
    opening = [fx for fx in range(x0 + 6, x1 - 5, 2)
               if lane(fx, inner, y1 + 4 if dirn == 1 else y0 - 4)] if dirn in (0, 1) else []
    if dirn in (2, 3):                         # side doors (2 = walk LEFT into it, 3 = RIGHT): line up on a clear row
        inner_x = x1 - 8 if dirn == 2 else x0 + 8      # 8 px into the rect from the side he walks in from
        rows = [fy for fy in range(y0 + 4, y1 - 3, 2)
                if all(walkable(mask, fx, fy) for fx in range(min(inner_x, x1 + 4 if dirn == 2 else x0 - 4),
                                                             max(inner_x, x1 + 4 if dirn == 2 else x0 - 4) + 1, 4))]
        if not rows: return
        fy_in = rows[len(rows) // 2]
        for dx in range(8, 81, 4):
            fx = x1 + dx if dirn == 2 else x0 - dx
            sx, sy = fx - 8, fy_in - 8 - ARRIVAL_STEP       # arrive just above the row, the arrival step brings him onto it
            if not all(walkable(mask, fx, fy) for fy in range(sy + 8, fy_in + 1, 2)): continue
            if not all(walkable(mask, x, fy_in) for x in range(min(fx, inner_x), max(fx, inner_x) + 1, 4)): continue
            yield sx, sy, 'UP', 0
        return
    if not opening: return
    fx_in = opening[len(opening) // 2]
    for dy in range(8, 81, 4):
        for dx in sorted(range(-48, 49, 4), key=abs):
            fx = fx_in + dx
            fy = y1 + dy if dirn == 1 else y0 - dy
            sx, sy = fx - 8, fy - 8 - ARRIVAL_STEP          # arrival walks ~14 px down before we take control
            if not lane(fx, sy + 8, fy) or not clear(fx, fy): continue
            if not all(clear(x, fy) for x in range(min(fx, fx_in), max(fx, fx_in) + 1, 4)): continue
            if not lane(fx_in, fy, inner): continue
            side = 'LEFT' if fx > fx_in else 'RIGHT'
            yield sx, sy, side, abs(fx - fx_in)


def neutralize_story_triggers(T, enemies=True):
    """In the test ROM, exits of class 0x0800742D (step-list events) whose param is a bytecode condition are story
    triggers (e.g. the chapter 5 opening at West City's arrival point): give them a condition that is never true, so
    placement checks see the area itself. Door-animation triggers have param 0 and stay. Conditional warp doors (e.g. the
    chapter 3 escape corridor) are made unconditional, so every door gets walked."""
    never = len(T); T += b'\x00\x00\x11\x00'                      # push 0; end
    tab = u32(T, 0x8A58) - BASE; cnt = A.area_count(T)
    for k in range(cnt):
        e = tab + 56 * k
        if not (0 <= e < len(T) - 56): break
        # field enemies (0x0800FD55 spawn records) never spawn in the test ROM: they rush the player and spoil the arrival
        # and door checks (their positions are checked against the floor mask by the area generators instead)
        no, lp = T[e + 4], u32(T, e + 0x14)
        if enemies and no and BASE <= lp < BASE + len(T):
            for i in range(no):
                o = u32(T, lp - BASE + 4 * i)
                if BASE <= o < BASE + len(T) and u32(T, o - BASE) == 0x0800FD55:
                    struct.pack_into('<I', T, o - BASE + 4, BASE + never)
        ne, xp = T[e + 3], u32(T, e + 0x10)
        if not ne or not (BASE <= xp < BASE + len(T)): continue
        for i in range(ne):
            prm, obj = struct.unpack_from('<II', T, xp - BASE + 8 * i)
            if BASE <= prm < BASE + len(T) and BASE <= obj < BASE + len(T) and u32(T, obj - BASE) == 0x0800742D:
                struct.pack_into('<I', T, xp - BASE + 8 * i, BASE + never)
            elif BASE <= prm < BASE + len(T) and BASE <= obj < BASE + len(T) and u32(T, obj - BASE) == 0x08007675:
                struct.pack_into('<I', T, xp - BASE + 8 * i, 0)     # conditional warp door: always open, so it is walked



def make_test_rom(R, keep_story=False, keep_enemies=False):
    """Copy of the ROM where 1:61 (the main lab the opening ends in) gets an extra warp exit (after its real ones) where the player stands after the opening,
    firing on DOWN.
    Returns (bytearray, hook offset); the hook object's dest is at +16 and its arrival point at +20."""
    T = bytearray(R.r)
    if not keep_story: neutralize_story_triggers(T, enemies=not keep_enemies)
    hook = (len(T) + 0xFF) & ~0xFF
    T += bytes(hook + 0x20 - len(T))
    # the hook covers only where the opening leaves the player (112,200): overlapping exits hide each other
    struct.pack_into('<IIHHHHII', T, hook, 0x08007675, 0x0800776D, 96, 184, 136, 224, 0, 0)
    e11 = R.entry(1, 61); n11 = T[e11 + 3]; ex11 = u32(T, e11 + 0x10)
    lst = bytes(T[ex11 - BASE:ex11 - BASE + 8 * n11]) if ex11 else b''
    T += bytes(8 * (n11 + 1) + 0x10)
    T[hook + 0x20:hook + 0x20 + 8 * n11] = lst
    struct.pack_into('<II', T, hook + 0x20 + 8 * n11, 0, BASE + hook)
    T[e11 + 3] = n11 + 1; struct.pack_into('<I', T, e11 + 0x10, BASE + hook + 0x20)
    return T, hook


def walkable(mask, x, y):
    tx, ty = int(x) // 8, int(y) // 8
    return 0 <= ty < mask.shape[0] and 0 <= tx < 256 and mask[ty, tx] == 1


def register(bg, render):
    """Camera (x, y) such that render[y:y+160, x:x+240] matches the backgrounds-only frame (gradient SSD via FFT)."""
    from scipy.signal import fftconvolve
    g = lambda a: np.abs(np.diff(a, axis=1))[:-1, :] + np.abs(np.diff(a, axis=0))[:, :-1]
    bg = bg[16:120]                       # skip the HUD rows and the area-name bar shown on arrival
    s = g(bg.mean(2)); m = g(render.mean(2))
    if m.shape[0] < s.shape[0] or m.shape[1] < s.shape[1]: return None, 1e9
    k = s[::-1, ::-1]
    cross = fftconvolve(m, k, mode='valid')
    m2 = fftconvolve(m * m, np.ones_like(s), mode='valid')
    ssd = m2 - 2 * cross + (s * s).sum()
    y, x = np.unravel_index(np.argmin(ssd), ssd.shape)
    return (int(x), int(y) - 16), float(ssd[y, x] / max(1e-9, np.median(ssd)))      # ratio: ~0 = clean match, ~1 = none


def run(harness, rom_path, script, outdir):
    p = os.path.join(outdir, 'script.txt'); open(p, 'w').write('\n'.join(script) + '\n')
    subprocess.run([harness, rom_path, p, outdir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def main():
    args = sys.argv[1:]
    rom_path = args[0]
    opt = lambda k, d: args[args.index(k) + 1] if k in args else d
    cfg = json.load(open(opt('--areas', os.path.join(HERE, '..', 'log4', 'areas.json'))))
    out = opt('--out', os.path.join(os.path.dirname(os.path.abspath(rom_path)), 'clipcheck'))
    harness = opt('--harness', os.path.join(HERE, 'harness'))
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith(('.png', '.bin', '.ss', '.gba', '.txt')): os.remove(os.path.join(out, f))
    R = Rom(open(rom_path, 'rb').read())
    # areas where LoG4 places something (spawns, doors, maps, object-list edits) and every new area; an entry that only
    # sets a palette or a name leaves Buu's Fury's own placements alone, so there is nothing of ours to check
    PLACES = ('spawn_ids', 'spawn_pos', 'doors', 'map_log2', 'keep_objects', 'spawns', 'map_from', 'spawns_append')
    targets = [(a['world'], a['area']) for a in cfg.get('areas', []) if any(k in a for k in PLACES)] + \
              [(a['world'], a['area']) for a in cfg.get('new_areas', [])]

    def our_spawns(w, a):
        """Spawns to check: all of them in new areas and areas whose object list we rebuilt (keep_objects /
        spawn_ids); in a BF area we only add to (spawns_append), just ours - BF's own townsfolk wander."""
        sp = R.spawns(w, a)
        # spawns marked "no_check" (sparkle effects such as the time machine's arrival flash have too few opaque pixels
        # to be found as a character) are left out
        skip = {(s_['x'], s_['y']) for x in cfg.get('areas', []) + cfg.get('new_areas', []) if (x['world'], x['area']) == (w, a)
                for s_ in x.get('spawns', []) if s_.get('no_check')}
        sp = [p_ for p_ in sp if p_ not in skip]
        ent = next((x for x in cfg.get('areas', []) if (x['world'], x['area']) == (w, a)), None)
        if ent is None or 'keep_objects' in ent or 'spawn_ids' in ent: return sp
        mine = {tuple(v) for v in ent.get('spawn_pos', {}).values()} | {(s_['x'], s_['y']) for s_ in ent.get('spawns_append', [])}
        return [p_ for p_ in sp if p_ in mine]

    T, hook = make_test_rom(R)
    test_rom = os.path.join(out, 'test.gba'); open(test_rom, 'wb').write(T)
    run(harness, test_rom, BOOT + ['save field', 'dump area 3001980 4'], out)
    p = struct.unpack('<I', open(os.path.join(out, 'area.bin'), 'rb').read())[0] - BASE
    if not (0 <= p < len(T)) or (T[p], T[p + 1]) != (1, 61):
        print('clipcheck: boot did not reach area 1:61 (the opening ends there)', (T[p], T[p + 1]) if 0 <= p < len(T) else hex(p)); return 1

    G = maprender.Game(test_rom, BASE, 0x701B0)
    renders, masks = {}, {}
    failures, report = [], []

    def case(w, a, ax, ay, why, dirn=0):
        name = 'c%02d_%d_%d_%d_%d' % (len(report), w, a, ax, ay)
        struct.pack_into('<II', T, hook + 16, ((dirn + 1) << 4) | (w << 8) | (a << 16) | (1 << 24), (ay << 16) | ax)
        open(test_rom, 'wb').write(T)
        run(harness, test_rom, ['load field', '3 DOWN', '240 -', 'lshot %s_full 1f' % name, 'lshot %s_obj 10' % name,
                                'lshot %s_bg f' % name, 'lshot %s_none 0' % name, 'dump %s_oam 7000000 400' % name,
                                'dump %s_area 3001980 4' % name], out)
        L = lambda k: np.array(Image.open(os.path.join(out, '%s_%s.png' % (name, k))).convert('RGB')).astype(int)
        full, obj, bg, none = L('full'), L('obj'), L('bg'), L('none')
        res = dict(case=name, area='%d:%d' % (w, a), arrival=(ax, ay), why=why, problems=[])
        pa = struct.unpack('<I', open(os.path.join(out, name + '_area.bin'), 'rb').read())[0] - BASE
        if not (0 <= pa < len(T)) or (T[pa], T[pa + 1]) != (w, a):
            res['problems'].append('warp did not reach the area'); report.append(res); return res
        M = R.map_of(w, a)
        if M not in renders:
            im, _ = G.render(M); renders[M] = np.array(im.convert('RGB')).astype(int); masks[M] = R.walk_mask(M)
        cam, err = register(bg, renders[M])
        res['camera'] = cam
        res['reg_err'] = round(err, 3)
        night = any(x.get('night') for x in cfg.get('new_areas', []) if (x['world'], x['area']) == (w, a))
        if cam is None or err > (0.42 if night else 0.35):     # moonlit palettes flatten the gradients a little
            res['problems'].append('could not register the screen against the map (err %.2f)' % err)
            report.append(res); return res
        spr = np.abs(obj - none).sum(2) > 0
        hidden = spr & (np.abs(full - bg).sum(2) == 0) & (np.abs(obj - bg).sum(2) > 0)
        oam = open(os.path.join(out, name + '_oam.bin'), 'rb').read()
        chars, shadows, objs = [], [], []
        for i in range(128):
            a0, a1, a2 = struct.unpack_from('<HHH', oam, 8 * i)
            if (a0 >> 8) & 3 == 2 or (a2 >> 10) & 3 != 3: continue
            ow, oh = OBJ_SIZE[(a0 >> 14, a1 >> 14)]
            x = a1 & 0x1FF; y = a0 & 0xFF
            x = x - 512 if x >= 256 else x; y = y - 256 if y >= 160 else y
            (shadows if (ow, oh) == (16, 8) else objs).append((i, x, y, ow, oh))
        shadow_px = np.zeros_like(spr)                   # semi-transparent shadows can blend to the floor colour
        for _, sx_, sy_, _, _ in shadows: shadow_px[max(0, sy_):max(0, sy_ + 8), max(0, sx_):max(0, sx_ + 16)] = True
        hidden &= ~shadow_px
        for i, x, y, ow, oh in objs:
            if oh < 16: continue
            box = np.zeros_like(spr); box[max(0, y):max(0, y + oh), max(0, x):max(0, x + ow)] = True
            px = spr & box
            if not px.any(): continue
            ys, xs = np.nonzero(px)
            bottom = ys.max()
            # the engine draws a 16x8 shadow under every character; a hovering one (the combat drone) floats above
            # it, so the shadow is its ground point. Pair the shadow centred under the sprite, at or below its bottom.
            cx = x + ow // 2
            tol = 6 if ow <= 16 else ow // 2 - 2              # a wide frame (someone lying down) is centred on its origin
            sh = [t for t in shadows if abs(t[1] + 8 - cx) <= tol and -12 <= t[2] - (y + oh) <= 48]
            if sh:
                _, sx_, sy_, _, _ = min(sh, key=lambda t: abs(t[2] - (y + oh)))
                sbox = np.zeros_like(spr); sbox[max(0, sy_):max(0, sy_ + 8), max(0, sx_):max(0, sx_ + 16)] = True
                feet = [(xx, yy) for yy, xx in zip(*np.nonzero(spr & sbox))] or [(cx, sy_ + 4)]
                gx, gy = sx_ + 8, sy_ + 4 + 4                # shadow centre + 4 = feet (measured on walkers)
            else:
                feet = [(xx, yy) for yy, xx in zip(ys, xs) if yy >= bottom - 1]
                gx, gy = int(np.mean([f[0] for f in feet])), int(bottom)
            off = [(xx, yy) for xx, yy in feet if not walkable(masks[M], xx + cam[0], yy + cam[1])]
            wx, wy = gx + cam[0], gy + cam[1]
            c = dict(oam=i, world_feet=(wx, wy), hidden=int((hidden & box).sum()), feet_off=len(off),
                     box=(x, y, ow, oh), touches_edge=bool(bottom >= 159), shadow=bool(sh))
            chars.append(c)
            # BF field enemies roam and walk behind props like any enemy in BF: only characters standing where an NPC
            # was placed, or where the player arrives, are judged (enemies are not placements)
            pfx, pfy = feet_after_arrival(ax, ay, dirn)
            placed = [(sx + 7, sy + 8) for sx, sy in R.spawns(w, a)] + [(pfx, pfy)]
            if not any(abs(wx - px) <= 20 and abs(wy - py) <= 20 for px, py in placed): continue
            shade = [r for x in cfg.get('areas', []) + cfg.get('new_areas', []) if (x['world'], x['area']) == (w, a)
                     for r in x.get('shade_ok', [])]     # areas.json "shade_ok": rects under an opaque shading layer
            if c['hidden'] > HIDDEN_TOLERANCE and not any(r[0] <= wx <= r[2] and r[1] <= wy <= r[3] for r in shade):
                res['problems'].append('character at map (%d,%d): %d pixels hidden by the map' % (wx, wy, c['hidden']))
            if c['feet_off'] > FEET_TOLERANCE and not c['touches_edge']:
                res['problems'].append('character at map (%d,%d): feet off the floor (%d px) - inside a prop or wall'
                                       % (wx, wy, c['feet_off']))
        res['characters'] = chars
        fx, fy = feet_after_arrival(ax, ay, dirn)
        if not why.startswith('arrival') and chars:          # a viewing spot: the player's own placement is incidental
            me = min(chars, key=lambda c: abs(c['world_feet'][0] - fx) + abs(c['world_feet'][1] - fy))
            me['player'] = True
            tag = 'character at map (%d,%d)' % tuple(me['world_feet'])
            res['problems'] = [p for p in res['problems'] if not p.startswith(tag)]
        periodic = any(x.get('clipcheck_periodic') for x in cfg.get('areas', []) + cfg.get('new_areas', [])
                       if (x['world'], x['area']) == (w, a))       # repeating map: camera registration is ambiguous
        if why.startswith('arrival') and not periodic and not any(abs(c['world_feet'][0] - fx) <= 10 and abs(c['world_feet'][1] - fy) <= 10
                                                 for c in chars):
            res['problems'].append('player not found at the arrival point (%d,%d)' % (ax, ay))
        if res['problems']:
            viz = full.astype(np.uint8).copy(); viz[hidden] = [255, 0, 255]
            im = Image.fromarray(viz).resize((480, 320), Image.NEAREST); d = ImageDraw.Draw(im)
            for c in chars:
                x, y, ow, oh = c['box']; col = (255, 0, 0) if (c['hidden'] or c['feet_off'] > FEET_TOLERANCE) else (0, 255, 0)
                d.rectangle([2 * x, 2 * y, 2 * (x + ow), 2 * (y + oh)], outline=col)
            im.save(os.path.join(out, 'FAIL_' + name + '.png'))
        report.append(res); return res

    # ---- footprints straight from the floor mask (no tolerance): every tile under a character's feet must be floor.
    # Spawn origin (x, y): sprite x-1..x+14, feet at y+2..y+8 (measured). Arrival: feet after the arrival step.
    for (w, a) in targets:
        mask = R.walk_mask(R.map_of(w, a))
        feet = [('NPC spawned at (%d,%d)' % (x, y), x + 7, y + 8) for x, y in our_spawns(w, a)]
        feet += [('arrival point (%d,%d) of a door from %d:%d' % (ex['arrival'] + (sw, sa)),)
                 + feet_after_arrival(*ex['arrival'], ex['face'])
                 for (sw, sa) in targets for ex in R.exits(sw, sa) if ex['kind'] == 'warp' and ex['to'] == (w, a)]
        # an arrival right on top of an NPC traps the player (NPCs are solid): keep 24 px clear
        for x, y in our_spawns(w, a):
            for (sw, sa) in targets:
                for ex in R.exits(sw, sa):
                    if ex['kind'] == 'warp' and ex['to'] == (w, a):
                        fx2, fy2 = feet_after_arrival(*ex['arrival'], ex['face'])
                        if abs(fx2 - (x + 7)) < 20 and abs(fy2 - (y + 8)) < 16:
                            report.append(dict(case='footprint', area='%d:%d' % (w, a), why='arrival %s' % (ex['arrival'],),
                                               problems=['arrival point %s from %d:%d lands on the NPC spawned at (%d,%d)'
                                                         % (ex['arrival'], sw, sa, x, y)]))
        for what, fx, fy in feet:
            bad = sorted({(px // 8 * 8, py // 8 * 8) for px in range(fx - 7, fx + 8) for py in range(fy - 6, fy + 1)
                          if not walkable(mask, px, py)})
            if bad:
                report.append(dict(case='footprint', area='%d:%d' % (w, a), why=what, problems=[
                    '%s: feet over non-floor tiles %s (prop or wall)' % (what, ', '.join('(%d,%d)' % t for t in bad[:4]))]))

    seen = {}
    for (w, a) in targets:
        M = R.map_of(w, a)
        mask = R.walk_mask(M)
        doors = R.exits(w, a)
        arrivals = sorted({ex['arrival'] + (ex['face'],) for (sw, sa) in targets for ex in R.exits(sw, sa)
                           if ex['kind'] == 'warp' and ex['to'] == (w, a)})
        for (ax, ay, dn) in arrivals:
            res = case(w, a, ax, ay, 'arrival point of a door', dn)
            for c in res.get('characters', []): seen.setdefault((w, a), []).append(c['world_feet'])
        for (sx, sy) in our_spawns(w, a):
            fx, fy = sx + 7, sy + 8                          # spawn origin -> feet (measured: sprite bottom = y + 8)
            if any(abs(fx - x) <= 12 and abs(fy - y) <= 12 for x, y in seen.get((w, a), [])): continue
            spot = None                                      # walkable point near the NPC, clear of doors and NPCs
            for r in (28, 36, 44, 56, 72, 96):
                for ang in np.linspace(0, 2 * np.pi, 24, endpoint=False):
                    x, y = int(sx + r * np.cos(ang)), int(sy + r * np.sin(ang))
                    fx2, fy2 = feet_after_arrival(x, y, 0)
                    if all(walkable(mask, fx2 + dx, fy2 - dy) for dx in (-8, 0, 8) for dy in range(0, ARRIVAL_STEP + 9, 4)) and \
                       not any(d['rect'][0] - 8 <= x <= d['rect'][2] + 8 and d['rect'][1] - 8 <= y <= d['rect'][3] + 8
                               for d in doors) and \
                       all(abs(x - px) + abs(y - py) > 20 for px, py in R.spawns(w, a)):
                        spot = (x, y); break
                if spot: break
            if spot is None:
                report.append(dict(case='-', area='%d:%d' % (w, a), why='NPC at (%d,%d)' % (sx, sy),
                                   problems=['no free floor near this NPC to look from - is it walled in?']))
                continue
            res = case(w, a, spot[0], spot[1], 'view of NPC spawned at (%d,%d)' % (sx, sy))
            for c in res.get('characters', []): seen.setdefault((w, a), []).append(c['world_feet'])
            if not any(abs(fx - x) <= 12 and abs(fy - y) <= 12 for x, y in [c['world_feet'] for c in res.get('characters', [])]):
                res['problems'].append('NPC spawned at (%d,%d) not found on screen' % (sx, sy))

    # ---- every warp door must work: approach from outside its rect, walk its direction, expect its destination
    for (w, a) in targets:
        exs = R.exits(w, a)
        for k, ex in enumerate(exs):
            if ex['kind'] != 'warp': continue
            # complementary 'when' doors on one doorway (e.g. 1:62's back door: 1:61 before chapter 2, 1:67 during
            # it): the test ROM opens both and the first hides the second, so only the first is walked
            if any(e2['kind'] == 'warp' and e2['rect'] == ex['rect'] for e2 in exs[:k]): continue
            x0, y0, x1, y1 = ex['rect']                # start outside the rect and walk in (doors fire on entry)
            name = 'door_%d_%d_%d' % (w, a, k)
            key = ('DOWN', 'UP', 'LEFT', 'RIGHT')[ex['dir']]
            starts = [st for st in door_approach(R.walk_mask(R.map_of(w, a)), ex['rect'], ex['dir']) if st[0] >= 0 and st[1] >= 0]
            # try up to 6 approaches at different distances (best-aligned at each), stop at the first that gets through
            by_dist = {}
            side_door = ex['dir'] in (2, 3)
            for st in starts: by_dist.setdefault(st[0] if side_door else st[1], st)
            ref = ((ex['rect'][2] if ex['dir'] == 2 else ex['rect'][0]) if side_door else
                   (ex['rect'][1] if ex['dir'] == 0 else ex['rect'][3]))
            tries = [by_dist[k] for k in sorted(by_dist, key=lambda v: abs(v + (8 if side_door else 0) - ref))][::2][:6]
            res = dict(case=name, area='%d:%d' % (w, a), why='door %d -> %d:%d' % ((k,) + ex['to']), problems=[])
            if not tries:
                res['problems'].append('no walkable approach to the door rect %s' % (ex['rect'],))
            got = None
            for t, (sx, sy, side, steps) in enumerate(tries):
                struct.pack_into('<II', T, hook + 16, (1 << 4) | (w << 8) | (a << 16) | (1 << 24), (sy << 16) | sx)
                open(test_rom, 'wb').write(T)
                walk = ['%d %s' % (steps, side)] if steps else []
                # hold the key only for the walk in (+ margin): holding on through the warp can walk the player
                # straight into the arrival room's own door and back
                feet_y = sy + 8 + ARRIVAL_STEP
                hold = (abs(sx + 8 - ref) + 16 if side_door else
                        abs(feet_y - (ex['rect'][1] if ex['dir'] == 1 else ex['rect'][3])) + 16)
                # read the current area several times: an arrival can start an event (a chapter card is its own
                # scene), so the destination may only show for a while
                reads = []
                for q in range(6): reads += ['40 -', 'dump %s_area%d 3001980 4' % (name, q)]
                run(harness, test_rom, ['load field', '3 DOWN', '200 -'] + walk + ['%d %s' % (hold, key)] + reads +
                                       ['shot %s_%d' % (name, t)], out)
                seen = []
                for q in range(6):
                    pa = struct.unpack('<I', open(os.path.join(out, '%s_area%d.bin' % (name, q)), 'rb').read())[0] - BASE
                    seen.append((T[pa], T[pa + 1]) if 0 <= pa < len(T) else None)
                got = ex['to'] if ex['to'] in seen else seen[-1]
                if got == ex['to']:
                    res['approach'] = (sx, sy, side, steps)
                    # replay it and check the player stays fully visible on every 3rd frame of the walk in (a door
                    # drawn over him, or map tiles over the doorway, fail here)
                    samp = []
                    for j in range(0, hold, 3):
                        samp += ['3 %s' % key, 'pshot %s_w%02d' % (name, j // 3)]     # full + sprites of ONE frame
                    run(harness, test_rom, ['load field', '3 DOWN', '200 -'] + walk + samp, out)
                    worst = (0, 0); pal0 = None
                    for j in range(0, hold, 3):
                        # the warp's fade-out runs while he keeps walking in, so sprite cover counts on every sample
                        # (it is computed from tile data, fade-proof); map cover only while the palette is at least
                        # half bright (deep in a fade everything is near black and compares equal)
                        pal = np.frombuffer(open(os.path.join(out, '%s_w%02d_pal.bin' % (name, j // 3)), 'rb').read(), '<u2')
                        lum = int((pal & 31).sum() + ((pal >> 5) & 31).sum() + ((pal >> 10) & 31).sum())
                        pal0 = lum if pal0 is None else pal0
                        v = walkin_visibility(out, name, j // 3)
                        if v: worst = (max(worst[0], v[0]), max(worst[1], v[1] if lum >= 0.5 * pal0 else 0))
                    res['walkin'] = worst
                    # areas.json door "cover_ok": the opening runs behind scenery on purpose (e.g. a bush at a map edge)
                    if any(tuple(d.get('rect', ())) == tuple(ex['rect']) and d.get('cover_ok')
                           for x in cfg.get('areas', []) + cfg.get('new_areas', []) if (x['world'], x['area']) == (w, a)
                           for d in x.get('doors', []) + x.get('doors_append', [])):
                        worst = (0, 0)
                    if worst[0] > WALKIN_TOLERANCE:
                        res['problems'].append('walking into the door, %d of the player\'s pixels are covered by another '
                                               'sprite (a door or prop drawn over him)' % worst[0])
                    if worst[1] > WALKIN_TOLERANCE:
                        res['problems'].append('walking into the door, %d of the player\'s pixels are covered by the map'
                                               % worst[1])
                    break
            if tries and got != ex['to']:
                res['problems'].append('walking %s into the door rect %s from %d approaches never reaches %d:%d'
                                       % (key.lower(), ex['rect'], len(tries), *ex['to']))
            report.append(res)

    bad = [r for r in report if r['problems']]
    lines = ['clipcheck: %d placements checked in %d areas, %d failing' % (len(report), len(targets), len(bad))]
    for r in bad:
        lines.append('  FAIL %s area %s (%s, player at %s):' % (r['case'], r['area'], r['why'], r.get('arrival')))
        lines += ['       - ' + p for p in r['problems']]
    open(os.path.join(out, 'report.txt'), 'w').write('\n'.join(lines) + '\n')
    json.dump(report, open(os.path.join(out, 'report.json'), 'w'), indent=1, default=str)
    print('\n'.join(lines))
    os.remove(test_rom)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
