"""Helpers for generated chapter areas (gen_ch*.py): floor masks, spawn/arrival snapping, edge exits.
Masks come from a built ROM (LoG2-imported maps exist only there) or the BF ROM (map_from BF areas)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import clipcheck as C, scenes

BF = C.Rom(open(os.path.join(HERE, '..', 'bf.gba'), 'rb').read())
_built = os.path.join(HERE, 'out', 'LoG4_shoot.gba')
OUT = C.Rom(open(_built if os.path.exists(_built) else os.path.join(HERE, 'out', 'LoG4.gba'), 'rb').read())
STEP = {'down': (0, 1), 'up': (0, -1), 'left': (-1, 0), 'right': (1, 0), None: (0, 0)}
FACE_IN = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}


def hexcond(*parts):
    """('set'|'clear', flag) ... ANDed -> 'hex ..' condition text."""
    b = b''
    for i, (k, f) in enumerate(parts):
        b += b'\x01' + scenes.enc_varint(f) + bytes([0x02, 27 if k == 'set' else 28])
        if i: b += b'\x04'
    return 'hex ' + (b + b'\x11').hex(' ')


def notcond(*parts):
    b = bytes.fromhex(hexcond(*parts)[4:])[:-1] + b'\x00\x00\x0b\x11'
    return 'hex ' + b.hex(' ')


class Gen:
    def __init__(self, src, size, world=1):
        """src: {area: ('bf', [w, a]) | ('l2', '0x..') | ('new', area)}; size: {area: (w, h) in px}"""
        self.src, self.size, self.doors, self._m, self.world = src, size, {a: [] for a in src}, {}, world

    def mask(self, a):
        if a not in self._m:
            k, s = self.src[a]
            self._m[a] = BF.walk_mask(BF.map_of(*s)) if k == 'bf' else OUT.walk_mask(OUT.map_of(self.world, s if k == 'new' else a))
        return self._m[a]

    def ok(self, a, x, y, r=12, face=None):
        """(x, y) = spawn origin / arrival point; feet at (x + 8, y + 8), an arrival's settle 14 px further on."""
        m = self.mask(a); dx, dy = STEP[face]
        for k in (0, 7, 14) if face else (0,):
            fx, fy = x + 8 + dx * k, y + 8 + dy * k
            if not all(C.walkable(m, fx + ex, fy + ey) for ex in range(-r, r + 1, 4) for ey in range(-r, 5, 4)): return False
        return True

    def snap(self, a, x, y, r=12, face=None):
        if self.ok(a, x, y, r, face): return [x, y]
        for d in range(4, 200, 4):
            for t in range(-d, d + 1, 4):
                for X, Y in ((x + t, y - d), (x + t, y + d), (x - d, y + t), (x + d, y + t)):
                    if self.ok(a, X, Y, r, face): return [X, Y]
        raise ValueError('no floor near 1:%d (%d,%d)' % (a, x, y))

    def edge(self, a, side, lo, hi):
        """Distance (px) from the map edge to the first walkable row/column of this opening."""
        m = self.mask(a); W, H = self.size[a]
        for k in range(0, 240, 8):
            if side == 'up': hit = any(C.walkable(m, x, k + 4) for x in range(lo + 4, hi, 8))
            elif side == 'down': hit = any(C.walkable(m, x, H - k - 4) for x in range(lo + 4, hi, 8))
            elif side == 'left': hit = any(C.walkable(m, k + 4, y) for y in range(lo + 4, hi, 8))
            else: hit = any(C.walkable(m, W - k - 4, y) for y in range(lo + 4, hi, 8))
            if hit: return k
        raise ValueError('opening 1:%d %s %d-%d is solid' % (a, side, lo, hi))

    def rect(self, a, side, lo, hi):
        W, H = self.size[a]; e = self.edge(a, side, lo, hi)
        return {'up': [lo, 0, hi, e + 48], 'down': [lo, H - e - 28, hi, H], 'left': [0, lo, e + 14, hi],
                'right': [W - e - 28, lo, W, hi]}[side]

    def arrival(self, a, side, lo, hi):
        W, H = self.size[a]; e = self.edge(a, side, lo, hi); mid = (lo + hi) // 2 - 8; face = FACE_IN[side]
        p = {'up': (mid, e + 64), 'down': (mid, H - e - 72), 'left': (e + 24, mid), 'right': (W - e - 56, mid)}[side]
        if side == 'up':
            for y in range(e + 64, e + 180, 4):
                for dx in sorted(range(-40, 41, 4), key=abs):
                    if self.ok(a, mid + dx, y, 14, face): return [mid + dx, y]
        return self.snap(a, *p, 14, face)

    def link(self, a, sa, b, sb, names, when_a=None, to_a=None):
        """Two-way edge exits: opening sa = (side, lo, hi) of area a <-> sb of area b. when_a / to_a: optional
        (condition, other destination area) alternative for a's exit (e.g. the same doorway leading elsewhere later)."""
        arr = {a: self.arrival(a, *sa), b: self.arrival(b, *sb)}
        for (x, s, y, t) in ((a, sa, b, sb), (b, sb, a, sa)):
            d = {'rect': self.rect(x, *s), 'warp': [self.world, y, arr[y][0], arr[y][1]], 'dir': s[0], 'face': FACE_IN[t[0]],
                 '_note': '%s -> %s' % (names[x], names[y])}
            self.doors[x].append(d)
        return arr

    def ev(self, a, rect, event, examine=None, when=None, note='', walk=False):
        d = {'rect': list(rect), 'event': event, '_note': note}
        if examine: d['examine'] = examine
        if walk: d['fn2'] = '0x080077DF'
        if when: d['when'] = when
        self.doors[a].append(d)

    def solid_for_top_exits(self, a):
        return [[d['rect'][0], 0, d['rect'][2], max(32, d['rect'][3] - 48)] for d in self.doors[a] if d.get('dir') == 'up' and 'warp' in d]


def write(entries, drop, world=1):
    """Replace new_areas entries for (world, area) in `drop` with `entries`."""
    p = os.path.join(HERE, 'areas.json'); cfg = json.load(open(p))
    cfg['new_areas'] = [x for x in cfg['new_areas'] if not (x['world'] == world and x['area'] in drop)] + entries
    json.dump(cfg, open(p, 'w'), indent=1)
