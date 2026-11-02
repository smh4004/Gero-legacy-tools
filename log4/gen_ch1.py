"""Chapter 1 'Red Ribbon Science' proving ground: writes the range areas into areas.json (replacing earlier versions).
Positions are snapped to walkable floor of the actual maps (built ROM needed for LoG2-imported maps: log4/out/LoG4.gba).
usage: python3 log4/gen_ch1.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import clipcheck as C, scenes
import numpy as np

BF = C.Rom(open(os.path.join(HERE, '..', 'bf.gba'), 'rb').read())
OUT = C.Rom(open(os.path.join(HERE, 'out', 'LoG4_shoot.gba'), 'rb').read())


def hexcond(*parts):
    """('set'|'clear', flag) ... ANDed -> 'hex ..' condition."""
    b = b''
    for i, (k, f) in enumerate(parts):
        b += b'\x01' + scenes.enc_varint(f) + bytes([0x02, 27 if k == 'set' else 28])
        if i: b += b'\x04'
    return 'hex ' + (b + b'\x11').hex(' ')


def notcond(*parts):
    b = bytes.fromhex(hexcond(*parts)[4:])[:-1] + b'\x00\x00\x0b\x11'
    return 'hex ' + b.hex(' ')


# area -> (source, map mask)
SRC = {90: ('bf', [20, 6]), 91: ('bf', [20, 2]), 92: ('bf', [20, 7]), 93: ('bf', [20, 5]), 94: ('bf', [20, 4]),
       84: ('l2', '0x66750c'), 85: ('l2', '0x66ac9c')}
SIZE = {90: (400, 240), 91: (320, 480), 92: (480, 480), 93: (480, 480), 94: (480, 400), 84: (304, 424), 85: (280, 230)}


def mask(a):
    k, s = SRC[a]
    return BF.walk_mask(BF.map_of(*s)) if k == 'bf' else OUT.walk_mask(OUT.map_of(1, a))


STEP = {'down': (0, 1), 'up': (0, -1), 'left': (-1, 0), 'right': (1, 0), None: (0, 0)}


def ok(m, x, y, r=12, face=None):
    """(x, y) = spawn origin; NPC feet at (x + 7, y + 8); an arrival's feet settle 14 px further in its facing
    (tools/clipcheck.py feet_after_arrival). Floor all around the feet, along the arrival step too."""
    dx, dy = STEP[face]
    for k in (0, 7, 14) if face else (0,):
        fx, fy = x + 8 + dx * k, y + 8 + dy * k
        if not all(C.walkable(m, fx + ex, fy + ey) for ex in range(-r, r + 1, 4) for ey in range(-r, 5, 4)): return False
    return True


def snap(a, x, y, r=12, face=None):
    m = mask(a)
    if ok(m, x, y, r, face): return [x, y]
    for d in range(4, 160, 4):
        for dx in range(-d, d + 1, 4):
            for dy in (-d, d):
                for X, Y in ((x + dx, y + dy), (x + dy, y + dx)):
                    if ok(m, X, Y, r, face): return [X, Y]
    raise ValueError('no floor near %d:%d (%d,%d)' % (1, a, x, y))


def door(side, a, lo, hi, to, arr, face, note):
    W, H = SIZE[a]
    rect = {'up': [lo, 0, hi, 48], 'down': [lo, H - 28, hi, H], 'left': [0, lo, 12, hi], 'right': [W - 28, lo, W, hi]}[side]
    return {'rect': rect, 'warp': [1, to, arr[0], arr[1]], 'dir': side, 'face': face, '_note': note}


def arrival(a, side, lo, hi):
    """Where a player arriving through this opening is placed: just inside it, facing into the map, on floor (arrivals
    under a top exit stay below its solid rows)."""
    W, H = SIZE[a]; mid = (lo + hi) // 2 - 8; face = FACE_IN[side]
    if (a, side) == (90, 'down'): return snap(a, 176, 140, 14, face)
    p = {'up': (mid, 64), 'down': (mid, H - 72), 'left': (24, mid), 'right': (W - 56, mid)}[side]
    m = mask(a)
    if side == 'up':
        for y in range(64, 176, 4):
            for dx in sorted(range(-40, 41, 4), key=abs):
                if ok(m, mid + dx, y, 14, face): return [mid + dx, y]
    return snap(a, *p, 14, face)


FACE_IN = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}
OPEN = {  # (area, side): (lo, hi)
    (90, 'up'): (96, 128), (90, 'right'): (152, 192),
    (91, 'down'): (56, 96), (91, 'up'): (48, 256), (90, 'down'): (88, 168),
    (92, 'down'): (168, 208), (85, 'down'): (112, 176),
    (94, 'left'): (288, 320), (94, 'up'): (352, 424),
    (93, 'down'): (176, 248), (93, 'left'): (216, 248), (84, 'right'): (272, 376)}
side_of = lambda k: k.split('_')[0]
ARR = {k: arrival(k[0], side_of(k[1]), *v) for k, v in OPEN.items()}
LINKS = [((90, 'up'), (91, 'down')), ((90, 'right'), (94, 'left')), ((91, 'up'), (92, 'down')),
         ((90, 'down'), (85, 'down')), ((94, 'up'), (93, 'down'))]
NAMES = {90: 'Range Gate', 91: 'Canyon Road', 92: 'Target Field', 93: 'Bone Flats', 94: 'The Pit', 84: 'Live-Fire Arena',
         85: 'Fuel Depot'}
doors = {a: [] for a in SRC}
for p, q in LINKS:
    for (a, s), (b, t) in ((p, q), (q, p)):
        lo, hi = OPEN[(a, s)]
        doors[a].append(door(side_of(s), a, lo, hi, b, ARR[(b, t)], FACE_IN[side_of(t)], '%s -> %s' % (NAMES[a], NAMES[b])))
# the arena gate: Bone Flats' west exit, open once all three sites report (exits are read at area load)
ALL3 = [('set', 353), ('set', 354), ('set', 355)]
lo, hi = OPEN[(93, 'left')]
d = door('left', 93, lo, hi, 84, ARR[(84, 'right')], 'left', 'Bone Flats -> Live-Fire Arena (all three target sites recorded)')
d['when'] = hexcond(*ALL3); doors[93].append(d)
doors[93].append({'rect': [0, lo - 8, 28, hi + 8], 'examine': 'left', 'event': 'arena_locked', 'when': notcond(*ALL3),
                  '_note': 'the arena gate before all three sites report'})
doors[84].append(door('right', 84, *OPEN[(84, 'right')], 93, ARR[(93, 'left')], 'right', 'Live-Fire Arena -> Bone Flats'))


def ev(a, x0, y0, x1, y1, event, examine=None, when=None, note='', walk=False):
    d = {'rect': [x0, y0, x1, y1], 'event': event, '_note': note}
    if examine: d['examine'] = examine
    if walk: d['fn2'] = '0x080077DF'
    if when: d['when'] = when
    doors[a].append(d)


GATE_ARR = snap(90, 150, 140, 14)
gx, gy = GATE_ARR
ev(90, gx - 24, gy - 24, gx + 40, gy + 40, 'ch1_brief', walk=True, when=hexcond(('clear', 352)), note='briefing on the first arrival (flag 352 clear)')
# three target sites (A press), supply crates
ev(85, 60, 168, 100, 198, 'crate_depot', examine='up', note='fuel drums with a supply box (items, flag 372)')
ev(94, 40, 280, 80, 330, 'crate_pit', examine='left', note='a dented supply drum (items, flag 373)')
ra = ARR[(84, 'right')]
ev(84, ra[0] - 30, ra[1] - 30, ra[0] + 40, ra[1] + 40, 'ch1_arena', walk=True, when=hexcond(('clear', 357)), note='arena arrival (flag 357 clear)')

E = lambda a, t, x, y, **k: dict(type=t, x=snap(a, x, y, 14)[0], y=snap(a, x, y, 14)[1], **k)
GUN, TUR, MECH, MERC, BOMB, TANK = 44, 64, 72, 75, 8, 127
enemies = {
    90: [],
    91: [E(91, GUN, 130, 300), E(91, GUN, 170, 200)],
    92: [E(92, TUR, 380, 140), E(92, TUR, 110, 140), E(92, MERC, 250, 190)],
    93: [E(93, BOMB, 120, 300), E(93, GUN, 300, 120), E(93, GUN, 150, 150)],
    94: [E(94, BOMB, 230, 260), E(94, GUN, 280, 240)],
    85: [E(85, TUR, 236, 132), E(85, MERC, 90, 186)],
    84: [dict(E(84, TANK, 120, 324), character=259, condition=0x20000 + 356, _note='the heavy tank (row 127): until destroyed (356)')],
}
# the three target sites: powered-down sensor drones (visible, A to read; drone_l2 = LoG2 drone NPC)
SITES = {92: ('site_a', 252, 250), 85: ('site_b', 200, 178), 93: ('site_c', 236, 170)}
spawns = {a: [{'actor': 'drone_l2', 'x': snap(a, x, y)[0], 'y': snap(a, x, y)[1], 'face': 'down', 'talk': t,
               '_note': 'target site sensor drone'}] for a, (t, x, y) in SITES.items()}
spawns[90] = [{'actor_id': 25, 'x': snap(90, 210, 120)[0], 'y': snap(90, 210, 120)[1], 'face': 'down', 'talk': 'range_sergeant',
                '_note': 'range sergeant (BF Bomber actor 25 = green-helmet soldier)'}]
TPL = {'bf': [20, 7], 'l2': [20, 7]}
cfg = json.load(open(os.path.join(HERE, 'areas.json')))
cfg['new_areas'] = [a for a in cfg['new_areas'] if not (a['world'] == 1 and a['area'] in SRC or (a['world'] == 1 and a['area'] in (86, 87, 88)))]
for a, (k, s) in SRC.items():
    ent = {'world': 1, 'area': a, 'template': TPL[k], 'name': 526, 'palette_act': 'act1',
           '_note': 'Chapter 1 proving ground: %s (generated by log4/gen_ch1.py)' % NAMES[a], 'doors': doors[a]}
    if k == 'bf': ent['map_from'] = s
    else: ent['map_log2'] = s
    if enemies.get(a): ent['enemies'] = enemies[a]
    if a in spawns: ent['spawns'] = spawns[a]
    if a == 90: ent['exits_from'] = [[20, 6, 1]]          # BF's Capsule save pad
    if a == 94: ent['keep_regions'] = []                   # drop BF's level-gate graphics (the Pit's level-140 gates)
    # top exits: the top rows of the opening are made solid so the player stops below the HUD and the warp fires
    sol = [[d['rect'][0], 0, d['rect'][2], 24 if a == 94 else 32] for d in doors[a] if d.get('dir') == 'up' and 'warp' in d]
    if a == 90:                                            # the gate's south exit: a foreground ledge covers the last rows
        for d in doors[a]:
            if d.get('dir') == 'down' and 'warp' in d: d['rect'] = [80, 196, 176, 240]; sol.append([80, 216, 176, 240])
    if sol: ent['solid'] = sol
    cfg['new_areas'].append(ent)
json.dump(cfg, open(os.path.join(HERE, 'areas.json'), 'w'), indent=1)
json.dump({'gate_arrival': GATE_ARR}, open(os.path.join(HERE, 'out', 'ch1_points.json'), 'w'))
print('gate arrival', GATE_ARR, 'arena arrival', ra)
for k, v in ARR.items(): print(k, v)
