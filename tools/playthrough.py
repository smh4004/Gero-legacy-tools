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
        new = len(T); T += struct.pack('<II', 0, BASE + hook) + old     # first: an exit the player stands in (Act Two
                                                                         # starts inside the Z-Mart door's rect) would
                                                                         # otherwise be the match and nothing fires
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
        a_ = self.area(st)                                # a scene area (world 0: the Act Two opening's 0:2, ch4_start's
        if a_ is None or a_[0] == 0: return False         # 0:96) is a scene still running, whatever the pad does
        self.h(['1 -', 'load ' + st, 'dump _pl 5000000 400'])     # a faded screen (black / white: < 8 colours) is a
        if len(set(struct.unpack('<512H', self.rd('_pl')))) < 8: return False   # transition still going (the area can
                                                          # load again under it: night_spotted's park, 2026-11-04)
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
            if self.can_move(cur):
                # (2026-11-04) and it stays put: a list can end with a fade and a load still to come (ch8_landing hands
                # control back, then fades to Vegeta's arena 17:3): settle 90 frames, go on from there if the area changed
                a0 = self.area(cur); self.h(['1 -', 'load ' + cur, '90 -', 'save _settle%d' % (k % 2)])
                if self.area('_settle%d' % (k % 2)) == a0: return cur
                cur = '_settle%d' % (k % 2); continue
            # A for the next text page, then a step away (an examine spot / NPC right in front would start again)
            away = ('DOWN', 'RIGHT', 'UP', 'LEFT')[k // 2 % 4]
            self.h(['1 -', 'load ' + cur, '4 A', '20 -', '14 ' + away, '6 -', 'save _free%d' % (k % 2)]); cur = '_free%d' % (k % 2)
        return cur

    def teleport(self, st, w, a, x, y, face='down', out='_tp'):
        if self._teleport(st, w, a, x, y, face, out): return True
        st2 = self.free(st)                               # still in a text box / scene: finish it, try again
        if self._teleport(st2, w, a, x, y, face, out): return True
        self.say('  teleport to %d:%d from %s failed (area %s)' % (w, a, st, self.area(st2)))
        return False

    def approach(self, st, sx, sy, dr, tries=10):
        """Walk up to an NPC that wanders (BF's own townsfolk move about; a fixed spot misses them) and press A facing
        it. The player is the record nearest the arrival spot, the NPC the one nearest where reachaudit saw it
        (44 px the facing way). Saves _trig."""
        recs = lambda ew_: {i: (struct.unpack_from('<i', ew_, i + 4)[0] >> 8, struct.unpack_from('<i', ew_, i + 8)[0] >> 8)
                            for i in range(0, len(ew_) - 12, 4) if struct.unpack_from('<I', ew_, i)[0] == 0x02050810}
        self.h(['1 -', 'load ' + st, 'dump _ew 2000000 40000']); r = recs(self.rd('_ew'))
        if len(r) < 2: return False
        ux, uy = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}[dr]
        d2 = lambda p, q: (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
        me = min(r, key=lambda i: d2(r[i], (sx, sy)))
        npc = min((i for i in r if i != me), key=lambda i: d2(r[i], (sx + 44 * ux, sy + 44 * uy)))
        cur = st
        for k in range(tries):
            self.h(['1 -', 'load ' + cur, 'dump _ew 2000000 40000']); r = recs(self.rd('_ew'))
            if me not in r or npc not in r: break
            (px, py), (nx, ny) = r[me], r[npc]
            tx, ty = nx - 20 * ux, ny - 20 * uy               # beside it, on the side we face it from
            keys = []
            ax, ay = ('x', tx - px), ('y', ty - py)
            for axis, dv in ((ax, ay) if ux == 0 else (ay, ax)):   # line up across first, then close in
                if abs(dv) > 3:
                    keys.append('%d %s' % (min(24, abs(dv)), ('RIGHT' if dv > 0 else 'LEFT') if axis == 'x' else ('DOWN' if dv > 0 else 'UP')))
            keys += ['3 ' + KEY[dr], '4 A', '20 -']
            nxt = '_ap%d' % (k % 2)
            self.h(['1 -', 'load ' + cur] + keys + ['save ' + nxt]); cur = nxt
            if not self.can_move(cur): break                 # a text box: the talk started
        self.keep(cur, '_trig')
        return True

    def keep(self, st, name):
        """Copy state st to its own name (the helpers below reuse theirs)."""
        if st != name: shutil.copy(os.path.join(self.w, st + '.ss'), os.path.join(self.w, name + '.ss'))
        return name

    def _clear(self, w, a, x, y, face, back):
        """The floor from (x, y) back `back` px against `face` is walkable (no wall to arrive in: 1:104's belt corridor
        is only 32 px tall, 2026-11-04)"""
        try:
            m = self.R.walk_mask(self.R.map_of(w, a))
        except Exception: return True
        ux, uy = {'down': (0, -1), 'up': (0, 1), 'left': (1, 0), 'right': (-1, 0)}[face]
        return all(C.walkable(m, x + ux * d + ox, y + uy * d + oy) for d in range(0, back + 1, 4) for ox in (-6, 6) for oy in (-4, 0))

    def _teleport(self, st, w, a, x, y, face='down', out='_tp'):
        """From state st to (w, a) with the player arriving at (x, y) facing `face` (he walks ~14 px that way)."""
        # the arrival walk (~14 px the facing way) ignores collision: arriving right at an obstacle can wedge the player
        # inside it (verified 2026-11-03: Ambush Ridge's stump, no way out). Arrive 16 px further back; the approach
        # after it walks normally
        back = 14 + (16 if out != '_tpw' and self._clear(w, a, x, y, face, 30) else 0)
        dx, dy = {'down': (0, -back), 'up': (0, back), 'left': (back, 0), 'right': (-back, 0)}[face]
        struct.pack_into('<II', self.T, self.hook + 16, ((DIRS[face] + 1) << 4) | (w << 8) | (a << 16) | (1 << 24),
                         ((y + dy) << 16) | (x + dx))
        open(self.rom, 'wb').write(self.T)
        # (2026-11-04) let a transition finish first: a state saved as a fade starts reloads the area ~30 frames on,
        # and the exits are instantiated again from the ROM over the rect written below (night_spotted's park)
        self.h(['1 -', 'load ' + st, '90 -', 'save _tp0']); st = '_tp0'
        self.h(['1 -', 'load ' + st, 'dump _ew 2000000 40000'])
        ew = self.rd('_ew'); pat = struct.pack('<4H', *MARK)
        hits = [i for i in range(0, len(ew) - 8, 2) if ew[i:i + 8] == pat]
        if not hits: return False
        L = ['1 -', 'load ' + st]
        # (2026-11-04) the area's other exits go off the map for this one move: an exit the player is standing in is
        # the match and the hook never fires (Act Two starts inside the Z-Mart door's rect). The warp reloads the
        # exits from the ROM.
        here = self.area(st)
        if here:
            try:
                e_ = self.R.entry(*here); n_ = self.T[e_ + 3]; xp = struct.unpack_from('<I', self.T, e_ + 0x10)[0] - BASE
                for k in range(n_):
                    o_ = struct.unpack_from('<I', self.T, xp + 8 * k + 4)[0] - BASE
                    r_ = bytes(self.T[o_ + 8:o_ + 16])
                    if r_ == pat or not 0 <= o_ < len(self.T): continue
                    for i in range(0, len(ew) - 8, 2):
                        if ew[i:i + 8] == r_:
                            for k2, v in enumerate(struct.pack('<4H', 0x7FF0, 0x7FF0, 0x7FF0, 0x7FF0)):
                                L.append('w8 %x %x' % (0x2000000 + i + k2, v))
            except Exception: pass
        for i in hits:
            for k, v in enumerate(struct.pack('<4H', 0, 0, 0x7FF0, 0x7FF0)): L.append('w8 %x %x' % (0x2000000 + i + k, v))
        start = self.area(st)
        near = lambda ew_: {(i, struct.unpack_from('<i', ew_, i + 4)[0] >> 10, struct.unpack_from('<i', ew_, i + 8)[0] >> 10)
                            for i in range(0, len(ew_) - 12, 4) if struct.unpack_from('<I', ew_, i)[0] == 0x02050810
                            and abs((struct.unpack_from('<i', ew_, i + 4)[0] >> 8) - x) <= 48
                            and abs((struct.unpack_from('<i', ew_, i + 8)[0] >> 8) - y) <= 48}   # (record, x/4, y/4):
                                                                       # someone new there, or moved there
        before = near(ew)
        # (2026-11-04) wait out a fade first: right after the Act Two opening the screen fades in from white and the
        # exits don't fire yet (the DOWN press did nothing and, in the same area, the check below passed anyway)
        self.h(L + ['150 -', '4 DOWN', '200 -', 'save ' + out, 'dump _ew 2000000 40000', 'dump _ar 3001980 4'])
        now = self.area()
        if now == (w, a) == start and not (near(self.rd('_ew')) - before):
            # same area and nobody arrived at the spot: it didn't fire. Unless it's a walk-in and the player already
            # stands there: the previous list's own warp brought him (ch8_after_krillin lands in Piccolo's rect)
            return out == '_tpw' and bool(near(self.rd('_ew')))
        # a walk-in trigger fires on arrival: its scene can already have moved the camera to a scene area (ch4_start
        # shows 0:96 right away, 2026-11-04). Arriving there counts once the player has left the area he was in
        return now == (w, a) or (out == '_tpw' and now not in (None, start))

    def hold(self, st):
        """w8 lines that refill every party member's HP (field enemies must not end the run; the run logs it)."""
        self.h(['1 -', 'load ' + st, 'dump _ch 3001560 3a8'])
        c = self.rd('_ch'); L = []
        for k in range(9):
            hp, mx = struct.unpack_from('<HH', c, 0x68 * k + 0x16)
            if mx and c[0x68 * k] & 1:
                L += ['w8 %x %x' % (0x3001560 + 0x68 * k + 0x16 + i, v) for i, v in enumerate(struct.pack('<H', mx))]
        return L

    def advance(self, st, lst, sets, limit=90, where='', away='DOWN', base=None):
        """Press A through the list's text until its flags are set, then step away between presses (so the NPC / spot
        isn't set off again) until the player can move; VRAM samples on the way. Returns (state, done)."""
        cur = st; hold = self.hold(st); low = None
        fl0 = self.flags(base or cur); todo = [f for f in sets if not self.fset(fl0, f)]   # base: the state before the
                                                          # walk-up (R.approach can start the talk: its flags are set)
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
            if 'ENDED' in out_ and os.path.exists(os.path.join(d, '_bot.ss')):   # the boss's actors went away: its death
                shutil.copy(os.path.join(d, '_bot.ss'), os.path.join(self.w, '_fe.ss'))    # (explosion, level-up text)
                c_, _ = self.advance('_fe', 'fight row %d' % row, [flag], 40)              # or the player's: see which
                if self.fset(self.flags(c_), flag):
                    shutil.copy(os.path.join(self.w, c_ + '.ss'), os.path.join(d, '_bot.ss'))
                    res += 'death flag %d set: WIN; ' % flag; break
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
        for name, (w, a, x, y, dr) in self.reach.items():   # BF's own NPC objects given a talk list (areas.json
            if name not in tr:                                # "object_talk": West City's fence, police, townsfolk):
                tr[name] = dict(kind='npc', w=w, a=a, rect=(x - 8, y - 8, x + 8, y + 8), dir=dr)   # reachaudit's spot
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
    # chapter 5: its side content (act2_ch5: the fence, the museum, the Ruby heist, notes) comes before the mattresses
    # (ch5_rest -> ch5_end, the night falls), as the walkthrough says: "Finish anything else in town, then examine the
    # mattresses"
    names = [e['list'] for e in lists]
    if 'night_police' in names and 'ch5_rest' in names:
        side = [e for e in lists if e['file'] == 'act2_ch5']
        endl = [e for e in lists if e['list'] in ('ch5_rest', 'ch5_end')]
        rest = [e for e in lists if e not in side and e not in endl]
        k = [e['list'] for e in rest].index('night_police')
        lists = rest[:k] + side + endl + rest[k:]
    # ch6_home ends chapter 6: the Collector's death runs the ambush and Act Three's opening on its own, so the rest of
    # chapter 6 (the old house, rooftops, Riverside, Docks, Mrs. Oda) comes before it, right before the ambush
    names = [e['list'] for e in lists]
    if 'ch6_home' in names and 'ch6_ambush' in names:
        home = lists[names.index('ch6_home')]; rest = [e for e in lists if e is not home]
        k = [e['list'] for e in rest].index('ch6_ambush')
        lists = rest[:k] + [home] + rest[k:]
    # a chapter's own ending list (chN_end with a trigger of its own, e.g. ch7_end: walking out of the lab runs
    # ch8_start) goes after the rest of its file (the lockdown, the archive, the quarters come first)
    trig_ = {}
    for v in json.load(open(os.path.join(HERE, '..', 'log4', 'areas.json')))['new_areas'] + \
            json.load(open(os.path.join(HERE, '..', 'log4', 'areas.json')))['areas']:
        for d in v.get('doors', []) + v.get('doors_append', []): trig_[d.get('event')] = 1
    for e in [e for e in lists if re.fullmatch(r'ch\d+_end', e['list']) and e['list'] in trig_]:
        rest = [x for x in lists if x is not e]
        last = max(i for i, x in enumerate(rest) if x['file'] == e['file'])
        lists = rest[:last + 1] + [e] + rest[last + 1:]
    # chapter 8: the docks and the old hideout (the tin box, 359) come before the fruit stall (341 needs 359), and the
    # stall before the landing (ch8_landing needs 341), as the walkthrough has it
    names = [e['list'] for e in lists]
    grp = [n_ for n_ in ('ch8_hideout', 'ch8_cache_river', 'ch8_cache_docks', 'note_warehouse', 'ch8_stall') if n_ in names]
    if 'ch8_landing' in names and grp:
        mv = [lists[names.index(n_)] for n_ in grp]; rest = [e for e in lists if e not in mv]
        k = [e['list'] for e in rest].index('ch8_landing')
        lists = rest[:k] + mv + rest[k:]
    # the Lookout's altar (lookout_door) wants all seven balls: after the last ball (kame_ball)
    names = [e['list'] for e in lists]
    if 'lookout_door' in names and 'kame_ball' in names:
        ld = lists[names.index('lookout_door')]; rest = [e for e in lists if e is not ld]
        k = [e['list'] for e in rest].index('kame_ball')
        lists = rest[:k + 1] + [ld] + rest[k + 1:]
    # ch4_pod ends Act One (the pod scene warps to Act Two): the chapter's side content (the pass, the graveyard, the
    # files) comes before it
    names = [e['list'] for e in lists]
    if 'ch4_pod' in names:
        pod = lists[names.index('ch4_pod')]; rest = [e for e in lists if e is not pod]
        last = max(i for i, e in enumerate(rest) if e['file'] == 'act1_ch4')
        lists = rest[:last + 1] + [pod] + rest[last + 1:]
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
    tpfail = {}; retry = {}
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
                if t['kind'] == 'walk': spot = (cx, cy, 'down', None)     # (arrives inside the rect: _tpw, no step back)
                elif e['list'] in R.reach:
                    _, _, sx, sy, dr = R.reach[e['list']]; spot = (sx, sy, dr, dr)
                else:
                    dr = t.get('dir') or 'up'
                    sx, sy = {'up': (cx, y1 + 10), 'down': (cx, y0 - 6), 'left': (x1 + 12, cy), 'right': (x0 - 12, cy)}[dr]
                    spot = (sx, sy, dr, dr)
                cur = R.keep(cur, '_main0')
                if not R.teleport(cur, t['w'], t['a'], spot[0], spot[1], spot[2], '_tpw' if t['kind'] == 'walk' else '_tp'):
                    res['result'] = 'teleport to %d:%d failed' % (t['w'], t['a'])
                else:
                    cur = '_tpw' if t['kind'] == 'walk' else '_tp'
                    away = 'DOWN'
                    if spot[3]:                          # walk up to it pressing A (reachaudit's verified "sweep")
                        k_ = KEY[spot[3]]; away = {'UP': 'DOWN', 'DOWN': 'UP', 'LEFT': 'RIGHT', 'RIGHT': 'LEFT'}[k_]
                        if t['kind'] == 'npc' and R.approach('_tp', spot[0], spot[1], spot[3]): cur = '_trig'
                        else: R.h(['1 -', 'load _tp'] + ['6 ' + k_, '4 A', '16 -'] * 16 + ['save _trig']); cur = '_trig'
                    cur, done = R.advance(cur, e['list'], e['sets'], where='%d:%d' % (t['w'], t['a']), away=away, base='_main0')
                    b = boss_here(cur)                           # a boss the list set loose here
                    if b:
                        f, row = b
                        cur, fr = R.fight(cur, row, f); R.say('  fight row', row, 'flag', f, ':', fr)
                        cur, _ = R.advance(cur, e['list'] + '/after', [f], 40)
                        res.setdefault('fights', []).append('row %d: %s' % (row, fr))
                    fl = R.flags(cur)
                    miss = [f for f in e['sets'] if not R.fset(fl, f)]
                    res['result'] = 'done' if not miss else ('done (this visit; still unset: %s)' % miss if done else 'NOT DONE: flags %s not set' % miss)
                    if miss and done: revisit.append(e)
        # every boss whose spawn condition now holds (side jobs: the rogue mechanoids once the sergeant gave the job)
        cur = R.keep(R.free(cur), '_main')               # (settled first: the list's own fade + load to a boss arena,
                                                          # ch8_landing -> Vegeta 17:3, must be done before the boss check)
                                                          # (advance / free / teleport reuse their state names: a
        fl = R.flags(cur)                                # revisit's advance overwrote _adv1 = cur, 2026-11-04)
        for f, (row, (bw, ba), en) in sorted(bosses.items()):
            if R.fset(fl, f) or not all(R.fset(fl, g) for g in cond_flags(en.get('condition', 0))): continue
            # only bosses a flag set loose (side jobs, story spawns: their condition needs a flag SET); bosses that are
            # just there until beaten are fought when a trigger needs them or the run is in their area
            # (2026-11-04) not while a later list of this chapter still has its trigger in that area: talking to Krillin
            # (ch8_krillin) is what starts his fight; fighting him first skipped the talk
            later_here = any(x['file'] == e['file'] and x['list'] in tr and (tr[x['list']]['w'], tr[x['list']]['a']) == (bw, ba)
                             for x in lists[i + 1:])
            if cond_flags(en.get('condition', 0)) or ((bw, ba) == R.area(cur) and not later_here):
                if not R.teleport(cur, bw, ba, en['x'], en['y'] + 56, 'up', '_tpb'): continue
                c2, fr = R.fight('_tpb', row, f); R.say('  fight row', row, 'flag', f, 'at %d:%d' % (bw, ba), ':', fr)
                c2, _ = R.advance(c2, 'boss%d' % row, [f], 40); cur = R.keep(c2, '_main'); fl = R.flags(cur)
                res.setdefault('fights', []).append('row %d: %s' % (row, fr))
        cur = R.keep(cur, '_main2')
        if res.get('result', '').startswith('NOT DONE') and e not in revisit:
            revisit.append(e); retry[e['list']] = (e['file'], 0, i)   # a boss in the way (relay_3 waits for Prototype 9:
                                                          # tried at once), a flag a later list sets: tried after it
        for e2 in list(revisit):                          # lists with a second visit (rewards) whose flags can be set now
            if e2['list'] in retry:                       # (2026-11-04) a NOT DONE list whose script waits for a flag a
                fi, cnt, since = retry[e2['list']]        # later list of its chapter sets (ch8_stall needs 359): tried
                if since == i and not res.get('fights'): continue   # again after each later list of that chapter, 4 times
                if lists[i]['file'] != fi or cnt >= 4:
                    revisit.remove(e2); del retry[e2['list']]
                    R.say('  %s still NOT DONE at the end of its chapter' % e2['list']); continue
                retry[e2['list']] = (fi, cnt + 1, since)
            t2 = tr[e2['list']]; need2, clear2 = SR.WHEN.get(e2['list'], ([], []))
            if not all(R.fset(fl, f) for f in need2) or any(R.fset(fl, f) for f in clear2): continue
            sp2 = R.reach.get(e2['list'])
            if not sp2 and t2['kind'] == 'walk':          # a walk-in: arrive inside its rect
                x0_, y0_, x1_, y1_ = t2['rect']; sp2 = (t2['w'], t2['a'], (x0_ + x1_) // 2, (y0_ + y1_) // 2, 'down')
            if not sp2: continue
            out2 = '_tpw' if t2['kind'] == 'walk' else '_tp'
            if not R.teleport(cur, t2['w'], t2['a'], sp2[2], sp2[3], sp2[4], out2):
                tpfail[e2['list']] = tpfail.get(e2['list'], 0) + 1      # out of reach now (another act's world)
                if tpfail[e2['list']] >= 3:
                    revisit.remove(e2); retry.pop(e2['list'], None); R.say('  revisit %s dropped (no way there)' % e2['list'])
            else:
                k_ = KEY[sp2[4]]
                if t2['kind'] == 'walk': R.keep('_tpw', '_trig')
                elif not (t2['kind'] == 'npc' and R.approach('_tp', sp2[2], sp2[3], sp2[4])):
                    R.h(['1 -', 'load _tp'] + ['6 ' + k_, '4 A', '16 -'] * 16 + ['save _trig'])
                c2, ok2 = R.advance('_trig', e2['list'] + '/revisit', e2['sets'], base=R.keep(cur, '_rv0'))
                fl2 = R.flags(c2)
                if ok2 and any(R.fset(fl2, f) and not R.fset(fl, f) for f in e2['sets']):   # finished, and it moved on
                    cur = R.keep(c2, '_main2'); fl = fl2; res.setdefault('revisits', []).append(e2['list'])
                    if all(R.fset(fl, f) for f in e2['sets']) or e2['list'] in retry:
                        revisit.remove(e2)
                        if e2['list'] in retry:
                            del retry[e2['list']]
                            for r_ in prog['results']:
                                if r_['list'] == e2['list'] and r_['result'].startswith('NOT DONE'):
                                    r_['result'] = 'done later (retried after list %d %s)' % (i, e['list'])
                            R.say('  %s done later, after list %d' % (e2['list'], i))
        if e['list'] in res.get('revisits', []) and res['result'].startswith('NOT DONE'):
            res['result'] = 'done (after the fight)'; retry.pop(e['list'], None)
        cur = R.free(cur)                                 # never carry a state with a text box open
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
