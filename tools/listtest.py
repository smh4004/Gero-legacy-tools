"""List test: run any named step list (log4/out/named_lists.json) from an A-press trigger at an arrival point, so a
chapter can be played from a fresh boot without savestates (states made with older builds break: the current
AreaEntry pointer and running script pointers move between builds). Preset flags are written first.
usage: python3 tools/listtest.py <rom> <outdir> <name> <world:area:x:y> <list name> [preset flag ...]
env:   SHOTS = dialogue pages to screenshot after the A press (16); TAIL = extra harness lines, '|'-separated; the final
       state is saved as <name>_end.ss in <outdir>.
e.g.   SHOTS=40 python3 tools/listtest.py log4/out/LoG4.gba /tmp/t fs 1:1:112:200 fs_start"""
import os, sys, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import clipcheck as C
rom, S, name, place, lname = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]; pre = [int(f) for f in sys.argv[6:]]
W, A_, x, y = (int(v) for v in place.split(':'))
named = json.load(open(os.environ.get('NAMED') or os.path.join(os.path.dirname(os.path.abspath(rom)), 'named_lists.json')))
R = C.Rom(open(rom, 'rb').read()); T, hook = C.make_test_rom(R, keep_story=os.environ.get("STORY") == "1", keep_enemies=True)
FB, BASE = 0x30010BD, 0x08000000
u = lambda o: struct.unpack_from('<I', T, o)[0]
e = R.entry(W, A_)
ex = T[e + 3]; old = T[u(e + 0x10) - BASE:u(e + 0x10) - BASE + 8 * ex]
o = len(T); T += struct.pack('<IIHHHHI', 0x0800742D, 0x0800770D, x - 40, y - 40, x + 40, y + 40, named[lname])
t = len(T); T += old + struct.pack('<II', 0, BASE + o)
T[e + 3] = ex + 1; struct.pack_into('<I', T, e + 0x10, BASE + t)
struct.pack_into('<II', T, hook + 16, (1 << 4) | (W << 8) | (A_ << 16) | (1 << 24), (y << 16) | x)
os.makedirs(S, exist_ok=True); open(S + '/lt.gba', 'wb').write(T)
l = C.BOOT + ['3 DOWN', '200 -']
bytes_ = {}
for f in pre: bytes_[FB + f // 8] = bytes_.get(FB + f // 8, 0) | 1 << (f % 8)
l += ['w8 %x %x' % kv for kv in bytes_.items()]
l += [x for x in os.environ.get('PRE', '').split('|') if x]      # PRE = harness lines before the A press
l += ['4 A', '30 -']
for i in range(int(os.environ.get("SHOTS", 16))): l += ['shot %s_%02d' % (name, i), '4 A', '50 -']
l += [x for x in os.environ.get('TAIL', '').split('|') if x] + ['save %s_end' % name, 'shot %s_end' % name, 'dump %s_flags %x 40' % (name, FB + 30)]
C.run(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness'), S + '/lt.gba', l, S)
print(name, 'list', lname, hex(named[lname]))
