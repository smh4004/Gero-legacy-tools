"""Reachability audit: can the player actually walk up to every LoG4 examine spot and NPC and set it off with A?
(2026-11-02: the Lookout's palace door played fine when its list was run directly, but no player could reach its rect.)

For each target (every examine exit and every NPC whose talk list is a LoG4 named list), in a copy of the ROM:
  - the target's list is swapped for a sentinel list that only sets flag 437, and its exit condition is cleared;
  - story triggers and field enemies are neutralised (clipcheck.make_test_rom), the player is dropped next to the
    target (outside an examine rect / beside an NPC, on walkable floor), holds the direction toward it, presses A;
  - pass = flag 437 set. NPCs are tried from below, left, right and above; examine spots from three points along the
    rect's near edge. Failures get a screenshot.
usage: python3 tools/reachaudit.py <rom> <outdir> [area filter w:a ...]"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clipcheck as C, scenes
from areas import EXAMINE

BASE, FB, SENT = 0x08000000, 0x30010BD, 437
u32 = lambda b, o: struct.unpack_from('<I', b, o)[0]


def main():
    rom_path, out = sys.argv[1], sys.argv[2]; only = set(sys.argv[3:])
    here = os.path.dirname(os.path.abspath(__file__))
    named = json.load(open(os.path.join(os.path.dirname(os.path.abspath(rom_path)), 'named_lists.json')))
    byptr = {v: k for k, v in named.items()}
    cfg = json.load(open(os.path.join(here, '..', 'log4', 'areas.json')))
    areas = sorted({(a['world'], a['area']) for a in cfg['new_areas'] + cfg.get('areas', [])})
    R = C.Rom(open(rom_path, 'rb').read())
    T, hook = C.make_test_rom(R, keep_story=False, keep_enemies=False)
    while len(T) % 4: T.append(0)
    step = len(T); T += struct.pack('<HB', 1, 0) + bytes([0x01]) + scenes.enc_varint(SENT) + bytes([0x02, 29, 0x11])
    while len(T) % 4: T.append(0)
    sent = len(T); T += struct.pack('<II', BASE + step, 0)
    getter_face = {0x0800774F: 'up'}
    targets = []
    for (w, a) in areas:
        if only and '%d:%d' % (w, a) not in only: continue
        e = R.entry(w, a)
        ne, xp = T[e + 3], u32(T, e + 0x10)
        for i in range(ne if xp else 0):
            prm_off = xp - BASE + 8 * i; o = u32(T, prm_off + 4) - BASE
            if u32(T, o) != 0x0800742D or u32(T, o + 16) not in byptr: continue
            g = u32(T, o + 4); face = getter_face.get(g)
            if face is None and BASE <= g - 1 < BASE + len(T) and u32(T, g - 1 - BASE) == 0x47704800:
                lit = u32(T, g - 1 - BASE + 4); face = next((k for k, v in EXAMINE.items() if v == lit), None)
            if face is None: continue                                  # walk-in / hold-UP events: not A-press
            targets.append(dict(kind='examine', w=w, a=a, name=byptr[u32(T, o + 16)], face=face,
                                rect=struct.unpack_from('<4H', T, o + 8), ptr=o + 16, cond=prm_off))
        n, lp = T[e + 4], u32(T, e + 0x14)
        for k in range(n if lp else 0):
            o = u32(T, lp - BASE + 4 * k) - BASE
            if u32(T, o) == 0x08017DA3 and u32(T, o + 12) in byptr:
                pos = u32(T, o + 8)
                targets.append(dict(kind='npc', w=w, a=a, name=byptr[u32(T, o + 12)], pos=(pos & 0xFFFF, pos >> 16),
                                    ptr=o + 12))
    os.makedirs(out, exist_ok=True)
    tr = os.path.join(out, 'ra.gba'); open(tr, 'wb').write(T)
    harness = os.path.join(here, 'harness')
    C.run(harness, tr, C.BOOT + ['save field'], out)
    masks = {}
    def walk_ok(w, a, x, y):
        if (w, a) not in masks: masks[(w, a)] = R.walk_mask(R.map_of(w, a))
        m = masks[(w, a)]
        return all(C.walkable(m, x + 8 + dx, y + 8 + dy) for dx in (-6, 0, 6) for dy in (-4, 0, 4))
    D = {'down': 0, 'up': 1, 'left': 2, 'right': 3}
    def frames_to(t, x, y, f):
        """hold the direction about as long as it takes to reach the target's middle (the player walks ~1 px/frame):
        walking on would carry the player straight through a rect on open floor"""
        if t['kind'] == 'npc': cx, cy = t['pos']; return 70
        # the player object sits at (arrival x, arrival y - 16) (EWRAM 0x0202F2BC, x << 8, y << 8; measured), ~0.95 px/frame
        x0, y0, x1, y1 = t['rect']; cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        return int(max(4, abs(cx - x) if f in ('left', 'right') else abs(cy - y)) / 0.95) + 2
    report = []
    OVR = json.load(open(os.environ['OVR'])) if os.environ.get('OVR') else {}   # name -> [[x, y, face, 'seq', 'harness|lines']]
    print('%d targets' % len(targets))
    for n_, t in enumerate(targets):
        w, a = t['w'], t['a']
        STEP = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
        def scan(x0, y0, x1, y1, f, near):
            """walkable start points outside the target on the side opposite f, nearest first, spread sideways"""
            dx, dy = STEP[f]; out_ = []
            for d in range(8, 96, 8):
                if dy:
                    yy = y1 + d if dy < 0 else y0 - d
                    cands = [(xx, yy) for xx in range(x0 - 8, x1 - 7, 8)]
                else:
                    xx = x1 + d - 8 if dx < 0 else x0 - d - 16
                    cands = [(xx, yy) for yy in range(y0 + 4, max(y0 + 5, y1 - 3), 8)]   # rect test point = arrival-frame y
                cands.sort(key=lambda p: abs(p[0] - near[0]) + abs(p[1] - near[1]))
                out_ += [(p[0], p[1], f, 'walk') for p in cands if walk_ok(w, a, *p)]
            seen_, picked = set(), []
            for p in out_:                                       # at most one start per sideways lane, nearest first
                k = p[0] // 16 if dy else p[1] // 16
                if k not in seen_: seen_.add(k); picked.append(p)
            return picked
        if t['kind'] == 'npc':
            x, y = t['pos']
            tries = [p_ for p_ in [(x, y + 44, 'up', 'sweep'), (x - 40, y + 4, 'right', 'sweep'), (x + 40, y + 4, 'left', 'sweep'),
                                   (x, y - 40, 'down', 'sweep'), (x, y + 30, 'up', 'sweep'), (x - 28, y + 4, 'right', 'sweep')]
                     if walk_ok(w, a, p_[0], p_[1])]
        else:
            x0, y0, x1, y1 = t['rect']; f = t['face']
            sc_ = scan(x0, y0, x1, y1, f, ((x0 + x1) // 2 - 8, (y0 + y1) // 2 - 8))
            far = [p_ for p_ in sc_ if (p_[1] - y1 >= 32 if f == 'up' else y0 - p_[1] >= 32 if f == 'down'
                                        else p_[0] - x1 >= 24 if f == 'left' else x0 - p_[0] >= 40)]
            near = [p_ for p_ in sc_ if p_ not in far]
            # (2026-11-04) the arrival walk (~14 px the facing way) ignores collision: from a near start it carried the
            # player through the obstacle into the rect, and the spot "passed" though no player can stand there (the park
            # bench note, Mrs. Oda's bag, the dome doors: found by tools/playthrough.py). Start 16 px further back
            # wherever that floor is walkable, so the sweep has to walk up to it for real
            bx, by = {'up': (0, 1), 'down': (0, -1), 'left': (1, 0), 'right': (-1, 0)}[f]
            near = [(p_[0] + 16 * bx, p_[1] + 16 * by) if all(walk_ok(w, a, p_[0] + d * bx, p_[1] + d * by) for d in (4, 8, 12, 16))
                    else p_ for p_ in near]
            tries = [(p_[0], p_[1], f, 'sweep') for p_ in (far[:3] + near[:2])]
            # last resort: stand inside the rect facing f (passes only if some floor inside the rect works at all)
            tries += [(xx, yy, f, 'inside') for yy in range(y0 + 2, y1, 4) for xx in range(x0, x1 - 7, 8)
                      if walk_ok(w, a, xx, yy)][:2]
        if t['name'] in OVR: tries = [tuple(v) for v in OVR[t['name']]] + tries
        tries = tries or [((t['pos'][0] if t['kind'] == 'npc' else t['rect'][0]), (t['pos'][1] + 40 if t['kind'] == 'npc' else t['rect'][3] + 8), 'up', 'walk')]
        old = bytes(T[t['ptr']:t['ptr'] + 4]); struct.pack_into('<I', T, t['ptr'], BASE + sent)
        if t['kind'] == 'examine': oldc = bytes(T[t['cond']:t['cond'] + 4]); struct.pack_into('<I', T, t['cond'], 0)
        relock = []          # a "locked" examine sits on a conditional warp: keep that warp's real condition (no flags = shut)
        if t['kind'] == 'examine':
            e = R.entry(w, a); ne, xp = T[e + 3], u32(T, e + 0x10)
            for i in range(ne if xp else 0):
                po = xp - BASE + 8 * i; o = u32(T, po + 4) - BASE
                if u32(T, o) != 0x08007675: continue
                r0 = struct.unpack_from('<4H', T, o + 8); r1 = t['rect']
                if r0[0] < r1[2] and r1[0] < r0[2] and r0[1] < r1[3] and r1[1] < r0[3] and u32(R.r, po):
                    relock.append((po, bytes(T[po:po + 4]))); T[po:po + 4] = R.r[po:po + 4]
        ok, used = False, None
        for j, (x, y, f, mode, *_) in enumerate(tries[:7]):
            struct.pack_into('<II', T, hook + 16, ((D[f] + 1) << 4) | (w << 8) | (a << 16) | (1 << 24), (y << 16) | x)
            open(tr, 'wb').write(T)
            nm = 'c%03d_%d' % (n_, j)
            # sweep: step toward the target pressing A every few pixels (a player walking up and mashing A)
            mv = ['6 %s|4 A|16 -' % f.upper()] * 16 if mode == 'sweep' else ['2 %s' % f.upper()]
            if mode == 'seq': mv = tries[j][4].split('|')
            mv = '|'.join(mv).split('|')
            C.run(harness, tr, ['load field', '3 DOWN', '200 -'] + mv + ['10 -', '4 A', '60 -',
                                'shot %s' % nm, 'dump %s 30010f0 8' % nm, 'dump %s_pos 202f2bc 8' % nm], out)
            fl = open(os.path.join(out, nm + '.bin'), 'rb').read()
            b = FB + SENT // 8 - 0x30010F0
            if fl[b] >> (SENT % 8) & 1: ok, used = True, tuple(tries[j][:4]); break
        struct.pack_into('<I', T, t['ptr'], u32(old, 0))
        if t['kind'] == 'examine': T[t['cond']:t['cond'] + 4] = oldc
        for po, v in relock: T[po:po + 4] = v
        r = dict(t, ok=ok, via=used, first=used == tries[0] if ok else False, tried=tries[:6]); r.pop('ptr'); r.pop('cond', None)
        report.append(r)
        print('%-6s %d:%-3d %-8s %-24s %s' % (('ok' if used[3] != 'inside' else 'INSIDE') if ok else 'FAIL', w, a, t['kind'], t['name'], used if ok else tries[:4]), flush=True)
    json.dump(report, open(os.path.join(out, 'report.json'), 'w'), indent=1)
    bad = [r for r in report if not r['ok']]
    print('%d of %d reachable; %d FAIL' % (len(report) - len(bad), len(report), len(bad)))


if __name__ == '__main__':
    main()
