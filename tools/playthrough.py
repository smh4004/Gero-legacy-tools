"""Continuous playthrough (2026-11-03, user: "one save carried from the start of Act 1 to the end ... chapter by chapter
and save progress ... run step 1's process during the whole check").

One game state is carried through every story list in story order (tools/storyrun.py's list order): levels, EXP,
items, party, forms and flags all come from actually playing the lists before, not from presets. Between triggers the
player is TELEPORTED (walking between places is what tools/clipcheck.py / reachaudit.py check): the test ROM gets one
extra warp exit in every area (class 0x08007675, DOWN-held getter) whose ROM rect is a tiny marker; its EWRAM copy
(areas instantiate their exits on load) is widened to the whole map and DOWN pressed, after the ROM file's destination
words were set to the target. Then each list is set off the way a player does it: walk-in rects by arriving inside,
examine spots and NPCs from tools/reachaudit.py's verified standing points (press the direction, then A). Text is
advanced with A until the list's flags are set and the player can move again. Bosses whose death flag a later trigger
needs, or that the list spawned, are fought with tools/fightbot.py (the player's HP is held so the run can go on; the
lowest HP reached is reported). Every ~30 frames (and every bot step) tools/vramcheck.py checks OBJ VRAM and every
visible sprite; the sprite guard's reject counter is read after every list.
Progress is saved after every list (states/NNN_<list>.ss, progress.json): re-running resumes; `--from N` restarts there.
usage: python3 tools/playthrough.py <test rom (--shoot, LOG4_GUARD_COUNTER=0203FF80)> <outdir> [--only-chapter FILE]
       [--from N] [--reach <reachaudit output>]"""
import json, os, re, struct, subprocess, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import clipcheck as C, storyrun as SR, vramcheck as V

H = os.path.join(HERE, 'harness')
FB, COUNTER, BASE = 0x30010BD, 0x0203FF80, 0x08000000
MARK = (5, 3, 6, 4)                                  # the hook's ROM rect (x0, y0, x1, y1): a marker no exit uses
DIRS = {'down': 0, 'up': 1, 'left': 2, 'right': 3}
KEY = {'down': 'DOWN', 'up': 'UP', 'left': 'LEFT', 'right': 'RIGHT'}
STATS = json.load(open(os.path.join(HERE, '..', 'log4', 'stats.json')))['enemies']


def make_rom(src, dst):
    """The test ROM plus the teleport hook in every area's exit list. Returns the hook offset."""
    T = bytearray(open(src, 'rb').read())
    hook = (len(T) + 0xFF) & ~0xFF
    T += bytes(hook + 0x20 - len(T))
    struct.pack_into('<IIHHHHII', T, hook, 0x08007675, 0x0800776D, *MARK, 0, 0)
    import areas as A
    tab = struct.unpack_from('<I', T, 0x8A58)[0] - BASE; cnt = A.area_count(T)
    # field enemies that aren't bosses (no death flag in stats.json) never spawn: they knock the player off the NPC /
    # spot he is walking up to, and they don't take part in the story (tools/vramaudit.py checks areas with them)
    never = len(T); T += b'\x00\x00\x11\x00'
    bossrows = {int(r) for r, v in STATS.items() if isinstance(v, dict) and 'call 29' in v.get('death', '')}
    for k in range(cnt):
        e = tab + 56 * k
        no, lp = T[e + 4], struct.unpack_from('<I', T, e + 0x14)[0]
        if no and BASE <= lp < BASE + len(T):
            for i in range(no):
                o = struct.unpack_from('<I', T, lp - BASE + 4 * i)[0]
                if BASE <= o < BASE + len(T) - 32 and struct.unpack_from('<I', T, o - BASE)[0] == 0x0800FD55 \
                        and struct.unpack_from('<I', T, o - BASE + 8)[0] not in bossrows:
                    struct.pack_into('<I', T, o - BASE + 4, BASE + never)
    for k in range(cnt):
        e = tab + 56 * k
        n, xp = T[e + 3], struct.unpack_from('<I', T, e + 0x10)[0]
        if n >= 250: continue
        old = bytes(T[xp - BASE:xp - BASE + 8 * n]) if n and BASE <= xp < BASE + len(T) else b''
        while len(T) % 4: T += b'\0'
        new = len(T); T += old + struct.pack('<II', 0, BASE + hook)
        T[e + 3] = n + 1; struct.pack_into('<I', T, e + 0x10, BASE + new)
    open(dst, 'wb').write(T)
    return hook


class Run:
    def __init__(self, rom_src, out, reach=None):
        self.out = out; os.makedirs(os.path.join(out, 'states'), exist_ok=True)
        self.w = os.path.join(out, 'work'); os.makedirs(self.w, exist_ok=True)
        self.rom = os.path.join(out, 'pt.gba')
        self.hook = make_rom(rom_src, self.rom)
        self.T = bytearray(open(self.rom, 'rb').read()); self.R = C.Rom(bytes(self.T))
        self.log = open(os.path.join(out, 'log.txt'), 'a')
        self.vprev = None; self.vram = {'problems': [], 'peak_used': 0, 'samples': 0, 'peak_area': ''}
        self.reach = {}
        if reach and os.path.exists(reach):
            for l in open(reach):
                m = re.match(r'(ok|INSIDE)\s+(\d+):(\d+)\s+(\w+)\s+(\S+)\s+\((\d+), (\d+), \'(\w+)\'', l)
                if m: self.reach.setdefault(m.group(5), (int(m.group(2)), int(m.group(3)), int(m.group(6)), int(m.group(7)), m.group(8)))

    def say(self, *a):
        s = ' '.join(str(x) for x in a); print(s, flush=True); self.log.write(s + '\n'); self.log.flush()

    def h(self, lines):
        p = os.path.join(self.w, '_s.txt'); open(p, 'w').write('\n'.join(lines) + '\n')
        subprocess.run([H, self.rom, p, self.w], capture_output=True, timeout=600)

    def rd(self, n): return open(os.path.join(self.w, n + '.bin'), 'rb').read()

    # ---- state queries
    def flags(self, st):
        self.h(['1 -', 'load ' + st, 'dump _fl %x 70' % FB]); return self.rd('_fl')

    @staticmethod
    def fset(fl, f): return fl[f // 8] >> (f % 8) & 1

    def area(self, st=None):
        if st: self.h(['1 -', 'load ' + st, 'dump _ar 3001980 4'])
        p = struct.unpack('<I', self.rd('_ar'))[0] - BASE
        return (self.T[p], self.T[p + 1]) if 0 <= p < len(self.T) - 1 else None

    def sample(self, tag, where):
        """VRAM check of the sample dumped as tag."""
        p, st, self.vprev = V.check(V.load(self.w, tag), self.T, self.vprev)
        self.vram['samples'] += 1
        if st['used'] > self.vram['peak_used']: self.vram['peak_used'], self.vram['peak_area'] = st['used'], where
        for q in p: self.vram['problems'].append('%s: %s' % (where, q)); self.say('  VRAM', where, q)

    def can_move(self, st):
        """The player answers the pad (no script / text box holding him): a position record moves with the pad."""
        for a_, b_ in (('RIGHT', 'LEFT'), ('DOWN', 'UP')):
            self.h(['1 -', 'load ' + st, 'dump _e0 2000000 40000', '12 ' + a_, 'dump _e1 2000000 40000', '24 ' + b_, 'dump _e2 2000000 40000'])
            a, b, c = self.rd('_e0'), self.rd('_e1'), self.rd('_e2')
            for i in range(0, len(a) - 12, 4):
                if struct.unpack_from('<I', a, i)[0] == 0x02050810:
                    k = 4 if a_ == 'RIGHT' else 8
                    v0, v1, v2 = (struct.unpack_from('<i', m, i + k)[0] >> 8 for m in (a, b, c))
                    if v1 - v0 >= 4 and v1 - v2 >= 4: return True
        return False

    # ---- actions
    def free(self, st, tries=30):
        """Press A (one text page at a time) until the player can move. Returns the state."""
        cur = st
        for k in range(tries):
            if self.can_move(cur): return cur
            self.h(['1 -', 'load ' + cur, '4 A', '30 -', 'save _free%d' % (k % 2)]); cur = '_free%d' % (k % 2)
        return cur

    def teleport(self, st, w, a, x, y, face='down', out='_tp'):
        if self._teleport(st, w, a, x, y, face, out): return True
        st2 = self.free(st)                               # still in a text box / scene: finish it, try again
        if self._teleport(st2, w, a, x, y, face, out): return True
        self.say('  teleport to %d:%d from %s failed (area %s)' % (w, a, st, self.area(st2)))
        return False

    def _teleport(self, st, w, a, x, y, face='down', out='_tp'):
        """From state st to (w, a) with the player arriving at (x, y) facing `face` (he walks ~14 px that way)."""
        dx, dy = {'down': (0, -14), 'up': (0, 14), 'left': (14, 0), 'right': (-14, 0)}[face]
        struct.pack_into('<II', self.T, self.hook + 16, ((DIRS[face] + 1) << 4) | (w << 8) | (a << 16) | (1 << 24),
                         ((y + dy) << 16) | (x + dx))
        open(self.rom, 'wb').write(self.T)
        self.h(['1 -', 'load ' + st, 'dump _ew 2000000 40000'])
        ew = self.rd('_ew'); pat = struct.pack('<4H', *MARK)
        hits = [i for i in range(0, len(ew) - 8, 2) if ew[i:i + 8] == pat]
        if not hits: return False
        L = ['1 -', 'load ' + st]
        for i in hits:
            for k, v in enumerate(struct.pack('<4H', 0, 0, 0x7FF0, 0x7FF0)): L.append('w8 %x %x' % (0x2000000 + i + k, v))
        self.h(L + ['4 DOWN', '200 -', 'save ' + out, 'dump _ar 3001980 4'])
        return self.area() == (w, a)

    def hold(self, st):
        """w8 lines that refill every party member's HP (field enemies must not end the run; the run logs it)."""
        self.h(['1 -', 'load ' + st, 'dump _ch 3001560 3a8'])
        c = self.rd('_ch'); L = []
        for k in range(9):
            hp, mx = struct.unpack_from('<HH', c, 0x68 * k + 0x16)
            if mx and c[0x68 * k] & 1:
                L += ['w8 %x %x' % (0x3001560 + 0x68 * k + 0x16 + i, v) for i, v in enumerate(struct.pack('<H', mx))]
        return L

    def advance(self, st, lst, sets, limit=90, where='', away='DOWN'):
        """Press A through the list's text until its flags are set, then step away between presses (so the NPC / spot
        isn't set off again) until the player can move; VRAM samples on the way. Returns (state, done)."""
        cur = st; hold = self.hold(st); low = None
        fl0 = self.flags(cur); todo = [f for f in sets if not self.fset(fl0, f)]
        # a list with branches sets only some of its flags per visit (e.g. a job giver: accept now, reward later):
        # done when any flag it still had to set got set and the text is over
        prog_ = lambda fl: (not todo) or any(self.fset(fl, f) for f in todo)
        for k in range(limit):
            nxt = '_adv%d' % (k % 2)
            fl = self.rd('_fl') if k else self.flags(cur)
            if prog_(fl) and (todo or k >= 6):
                # its job is done: from now on press A only while something holds the player (a text box), so an NPC
                # or examine spot isn't started again
                if self.can_move(cur): return cur, True
                keys = ['4 A', '20 -']
            else: keys = ['4 A', '26 -']
            self.h(['1 -', 'load ' + cur] + hold + keys + V.sample_lines('_sv') +
                   ['save ' + nxt, 'dump _fl %x 70' % FB, 'dump _ar 3001980 4'])
            self.sample('_sv', '%s %s' % (lst, where or '%d:%d' % (self.area() or (0, 0))))
            cur = nxt
        return cur, prog_(self.rd('_fl'))

    def fight(self, st, row, flag, steps=150):
        d = os.path.join(self.w, 'bot'); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        shutil.copy(os.path.join(self.w, st + '.ss'), os.path.join(d, 'f0.ss')); shutil.copy(self.rom, os.path.join(d, 'lt.gba'))
        self.h(['1 -', 'load ' + st, 'dump _g 3001068 4']); lead = self.rd('_g')[0]
        hold = '|'.join(self.hold(st))                    # HP held at max: the run must go on (the result says how it went)
        vj = os.path.join(d, 'vram.json')
        res = ''
        for weak in ('', '1'):                            # the bot's own fight first; if it can't win, the boss at 1 HP
            env = dict(os.environ, NOB='1', BOTPRE=hold, BOTVRAM=vj, BOTWEAK=weak, RANGED='1' if lead == 2 and not weak else '')   # helped: point blank
            r = subprocess.run(['python3', os.path.join(HERE, 'fightbot.py'), os.path.join(d, 'lt.gba'), d, 'f0',
                                str(STATS[str(row)]['hp']), str(flag), str(lead), str(steps if not weak else 40)],
                               env=env, capture_output=True, text=True)
            out_ = (r.stdout + r.stderr).strip().split('\n')[-1][:100]
            res += ('helped: ' if weak else '') + out_ + '; '
            if 'WIN' in out_: break
        else:                                             # the bot never landed the last hit: set the death flag by hand
            fb = FB + flag // 8                           # (every death script starts with it; the rest is a heal and,
            self.h(['1 -', 'load ' + st, 'dump _fx %x 1' % fb])        # for some, a warp the
            v = self.rd('_fx')[0] | 1 << (flag % 8)                                           # next teleport replaces)
            self.h(['1 -', 'load ' + st, 'w8 %x %x' % (fb, v), '30 -', 'save _fought'])
            return '_fought', res.rstrip('; ') + '; flag %d SET BY HAND' % flag
        res = res.rstrip('; ')
        if os.path.exists(vj):
            v = json.load(open(vj)); self.vram['samples'] += v['samples']
            for q in v['problems']: self.vram['problems'].append('fight row %d: %s' % (row, q)); self.say('  VRAM', q)
        shutil.copy(os.path.join(d, '_bot.ss'), os.path.join(self.w, '_fought.ss'))
        return '_fought', res

    # ---- the story
    def triggers(self):
        cfg = json.load(open(os.path.join(HERE, '..', 'log4', 'areas.json')))
        tr = {}
        for v in cfg['areas'] + cfg['new_areas']:
            w, a = v['world'], v['area']
            for d in v.get('doors', []) + v.get('doors_append', []):
                ev = d.get('event')
                if not ev or 'rect' not in d or ev in tr: continue
                x0, y0, x1, y1 = d['rect']
                if d.get('examine'): kind = 'examine'
                elif d.get('fn2', '').lower() == '0x080077df': kind = 'walk'
                else: kind = 'apress'
                tr[ev] = dict(kind=kind, w=w, a=a, rect=(x0, y0, x1, y1), dir=d.get('examine'))
            for s in v.get('spawns', []) + v.get('spawns_append', []):
                if s.get('talk') and s['talk'] not in tr:
                    tr[s['talk']] = dict(kind='npc', w=w, a=a, rect=(s['x'] - 8, s['y'] - 16, s['x'] + 8, s['y']), dir='up')
        return tr

    def boss_rows(self):
        """death flag -> (row, (w, a) where it spawns, spawn condition)"""
        cfg = json.load(open(os.path.join(HERE, '..', 'log4', 'areas.json')))
        out = {}
        for v in cfg['new_areas'] + cfg['areas']:
            for e in v.get('enemies', []):
                m = re.findall(r'call 29 (\d+)', STATS.get(str(e['type']), {}).get('death', ''))
                for f in m: out.setdefault(int(f), (e['type'], (v['world'], v['area']), e))
        return out


def main():
    args = sys.argv[1:]
    rom, out = args[0], args[1]
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    R = Run(rom, out, opt('--reach'))
    lists = SR.story_lists(); SR.places()                       # (fills SR.WHEN)
    # story order, not file order: act2_siblings ends with the crossroads ambush (end of Act Two, it runs Act Three's
    # start); Act Two's chapter 5 / 6 side content (act2_ch5, act2_ch6) comes before it
    names = [e['list'] for e in lists]
    if 'ch6_ambush' in names:
        k = names.index('ch6_ambush'); tail = [e for e in lists[k:] if e['file'] == 'act2_siblings']
        rest = [e for e in lists if e not in tail]
        last = max(i for i, e in enumerate(rest) if e['file'] in ('act2_ch5', 'act2_ch6'))
        lists = rest[:last + 1] + tail + rest[last + 1:]
    tr = R.triggers(); bosses = R.boss_rows()
    prog_p = os.path.join(out, 'progress.json')
    prog = json.load(open(prog_p)) if os.path.exists(prog_p) else {'next': 0, 'state': None, 'results': []}
    if opt('--from') is not None:
        n = int(opt('--from')); prog['next'] = n
        prog['results'] = [r for r in prog['results'] if r['i'] < n]
        prog['state'] = prog['results'][-1]['state'] if prog['results'] else None
    if prog['state'] is None:                                    # a new game: the title, new game and the opening
        R.say('boot: new game')
        R.h(C.BOOT + ['save _boot'])
        shutil.copy(os.path.join(R.w, '_boot.ss'), os.path.join(out, 'states', '000_boot.ss'))
        prog['state'] = '000_boot'
    only = opt('--only-chapter')

    def cond_flags(c):                                   # (as tools/enemysweep.py) flags a spawn condition needs set
        if isinstance(c, int): return [c & 0xFFFF] if c >> 16 == 1 else []
        if not isinstance(c, str) or not c.startswith('hex '): return []
        b = bytes.fromhex(c[4:]); o = []; i = 0
        while i < len(b) and b[i] == 1:
            i += 1; v = 0
            while b[i] & 0x80: v = (v << 7) | (b[i] & 0x7F); i += 1
            v = (v << 7) | b[i]; i += 1
            if b[i] == 2 and b[i + 1] == 27: o.append(v >> 1)
            i += 2
            if i < len(b) and b[i] == 4: i += 1
        return o

    def boss_here(cur):
        """A boss (row with a death flag) that is spawned in the current area: its flag clear, its spawn flags set."""
        fl = R.flags(cur); here = R.area(cur)
        for f, (row, wa, en) in bosses.items():
            if wa == here and not R.fset(fl, f) and all(R.fset(fl, g) for g in cond_flags(en.get('condition', 0))):
                return f, row
        return None

    revisit = [lists[r['i']] for r in prog['results'] if r.get('result', '').startswith('done (this visit')]
    later_need = {f for e_ in lists for f in SR.WHEN.get(e_['list'], ([], []))[0]}
    for i in range(prog['next'], len(lists)):
        e = lists[i]
        if only and e['file'] != only: continue
        shutil.copy(os.path.join(out, 'states', prog['state'] + '.ss'), os.path.join(R.w, 'cur.ss'))
        res = {'i': i, 'list': e['list'], 'file': e['file']}
        cur = 'cur'
        fl = R.flags(cur)
        t = tr.get(e['list'])
        if e['sets'] and all(R.fset(fl, f) for f in e['sets']):
            res['result'] = 'already done (ran as part of an earlier list)'
        elif not t:
            res['result'] = 'no trigger of its own (run by another list / an enemy death)'
        else:
            need, clear = SR.WHEN.get(e['list'], ([], []))
            for f in need:                                       # a boss this trigger waits for: fight it first
                if not R.fset(fl, f) and f in bosses:
                    row, (bw, ba), en = bosses[f]
                    if R.teleport(cur, bw, ba, en['x'], en['y'] + 56, 'up', '_tpb'):
                        cur, fr = R.fight('_tpb', row, f); R.say('  fight row', row, 'for flag', f, ':', fr)
                        cur, _ = R.advance(cur, e['list'] + '/boss', [f], 40)
                        fl = R.flags(cur)
            blocked = [f for f in need if not R.fset(fl, f)] + [f for f in clear if R.fset(fl, f)]
            if blocked:
                res['result'] = 'blocked: trigger needs flags %s' % blocked
            else:
                x0, y0, x1, y1 = t['rect']; cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
                if t['kind'] == 'walk': spot = (cx, cy, 'down', None)
                elif e['list'] in R.reach:
                    _, _, sx, sy, dr = R.reach[e['list']]; spot = (sx, sy, dr, dr)
                else:
                    dr = t.get('dir') or 'up'
                    sx, sy = {'up': (cx, y1 + 10), 'down': (cx, y0 - 6), 'left': (x1 + 12, cy), 'right': (x0 - 12, cy)}[dr]
                    spot = (sx, sy, dr, dr)
                if not R.teleport(cur, t['w'], t['a'], spot[0], spot[1], spot[2]):
                    res['result'] = 'teleport to %d:%d failed' % (t['w'], t['a'])
                else:
                    cur = '_tp'
                    away = 'DOWN'
                    if spot[3]:                          # walk up to it pressing A (reachaudit's verified "sweep")
                        k_ = KEY[spot[3]]; away = {'UP': 'DOWN', 'DOWN': 'UP', 'LEFT': 'RIGHT', 'RIGHT': 'LEFT'}[k_]
                        R.h(['1 -', 'load _tp'] + ['6 ' + k_, '4 A', '16 -'] * 16 + ['save _trig']); cur = '_trig'
                    cur, done = R.advance(cur, e['list'], e['sets'], where='%d:%d' % (t['w'], t['a']), away=away)
                    b = boss_here(cur)                           # a boss the list set loose here
                    if b:
                        f, row = b
                        cur, fr = R.fight(cur, row, f); R.say('  fight row', row, 'flag', f, ':', fr)
                        cur, _ = R.advance(cur, e['list'] + '/after', [f], 40)
                    fl = R.flags(cur)
                    miss = [f for f in e['sets'] if not R.fset(fl, f)]
                    res['result'] = 'done' if not miss else ('done (this visit; still unset: %s)' % miss if done else 'NOT DONE: flags %s not set' % miss)
                    if miss and done: revisit.append(e)
        # every boss whose spawn condition now holds (side jobs: the rogue mechanoids once the sergeant gave the job)
        fl = R.flags(cur)
        for f, (row, (bw, ba), en) in sorted(bosses.items()):
            if R.fset(fl, f) or not all(R.fset(fl, g) for g in cond_flags(en.get('condition', 0))): continue
            # only bosses a flag set loose (side jobs, story spawns: their condition needs a flag SET); bosses that are
            # just there until beaten are fought when a trigger needs them or the run is in their area
            if cond_flags(en.get('condition', 0)) or (bw, ba) == R.area(cur):
                if not R.teleport(cur, bw, ba, en['x'], en['y'] + 56, 'up', '_tpb'): continue
                c2, fr = R.fight('_tpb', row, f); R.say('  fight row', row, 'flag', f, 'at %d:%d' % (bw, ba), ':', fr)
                c2, _ = R.advance(c2, 'boss%d' % row, [f], 40); cur = c2; fl = R.flags(cur)
                res.setdefault('fights', []).append('row %d: %s' % (row, fr))
        for e2 in list(revisit):                          # lists with a second visit (rewards) whose flags can be set now
            t2 = tr[e2['list']]; need2, clear2 = SR.WHEN.get(e2['list'], ([], []))
            if not all(R.fset(fl, f) for f in need2) or any(R.fset(fl, f) for f in clear2): continue
            sp2 = R.reach.get(e2['list'])
            if not sp2: continue
            if R.teleport(cur, t2['w'], t2['a'], sp2[2], sp2[3], sp2[4]):
                k_ = KEY[sp2[4]]
                R.h(['1 -', 'load _tp'] + ['6 ' + k_, '4 A', '16 -'] * 16 + ['save _trig'])
                c2, ok2 = R.advance('_trig', e2['list'] + '/revisit', e2['sets'])
                fl2 = R.flags(c2)
                if any(R.fset(fl2, f) and not R.fset(fl, f) for f in e2['sets']):
                    cur = c2; fl = fl2; res.setdefault('revisits', []).append(e2['list'])
                    if all(R.fset(fl, f) for f in e2['sets']): revisit.remove(e2)
        R.h(['1 -', 'load ' + cur, 'dump _cnt %x 4' % COUNTER, 'dump _ar 3001980 4', '2 -', 'shot _end'])
        res['rejects'] = struct.unpack('<I', R.rd('_cnt'))[0]; res['end_area'] = '%d:%d' % (R.area() or (0, 0))
        name = '%03d_%s' % (i + 1, e['list'])
        shutil.copy(os.path.join(R.w, cur + '.ss'), os.path.join(out, 'states', name + '.ss'))
        shutil.copy(os.path.join(R.w, '_end.png'), os.path.join(out, 'states', name + '.png'))
        prog['state'] = name; res['state'] = name; res['vram_problems'] = len(R.vram['problems'])
        prog['results'].append(res); prog['next'] = i + 1
        json.dump(prog, open(prog_p, 'w'), indent=1)
        json.dump(R.vram, open(os.path.join(out, 'vram.json'), 'w'), indent=1)
        R.say('%3d %-24s %-16s end %-6s rejects %d  %s' % (i, e['list'], e['file'], res['end_area'], res['rejects'], res['result']))
    R.say('end: %d VRAM samples, %d problems, peak OBJ VRAM %d bytes (%s)' %
          (R.vram['samples'], len(R.vram['problems']), R.vram['peak_used'], R.vram['peak_area']))


if __name__ == '__main__':
    main()
