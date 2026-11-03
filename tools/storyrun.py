"""Automated story run: plays every story list of the game, in story order, in the emulator, each from a fresh boot
with every flag the earlier lists set already set (tools/listtest.py), at the place the game triggers it (its
event / NPC in log4/areas.json; lists without one run in Gero's lab, 1:1). Then checks:
  - the run finished (no emulator error), and where it ended (area);
  - which of the flags the list sets got set ("flags: missing" = a set_flag that never ran: a branch, or a hang);
  - the last screen (contact sheets: look for black screens, garbled sprites, wrong places). NPC talks and examine
    spots run again on the later A presses (the game's own trigger is right there), so their last screen can show a
    repeat talk; the flags column is the reliable "it finished" signal.
usage: python3 tools/storyrun.py <rom> <outdir> [list name filter ...]
env:   JOBS (4), SHOTS (A presses after the trigger, 40)"""
import json, os, re, sys, glob, struct, subprocess
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import scenes

ORDER = ['act1_opening', 'lab_talk', 'act1_ch1', 'act1_ch2', 'act1_ch3', 'act1_ch4', 'act2_siblings', 'act2_ch5',
         'act2_ch6', 'act3_ch7', 'act3_ch8', 'act3_ch9', 'act3_world', 'act3_world_fly', 'act3_ch10', 'credits',
         'secret_first_steps']
FB = 0x30010BD


def story_lists():
    out = []
    for name in ORDER:
        p = os.path.join(HERE, '..', 'log4', 'scenes', name + '.scene')
        if not os.path.exists(p): continue
        sc = scenes.parse(p)
        cuts = sc.get('lists', [])
        for k, (ln, i) in enumerate(cuts):
            steps = sc['steps'][i:cuts[k + 1][1] if k + 1 < len(cuts) else len(sc['steps'])]
            sets, clears, guard = [], [], set()
            for st in steps:
                if st[0] == 'ifflag': guard.add(st[1])
                if st[0] == 'do':
                    sets += [int(m) for m in re.findall(r'call 29 (\d+)', st[1])]
                    clears += [int(m) for m in re.findall(r'call 30 (\d+)', st[1])]
            out.append({'list': ln, 'file': name, 'sets': sets, 'clears': clears, 'guards': sorted(guard)})
    return out


WHEN = {}
DEATH = {int(f) for e in json.load(open(os.path.join(HERE, '..', 'log4', 'stats.json')))['enemies'].values()
         if isinstance(e, dict) for f in re.findall(r'call 29 (\d+)', e.get('death', ''))}


def when_flags(w):
    """A trigger condition -> (flags that must be set, flags that must be clear)."""
    st, cl = [], []
    if w.startswith('hex '):
        b = bytes.fromhex(w[4:]); i = 0
        while i < len(b):
            if b[i] == 0x01:
                v, i = scenes.varint(b, i + 1)
                if i + 1 < len(b) and b[i] == 0x02 and b[i + 1] in (27, 28): (st if b[i + 1] == 27 else cl).append(v); i += 2
            else: i += 1
    for k, f in re.findall(r'call (2[78]) (\d+)', w): (st if k == '27' else cl).append(int(f))
    return st, cl


def places():
    cfg = json.load(open(os.path.join(HERE, '..', 'log4', 'areas.json')))
    pl = {}
    for v in cfg.get('areas', []) + cfg['new_areas']:
        w, a = v['world'], v['area']
        for d in v.get('doors', []):
            if d.get('event') and 'rect' in d:
                r = d['rect']; pl.setdefault(d['event'], (w, a, (r[0] + r[2]) // 2, (r[1] + r[3]) // 2, tuple(r)))
                if d.get('when') and d['event'] not in WHEN: WHEN[d['event']] = when_flags(d['when'])
        for s in v.get('spawns', []):
            if s.get('talk'): pl.setdefault(s['talk'], (w, a, s['x'], s['y'] + 24, (s['x'] - 24, s['y'] - 24, s['x'] + 24, s['y'] + 24)))
    return pl


def stand_near(R, w, a, x, y, rect):
    """A walkable spot 24-90 px outside the trigger rect / NPC, so the game's own trigger doesn't fire again when
    later A presses advance the text (the injected test trigger covers +-40 px around the spot)."""
    import clipcheck as C
    try: m = R.walk_mask(R.map_of(w, a))
    except Exception: return x, y + 40
    ok = lambda X, Y: all(C.walkable(m, X + dx, Y + dy) for dx in (-6, 6) for dy in (-4, 4))
    x0, y0, x1, y1 = rect
    for d in range(24, 92, 4):
        for X, Y in ((x, y1 + d), (x0 - d, y), (x1 + d, y), (x, y0 - d)):
            if ok(X, Y): return X, Y
    return x, y1 + 36


def main(rom, out, filt):
    os.makedirs(out, exist_ok=True)
    pl = places(); L = story_lists(); R_ = {}
    done = set(); jobs = []
    for e in L:
        need, clear = WHEN.get(e['list'], ([], []))
        boss = set(e['guards']) & DEATH                   # it checks a boss's death flag: that fight was won
        pre = sorted((done | set(need) | boss) - set(clear) - set(e['sets']) - set(e['clears']))   # (its other if_flag checks are prerequisites: keep them)
        p = pl.get(e['list'])
        if p:
            import clipcheck as C
            R = R_.setdefault('R', C.Rom(open(rom, 'rb').read()))
            e['place'] = (p[0], p[1], p[2], p[3])     # on the trigger itself (a spot beside it often missed the A-press trigger)
        else: e['place'] = (1, 1, 112, 200)
        e['pre'] = pre
        done |= set(e['sets']); done -= set(e['clears'])
        if not filt or any(f in e['list'] for f in filt): jobs.append(e)
    shots = os.environ.get('SHOTS', '40')
    boot = os.path.join(out, '_bootflags.bin')

    def run(e):
        d = os.path.join(out, e['list'])
        env = dict(os.environ, SHOTS=shots, BOOTFLAGS=boot, ONESHOT='1', NOENEMIES='1', TAIL='120 -|dump %s_area 3001980 4' % 'r')
        w, a, x, y = e['place']
        r = subprocess.run(['python3', os.path.join(HERE, 'listtest.py'), rom, d, 'r', '%d:%d:%d:%d' % (w, a, x, y), e['list']]
                           + [str(f) for f in e['pre']], env=env, capture_output=True, text=True)
        res = dict(e, ok=r.returncode == 0, err=r.stderr[-300:] if r.returncode else '')
        try:
            fl = open(os.path.join(d, 'r_flags.bin'), 'rb').read()
            res['set_ok'] = [f for f in e['sets'] if fl[f // 8 - 30] >> (f % 8) & 1]
            res['missing'] = [f for f in e['sets'] if f not in res['set_ok']]
            T = open(os.path.join(d, 'lt.gba'), 'rb').read()
            ap = struct.unpack('<I', open(os.path.join(d, 'r_area.bin'), 'rb').read())[0] - 0x08000000
            res['end_area'] = '%d:%d' % (T[ap], T[ap + 1]) if 0 <= ap < len(T) else hex(ap)
            for f in glob.glob(os.path.join(d, 'r_[0-9]*.png')) + [os.path.join(d, 'lt.gba')]: os.remove(f)
        except Exception as ex:
            res['ok'] = False; res['err'] = (res['err'] + ' ' + repr(ex))[-300:]
        return res

    pre_jobs = [j for j in jobs if j['pre']]
    first = [run(pre_jobs[0])] if pre_jobs and not os.path.exists(boot) else []   # fills the shared opening flags
    rest = [j for j in jobs if not first or j is not pre_jobs[0]]
    with ThreadPoolExecutor(int(os.environ.get('JOBS', 4))) as ex:
        results = first + list(ex.map(run, rest))
    order = [j['list'] for j in jobs]
    results.sort(key=lambda r: order.index(r['list']))
    json.dump(results, open(os.path.join(out, 'report.json'), 'w'), indent=1)
    bad = [r for r in results if not r['ok'] or r.get('missing')]
    for r in results:
        print('%-4s %-24s %-8s end %-6s %s' % ('OK' if r['ok'] and not r.get('missing') else 'CHECK', r['list'],
              '%d:%d' % r['place'][:2], r.get('end_area', '?'), ('missing flags %s' % r['missing']) if r.get('missing') else r.get('err', '')))
    sheet(out, results)
    print('%d lists, %d to check' % (len(results), len(bad)))


def sheet(out, results, per=24):
    from PIL import Image, ImageDraw
    for k in range(0, len(results), per):
        part = results[k:k + per]
        W = Image.new('RGB', (6 * 244, ((len(part) + 5) // 6) * 176), (20, 20, 20)); dr = ImageDraw.Draw(W)
        for i, r in enumerate(part):
            p = os.path.join(out, r['list'], 'r_end.png')
            x, y = (i % 6) * 244, (i // 6) * 176
            if os.path.exists(p): W.paste(Image.open(p), (x + 2, y + 14))
            dr.text((x + 3, y + 1), '%s %s' % (r['list'], '' if r['ok'] and not r.get('missing') else '[CHECK]'), fill=(255, 255, 120))
        W.save(os.path.join(out, 'sheet_%02d.png' % (k // per)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
