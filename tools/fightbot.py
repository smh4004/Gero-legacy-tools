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

run(['load ' + st, 'dump _ew 2000000 40000', 'save _bot'])
ew = rd('_ew'); hpaddr = None
for i in range(0xF0, len(ew) - 4, 4):                 # exact max HP behind a position struct (other copies exist)
    if struct.unpack_from('<I', ew, i)[0] == bhp << 10 and (struct.unpack_from('<I', ew, i - 0xF0)[0] == 0x02050810 or
                                                         os.environ.get('ANYMARK')):   # vehicles (BF Tank) use another class
        hpaddr = 0x2000000 + i; break
if hpaddr is None:                                  # already hit: an enemy HP field (0 < hp <= max) behind a position struct
    for i in range(0xF0, len(ew) - 4, 4):
        v = struct.unpack_from('<I', ew, i)[0]
        if struct.unpack_from('<I', ew, i - 0xF0)[0] in (0x02050810, 0x050C1020) \
                and 0 < v <= bhp << 10 and v > (bhp << 10) * 2 // 3:
            hpaddr = 0x2000000 + i; break
assert hpaddr, 'boss HP field not found'
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
assert ppos, 'player position not found'
if len(cands) > 1:                                  # an NPC (e.g. Eighteen next to the landing spot) can stand closer:
    xs = {}
    for key in ('RIGHT', 'LEFT'):                  # the player is the one that goes right on RIGHT and left on LEFT
        run(['load _bot', '10 -'] + ['dump _q%d %x 8' % (j, a) for j, a in enumerate(cands)] + ['20 ' + key]
            + ['dump _r%d %x 8' % (j, a) for j, a in enumerate(cands)])
        xs[key] = [struct.unpack('<i', rd('_r%d' % j)[:4])[0] - struct.unpack('<i', rd('_q%d' % j)[:4])[0] for j in range(len(cands))]
    mv = [(xs['RIGHT'][j] - xs['LEFT'][j], a) for j, a in enumerate(cands)]
    if max(mv)[0] > 0: ppos = max(mv)[1]
trace = []; ALL = []      # every key line sent, in order (keys.txt: replay it from the start state to record video)
for k in range(steps):
    run(['load _bot', 'dump _p %x 8' % ppos, 'dump _b %x 8' % pos, 'dump _h %x 4' % hpaddr,
         'dump _c %x 20' % (0x3001560 + 0x68 * ch), 'dump _f 30010db 40'])
    px, py = (v >> 8 for v in struct.unpack('<II', rd('_p'))); bx, by = (v >> 8 for v in struct.unpack('<II', rd('_b')))
    bh = struct.unpack('<I', rd('_h'))[0] >> 10; c = rd('_c'); php = c[0x16] | c[0x17] << 8
    f = rd('_f'); done = f[flag // 8 - 30] >> (flag % 8) & 1
    trace.append((k, php, bh, (px, py), (bx, by)))
    if done or php == 0: break
    dx, dy = bx - px, by - py
    keys = []
    if os.environ.get('RANGED'):                  # a shooter (the drone): line up on the boss's row, then fire at it
        oy = int(os.environ.get('RANGED_DY', '0'))
        if abs(dy + oy) > 6: keys += ['%d %s' % (min(20, abs(dy + oy)), 'DOWN' if dy + oy > 0 else 'UP')]
        elif abs(dx) > 120: keys += ['%d %s' % (min(24, abs(dx) - 100), 'RIGHT' if dx > 0 else 'LEFT')]
        else: keys += ['2 ' + ('RIGHT' if dx > 0 else 'LEFT'), '4 A', '10 -', '4 A', '10 -', '4 A', '16 -']
        run(['load _bot'] + keys + ['save _bot']); ALL.extend(keys); continue
    if abs(dx) > 20 or abs(dy) > 20:
        if abs(dx) > abs(dy): keys += ['%d %s' % (min(24, abs(dx)), 'RIGHT' if dx > 0 else 'LEFT')]
        else: keys += ['%d %s' % (min(24, abs(dy)), 'DOWN' if dy > 0 else 'UP')]
        if min(abs(dx), abs(dy)) < 12: keys += ['4 B', '8 -']
    else:
        face = ('RIGHT' if dx > 0 else 'LEFT') if abs(dx) > abs(dy) else ('DOWN' if dy > 0 else 'UP')
        keys += ['2 ' + face, '4 A', '6 -', '4 A', '6 -', '4 A', '10 -']
    run(['load _bot'] + keys + ['save _bot']); ALL.extend(keys)
print('player hp / boss hp:', trace[::6] + [trace[-1]])
print('RESULT', 'WIN' if done else 'LOSS', 'steps', len(trace), 'player hp', php, 'boss hp', bh)
open(os.path.join(D, 'keys.txt'), 'w').write('\n'.join(ALL))
