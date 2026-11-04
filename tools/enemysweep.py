"""Enemy sweep (2026-11-03): fight every enemy type the game spawns, in its own area, and count
  - frames the sprite guard (tools/framegrd.py) rejects: the enemy asked for an animation slot / frame its sprite
    doesn't have (a behaviour / sprite mismatch: the cause of the garbled shadows in the user's trailer v8 report);
  - animation-slot requests past the end of the actor's slot list (the root cause: the engine then reads the next
    actor's data as an animation - garbage frames, or another character's valid frames).
For each enemy row: the first spawn in log4/areas.json, the flags its spawn condition needs preset, the player dropped
on walkable floor 24-56 px away with the party of that act (the drone / Lapis / Seventeen), then tools/fightbot.py fights it for 60 steps (walks at it, attacks when in reach),
and the guard's reject counter is read from RAM. Needs a test ROM built with --shoot and LOG4_GUARD_COUNTER=0203FF80
(release ROMs have no counter).
usage: python3 tools/enemysweep.py <rom> <outdir> [row ...]      (named_lists.json beside the rom)"""
import json, os, re, struct, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import clipcheck as C, framegrd

ROM, OUT = sys.argv[1], sys.argv[2]
ONLY = {int(x) for x in sys.argv[3:]}
_r = bytearray(open(os.path.join(HERE, '..', 'bf.gba'), 'rb').read()); _, BAD = framegrd.apply(_r, 0xF3B800)
R = C.Rom(open(ROM, 'rb').read())
cfg = json.load(open(os.path.join(HERE, '..', 'log4', 'areas.json')))


def cond_flags(c):
    """Flags that must be SET for a spawn condition (0x1NNNN, or 'hex' text from areagen.hexcond)."""
    if isinstance(c, int): return [c & 0xFFFF] if c >> 16 == 1 else []
    if not isinstance(c, str) or not c.startswith('hex '): return []
    b = bytes.fromhex(c[4:]); out = []; i = 0
    while i < len(b) and b[i] == 1:
        i += 1; v = 0
        while b[i] & 0x80: v = (v << 7) | (b[i] & 0x7F); i += 1
        v = (v << 7) | b[i]; i += 1
        f = v >> 1
        if b[i] == 2 and b[i + 1] == 27: out.append(f)
        i += 2
        if i < len(b) and b[i] == 4: i += 1
    return out


def spot(w, a, x, y):
    m = R.walk_mask(R.map_of(w, a))
    for d in range(24, 60, 4):
        for dx, dy in ((0, d), (0, -d), (d, 0), (-d, 0), (d, d), (-d, d), (d, -d), (-d, -d)):
            X, Y = x + dx, y + dy
            if X < 8 or Y < 8: continue
            if all(C.walkable(m, X + ox, Y + oy) for ox in (2, 14) for oy in (4, 14)): return X, Y
    return None


def rows():
    seen = {}
    for v in cfg['new_areas'] + cfg['areas']:
        for e in v.get('enemies', []):
            key = (e['type'], e.get('character'), e.get('actor'))
            if key not in seen: seen[key] = (v['world'], v['area'], e)
    return seen


COUNTER = 0x0203FF80          # the test ROM's reject counter (build with --shoot and LOG4_GUARD_COUNTER=0203FF80)
STATS = json.load(open(os.path.join(HERE, '..', 'log4', 'stats.json')))['enemies']


def go(item):
    (row, ch, actor), (w, a, e) = item
    name = 'r%d_%s' % (row, actor or ch or 'n')
    d = os.path.join(OUT, name); os.makedirs(d, exist_ok=True)
    p = spot(w, a, e['x'], e['y'])
    if not p: return name, w, a, 'no floor near the spawn', None
    flags = cond_flags(e.get('condition', 0))
    env = dict(os.environ, SHOTS='0', TAIL='30 -', ONESHOT='1', BOOTFLAGS=os.path.join(OUT, '_boot.bin'))
    party, ch = party_for(w, a)
    subprocess.run(['python3', os.path.join(HERE, 'listtest.py'), ROM, d, 's', '%d:%d:%d:%d' % (w, a, p[0], p[1]),
                    party] + [str(f) for f in flags], env=dict(env, TAIL='4 A|40 -|4 A|40 -|4 A|60 -'), capture_output=True)
    if not os.path.exists(os.path.join(d, 's_end.ss')): return name, w, a, 'no state', None
    hp = STATS.get(str(row), {}).get('hp')
    if not hp: return name, w, a, 'no hp in stats.json', None
    r = subprocess.run(['python3', os.path.join(HERE, 'fightbot.py'), os.path.join(d, 'lt.gba'), d, 's_end', str(hp), '543', str(ch),
                        str(STEPS), str(p[0]), str(p[1])], env=dict(os.environ, ANYMARK='1'), capture_output=True, text=True)
    res = (r.stdout + r.stderr).strip().split('\n')[-1][:60]
    open(os.path.join(d, '_c.txt'), 'w').write('1 -\nload _bot\ndump _cnt %x 4\n' % COUNTER)
    subprocess.run([os.path.join(HERE, 'harness'), os.path.join(d, 'lt.gba'), os.path.join(d, '_c.txt'), d], capture_output=True)
    cp = os.path.join(d, '_cnt.bin')
    n = struct.unpack('<I', open(cp, 'rb').read())[0] if os.path.exists(cp) else None
    return name, w, a, res, n


STEPS = 60
ACT3_LAB = {111, 112, 115, 116, 117, 80, 81, 82, 83}


def party_for(w, a):
    """The party the player has in that area: the drone in Act 1, Lapis in Act 2, Seventeen in Act 3 (shoot lists sw_*)."""
    if w == 1 and a not in ACT3_LAB: return 'sw_drone', 2
    if w in (4, 16): return 'sw_lapis', 1
    return 'sw_17', 1


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    items = [i for i in rows().items() if not ONLY or i[0][0] in ONLY]
    # one boot first so the boot-flag cache exists before the parallel runs
    first = go(items[0]); print(first, flush=True)
    with ThreadPoolExecutor(6) as ex:
        for r in ex.map(go, items[1:]): print(r, flush=True)
