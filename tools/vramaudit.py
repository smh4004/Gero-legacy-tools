"""OBJ VRAM audit, every area (2026-11-03, user: "make sure nothing appears garbled"; Super 17's frames now take 2 KB).
For each area LoG4 defines: drop the player at a checked arrival point (clipcheck's report) with that act's party
(the drone in Act 1, Lapis in Act 2, Seventeen with the Super 17 skill in Act 3), let the field enemies come, then fire
ki, transform to Super 17 (Act 3), walk and punch around; every ~15 frames tools/vramcheck.py samples IWRAM / EWRAM /
OBJ VRAM / OAM and checks the allocator, every visible sprite's tiles and every registered object's tiles. Also reads
the sprite guard's reject counter (test ROM). Reports per area: problems, peak OBJ VRAM in use, smallest free space.
Needs a test ROM built with --shoot and LOG4_GUARD_COUNTER=0203FF80 (named_lists.json beside it: sw_drone / sw_lapis /
sw_17s) and log4/out/clipcheck/report.json (the release build writes it).
usage: python3 tools/vramaudit.py <test rom> <outdir> [w:a ...]   -> <outdir>/vramaudit.json + a printed table"""
import json, os, struct, subprocess, sys, shutil
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import vramcheck as V

COUNTER = 0x0203FF80
ACT3_LAB = {111, 112, 115, 116, 117, 80, 81, 82, 83}


def party_for(w, a):
    if w == 1 and a not in ACT3_LAB: return 'sw_drone', False
    if w in (4, 16): return 'sw_lapis', False
    return 'sw_17s', True


def actions(super17):
    """Harness lines: what the player does, with a sample every ~15 frames. Returns (lines, sample tags)."""
    L, tags = [], []
    def smp():
        t = '_v%02d' % len(tags); tags.append(t); L.extend(V.sample_lines(t))
        if os.environ.get('KEEP'): L.append('shot %s' % t)         # KEEP=1: keep the dumps, screenshot each sample
    L += ['15 -']; smp()
    for _ in range(3): L += ['2 B', '13 -']; smp()                       # the current skill: ki blasts
    if super17:
        L += ['2 L', '10 -', '2 L', '10 -', '2 L', '10 -', '2 L', '10 -', '2 B']
        for _ in range(6): L += ['15 -']; smp()                          # the transformation (2 KB frames, flash)
    for d in ('LEFT', 'UP', 'RIGHT', 'DOWN', 'LEFT', 'DOWN', 'RIGHT', 'UP'):
        L += ['15 ' + d]; smp()
        L += ['3 A', '5 -', '3 A', '4 -']; smp()
    for _ in range(4): L += ['15 -']; smp()                              # the enemies' turn
    return L, tags


def setup_elsewhere(d, rom, party, place, L, out):
    """Party list in Gero's lab room 1:1 (storyrun's default spot; 1:61's own test warp hook would hide the trigger), then tools/playthrough.py's teleport to the area, then the
    same actions and samples. Returns (lead, form)."""
    import playthrough as P, clipcheck as C_
    w, a, x, y = place
    hooked = os.path.join(d, 'hooked.gba'); P.make_rom(rom, hooked)     # the teleport exit must exist when 1:61 loads
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(rom)), 'named_lists.json'), os.path.join(d, 'named_lists.json'))
    env = dict(os.environ, RECT='96', SHOTS='0', ONESHOT='1', TAIL='60 -', BOOTFLAGS=os.path.join(out, '_boot_h.bin'),
               NAMED=os.path.join(d, 'named_lists.json'))
    subprocess.run(['python3', os.path.join(HERE, 'listtest.py'), hooked, d, 'p', '1:1:112:200', party], env=env,
                   capture_output=True, text=True)
    R = P.Run.__new__(P.Run)
    R.w = d; R.rom = os.path.join(d, 'lt.gba'); R.T = bytearray(open(R.rom, 'rb').read()); R.R = C_.Rom(bytes(R.T))
    R.log = open(os.path.join(d, 'tp.log'), 'w'); R.vprev = None
    R.vram = {'problems': [], 'peak_used': 0, 'samples': 0, 'peak_area': ''}
    R.hook = next(i for i in range(0x1000000, len(R.T) - 32, 4) if struct.unpack_from('<II', R.T, i) == (0x08007675, 0x0800776D)
                  and struct.unpack_from('<4H', R.T, i + 8) == P.MARK)
    if not R.teleport('p_end', w, a, x, y, 'down'): return None, None
    R.h(['1 -', 'load _tp'] + L)
    return open(os.path.join(d, '_lead.bin'), 'rb').read()[0], open(os.path.join(d, '_form.bin'), 'rb').read()[0]


def go(item):
    (w, a), (x, y), rom, out = item
    d = os.path.join(out, 'a%d_%d' % (w, a)); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    party, s17 = party_for(w, a)
    L, tags = actions(s17)
    L += ['dump _cnt %x 4' % COUNTER, 'dump _form 30015dc 1', 'dump _area 3001980 4', 'shot _last']
    L += ['dump _lead 3001068 4']
    want = {'sw_drone': 2, 'sw_lapis': 1, 'sw_17s': 1}[party]
    for arrive in ('120', '60', '220', '320'):     # the party list runs on an A press after arrival: an area's own
        env = dict(os.environ, RECT='96', SHOTS='0', ONESHOT='1', ARRIVE=arrive, TAIL='|'.join(L),   # arrival scene
                   BOOTFLAGS=os.path.join(out, '_boot.bin'))                                           # can eat it
        r = subprocess.run(['python3', os.path.join(HERE, 'listtest.py'), rom, d, 's', '%d:%d:%d:%d' % (w, a, x, y), party],
                           env=env, capture_output=True, text=True)
        try:
            lead = open(os.path.join(d, '_lead.bin'), 'rb').read()[0]; form = open(os.path.join(d, '_form.bin'), 'rb').read()[0]
        except Exception: lead = form = None
        if lead == want and (not s17 or form == 15): break
    if lead != want:                                   # the area's own arrival takes the A press: set the party up
        lead, form = setup_elsewhere(d, rom, party, (w, a, x, y), L, out)            # in the lab, then teleport here
        arrive = 'teleport'
    res = {'area': '%d:%d' % (w, a), 'party': party, 'problems': [], 'samples': 0, 'lead': lead, 'arrive': arrive}
    try:
        T = open(os.path.join(d, 'lt.gba'), 'rb').read()
        prev = None; peak = 0; minfree = 1 << 20; nprob = 0
        for t in tags:
            p, st, prev = V.check(V.load(d, t), T, prev)
            res['samples'] += 1; peak = max(peak, st['used']); minfree = min(minfree, st['largest_free'])
            if p: nprob += 1; res['problems'] += ['%s: %s' % (t, q) for q in p[:3]]
        res.update(peak_used=peak, min_largest_free=minfree,
                   rejects=struct.unpack('<I', open(os.path.join(d, '_cnt.bin'), 'rb').read())[0],
                   form=open(os.path.join(d, '_form.bin'), 'rb').read()[0], bad_samples=nprob)
        for f in os.listdir(d):                                             # keep the disk small: drop the dumps
            if f.startswith('_v') and f.endswith('.bin') and not os.environ.get('KEEP'): os.remove(os.path.join(d, f))
    except Exception as ex:
        res['problems'].append('run failed: %s %s' % (ex, (r.stdout + r.stderr)[-200:]))
    return res


def main(rom, out, only=None):
    os.makedirs(out, exist_ok=True)
    rep = json.load(open(os.path.join(HERE, '..', 'log4', 'out', 'clipcheck', 'report.json')))
    spots = {}
    for key in ('arrival', 'approach'):                    # a checked arrival point, else a door's checked approach
        for c in rep:
            if c['problems'] or c['area'] in spots or key not in c: continue
            spots[c['area']] = tuple(c[key][:2])
    import clipcheck as C                                  # areas clipcheck doesn't place anything in: where a door
    R = C.Rom(open(rom, 'rb').read())                      # of another area brings the player
    cfg = json.load(open(os.path.join(HERE, '..', 'log4', 'areas.json')))
    allv = [(v['world'], v['area']) for v in cfg['new_areas'] + cfg['areas']]
    for w, a in allv:
        for e in R.exits(w, a):
            t = e.get('to')
            if t and '%d:%d' % tuple(t) not in spots and e.get('arrival') and tuple(t) in allv:
                spots['%d:%d' % tuple(t)] = tuple(e['arrival'])
    import numpy as np                                    # last resort: the walkable floor nearest the map's middle
    for w, a in allv:
        k = '%d:%d' % (w, a)
        if k in spots: continue
        try:
            m = R.walk_mask(R.map_of(w, a)); ys, xs = np.nonzero(m)
            ok = [(abs(x_ - xs.mean()) + abs(y_ - ys.mean()), x_, y_) for y_, x_ in zip(ys, xs)
                  if all(C.walkable(m, x_ * 8 + ox, y_ * 8 + oy) for ox in (2, 14) for oy in (4, 14))]
            if ok: _, x_, y_ = min(ok); spots[k] = (int(x_) * 8, int(y_) * 8)
        except Exception: pass
    missing = sorted({'%d:%d' % k for k in allv} - set(spots))
    if missing: print('no arrival point known for', missing)
    items = [(tuple(int(v) for v in k.split(':')), xy, rom, out) for k, xy in spots.items() if not only or k in only]
    first = go(items[0]); results = [first]; print(json.dumps(first), flush=True)
    with ThreadPoolExecutor(int(os.environ.get('JOBS', 6))) as ex:
        for r in ex.map(go, items[1:]): results.append(r); print(json.dumps(r), flush=True)
    json.dump(results, open(os.path.join(out, 'vramaudit.json'), 'w'), indent=1)
    bad = [r for r in results if r['problems'] or r.get('rejects')]
    print('%d areas; %d with problems or guard rejects; peak OBJ VRAM in use %d bytes (%s); smallest largest-free %d bytes'
          % (len(results), len(bad), max(r.get('peak_used', 0) for r in results),
             max(results, key=lambda r: r.get('peak_used', 0))['area'], min(r.get('min_largest_free', 1 << 20) for r in results)))
    return results


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], set(sys.argv[3:]) or None)
