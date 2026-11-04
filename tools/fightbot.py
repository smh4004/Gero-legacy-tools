"""Closed-loop fight bot for boss balance tests (harness runs in short chunks from save states).
Each step: load state, read player (0x0202F3D8, x/y <<8) and boss (found by its HP field = hp<<10; position at
HP field - 0xEC), walk toward the boss, attack when close, save state. Stops when `flag` is set or the player's HP
(character `ch` record +0x16) hits 0.
usage: python3 tools/fightbot.py <rom> <dir> <start state name> <boss hp> <flag> [ch=1] [steps=120] [arrival x y]"""
import os, struct, subprocess, sys
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness')
rom, D, st, bhp, flag = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
ch = int(sys.argv[6]) if len(sys.argv) > 6 else 1; steps = int(sys.argv[7]) if len(sys.argv) > 7 else 120
AX, AY = (int(sys.argv[8]), int(sys.argv[9])) if len(sys.argv) > 9 else (424, 440)   # where the player arrived

def run(lines):
    open(os.path.join(D, '_bot.txt'), 'w').write('\n'.join(lines) + '\n')
    subprocess.run([HARNESS, rom, os.path.join(D, '_bot.txt'), D], capture_output=True)

def rd(n): return open(os.path.join(D, n + '.bin'), 'rb').read()

run(['load ' + st, 'save _bot'])
MARKS = (0x02050810, 0x050C1020)
ENEMY = 0x0804C484
def find():
    """Find the boss's HP field and the player's position in the current _bot state. Run again when a record
    moves (a scripted fight start reallocates the actors: 2026-11-03, Android 13 / the pit rogue)."""
    global hpaddr, pos, ppos, cands
    run(['load _bot', 'dump _ew 2000000 40000']); ew = rd('_ew'); hpaddr = None
    # (2026-11-03) enemy objects start with the word 0x0804C484 (their class), HP at +0x28C (<< 10), position at
    # +0x1A0 (RE_NOTES "Enemy rows and boss fights"). The word before the position ([0x02050810] etc.) is a flags word
    # that varies (0x00001040 on the big machines: Prototype 12, the Security Unit, the Collector), so it isn't used.
    foes = [(struct.unpack_from('<I', ew, i + 0x28C)[0], 0x2000000 + i + 0x28C) for i in range(0, len(ew) - 0x290, 4)
            if struct.unpack_from('<I', ew, i)[0] == ENEMY and struct.unpack_from('<I', ew, i + 0x18)[0] == 0x03001BA4]
    foes = [(v, a) for v, a in foes if 0 < v <= 2 * (bhp << 10)]
    exact = [a for v, a in foes if v == bhp << 10]
    if exact: hpaddr = exact[0]
    elif foes: hpaddr = max(foes)[1]                 # already hit, or HP scaled: the enemy with the most HP left
    assert hpaddr, 'boss HP field not found (no enemy record with HP: the boss has not spawned)'
    pos = hpaddr - 0xEC
    ppos = None                                                     # the player = the position struct ([0x02050810][x][y])
    for i in range(0, len(ew) - 12, 4):                             # nearest the arrival point (424, 440) at the start
        if struct.unpack_from('<I', ew, i)[0] == 0x02050810:
            x, y = (v >> 8 for v in struct.unpack_from('<II', ew, i + 4))
            if 0x2000000 + i + 4 != pos and abs(x - AX) < 40 and abs(y - AY) < 40:
                if ppos is None or abs(x - AX) + abs(y - AY) < best: ppos, best = 0x2000000 + i + 4, abs(x - AX) + abs(y - AY)
    cands = [0x2000000 + i + 4 for i in range(0, len(ew) - 12, 4) if struct.unpack_from('<I', ew, i)[0] == 0x02050810
             and 0x2000000 + i + 4 != pos and abs((struct.unpack_from('<I', ew, i + 4)[0] >> 8) - AX) < 60
             and abs((struct.unpack_from('<I', ew, i + 8)[0] >> 8) - AY) < 60]
    if not cands:                                        # not near the given point: try every position struct
        cands = [0x2000000 + i + 4 for i in range(0, len(ew) - 12, 4) if struct.unpack_from('<I', ew, i)[0] == 0x02050810
                 and 0x2000000 + i + 4 != pos]
        ppos = cands[0] if cands else None
    if ppos is None:                                    # (2026-11-03) the area can move the player on arrival (40-60 px):
        cands = sorted((abs((struct.unpack_from('<I', ew, i + 4)[0] >> 8) - AX) +       # every position record but the
                        abs((struct.unpack_from('<I', ew, i + 8)[0] >> 8) - AY), 0x2000000 + i + 4)   # boss's, nearest
                       for i in range(0, len(ew) - 12, 4)                               # first; the RIGHT / LEFT probe
                       if struct.unpack_from('<I', ew, i)[0] == 0x02050810 and 0x2000000 + i + 4 != pos)   # below picks
        cands = [c for _, c in cands]; ppos = cands[0] if cands else None               # the one the pad moves
    assert ppos, 'player position not found'
    if len(cands) > 1:                                  # an NPC (e.g. Eighteen next to the landing spot) can stand closer:
        xs = {}
        for key in ('RIGHT', 'LEFT'):                  # the player is the one that goes right on RIGHT and left on LEFT
            run(['load _bot', '10 -'] + ['dump _q%d %x 8' % (j, a) for j, a in enumerate(cands)] + ['20 ' + key]
                + ['dump _r%d %x 8' % (j, a) for j, a in enumerate(cands)])
            xs[key] = [struct.unpack('<i', rd('_r%d' % j)[:4])[0] - struct.unpack('<i', rd('_q%d' % j)[:4])[0] for j in range(len(cands))]
        mv = [(xs['RIGHT'][j] - xs['LEFT'][j], a) for j, a in enumerate(cands)]
        if max(mv)[0] > 0: ppos = max(mv)[1]


hpaddr = ppos = None
for _ in range(4):                                   # the boss can appear after an intro: wait up to 3 x 60 frames
    try: find(); break
    except AssertionError as e:
        if _ == 3: raise
        run(['load _bot', '60 -', 'save _bot'])
trace = []; ALL = []; gone = 0; ended = False      # every key line sent, in order (keys.txt: replay it from the start state to record video)
for k in range(steps):
    if hpaddr and ppos: run(['load _bot', 'dump _m %x 4' % (ppos - 4), 'dump _n %x 4' % (hpaddr - 0x28C)])
    if not (hpaddr and ppos) or struct.unpack('<I', rd('_m'))[0] != 0x02050810 or struct.unpack('<I', rd('_n'))[0] != ENEMY:
        try: find(); gone = 0                        # the actors were reallocated (the fight proper began)
        except AssertionError:                       # no actors: a fade, a scene, or "You have died!"
            hpaddr = ppos = None; gone += 1
            if gone >= 3: ended = True; break
            run(['load _bot', '30 -', 'save _bot']); continue
    run(['load _bot', 'dump _p %x 8' % ppos, 'dump _b %x 8' % pos, 'dump _h %x 4' % hpaddr,
         'dump _c 3001560 680', 'dump _f 30010db 40', 'dump _g 3001068 4'])
    px, py = (v >> 8 for v in struct.unpack('<II', rd('_p'))); bx, by = (v >> 8 for v in struct.unpack('<II', rd('_b')))
    bh = struct.unpack('<I', rd('_h'))[0] >> 10; c = rd('_c'); lead = rd('_g')[0] if rd('_g')[0] < 16 else ch   # (2026-11-03) the character
    php = c[0x68 * lead + 0x16] | c[0x68 * lead + 0x17] << 8   # being played: G[0] (IWRAM 0x03001068, RE_NOTES "Party"),
                                                                 # not the `ch` argument (an area script can switch it)
    f = rd('_f'); done = f[flag // 8 - 30] >> (flag % 8) & 1
    trace.append((k, php, bh, (px, py), (bx, by))); AX, AY = px, py      # re-finds look near the player's last spot
    done = done or bh == 0                           # (2026-11-03) the boss's HP ran out (its own flag may differ)
    if done or php == 0: break
    dx, dy = bx - px, by - py
    keys = []
    if os.environ.get('RANGED'):                  # a shooter (the drone): line up on the boss's row, then fire at it
        oy = int(os.environ.get('RANGED_DY', '0'))
        if abs(dy + oy) > 6: keys += ['%d %s' % (min(20, abs(dy + oy)), 'DOWN' if dy + oy > 0 else 'UP')]
        elif abs(dx) > 120: keys += ['%d %s' % (min(24, abs(dx) - 100), 'RIGHT' if dx > 0 else 'LEFT')]
        else: keys += ['2 ' + ('RIGHT' if dx > 0 else 'LEFT'), '4 A', '10 -', '4 A', '10 -', '4 A', '16 -']
    else:
        # (2026-11-03) line up beside the boss on its row and hit it horizontally: standing on top of it (dx, dy ~ 0)
        # the swings miss (the bot used to stall there: Android 13, the pit rogue)
        tx = bx - 18 if px <= bx else bx + 18
        ex, ey = tx - px, by - py
        if abs(dx) < 10 and abs(dy) < 10:               # on top of it (it follows the player): back off and swing at once
            away, back = ('RIGHT', 'LEFT') if px >= bx else ('LEFT', 'RIGHT')
            keys += ['10 ' + away, '2 ' + back, '4 A', '6 -', '4 A', '6 -', '4 A', '10 -']
        elif abs(ex) > 6 or abs(ey) > 6:
            if abs(ex) >= abs(ey): keys += ['%d %s' % (max(2, min(24, abs(ex))), 'RIGHT' if ex > 0 else 'LEFT')]
            else: keys += ['%d %s' % (max(2, min(24, abs(ey))), 'DOWN' if ey > 0 else 'UP')]
            if abs(dx) > 40 and min(abs(ex), abs(ey)) < 12 and not os.environ.get('NOB'): keys += ['4 B', '8 -']   # NOB: B is a skill (Super 17 would revert)
        else:
            keys += ['2 ' + ('RIGHT' if dx > 0 else 'LEFT'), '4 A', '6 -', '4 A', '6 -', '4 A', '10 -']
    pre = [x for x in os.environ.get('BOTPRE', '').split('|') if x]   # harness lines before each step (tests: hold stats)
    if os.environ.get('BOTWEAK') and hpaddr:          # (tests) the boss at 1 HP: the next hit beats it, its death
        pre += ['w8 %x %x' % (hpaddr + i, v) for i, v in enumerate(struct.pack('<I', 1 << 10))]   # script runs as normal
    vr = os.environ.get('BOTVRAM')                    # (2026-11-03) a json file: OBJ VRAM check after every step
    if vr: sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import vramcheck as V
    run(['load _bot'] + pre + keys + ['save _bot'] + (['shot _s%02d' % k] if os.environ.get('BOTSHOTS') else [])
        + (V.sample_lines('_bv') if vr else [])); ALL.extend(pre + keys)
    if vr:
        import json as _j
        if '_vprev' not in globals(): _vprev = None; _rom = open(rom, 'rb').read()
        p_, st_, _vprev = V.check(V.load(D, '_bv'), _rom, _vprev)
        acc = _j.load(open(vr)) if os.path.exists(vr) else {'problems': [], 'peak_used': 0, 'samples': 0}
        acc['problems'] += ['bot step %d: %s' % (k, q) for q in p_]; acc['samples'] += 1
        acc['peak_used'] = max(acc['peak_used'], st_['used']); _j.dump(acc, open(vr, 'w'))
print('player hp / boss hp:', trace[::6] + [trace[-1]])
open(os.path.join(D, 'keys.txt'), 'w').write('\n'.join(ALL))
if ended: print('player hp / boss hp:', trace[::6] + trace[-1:]); print('RESULT ENDED (no actors left: the player died or a scene began) steps', len(trace), 'boss hp', bh); sys.exit(0)
print('RESULT', 'WIN' if done else 'LOSS', 'steps', len(trace), 'player hp', php, 'boss hp', bh)
open(os.path.join(D, 'keys.txt'), 'w').write('\n'.join(ALL))
