"""Talk test: run an NPC's talk list (the step list in its spawn record) from an A-press trigger at the arrival point
(BF townspeople wander, so walking up to one by fixed inputs is unreliable), twice, screenshotting every dialogue page,
then print the story flags. Preset flags are written into the flag bitfield first (IWRAM 0x30010BD + n/8, bit n%8).
usage: python3 tools/talktest.py <rom> <outdir> <name> <world:area:x:y> <object index> [preset flag ...]
env:   STORY=1 keeps story triggers (clipcheck's test ROM disables them), ROUNDS / SHOTS = talk rounds / pages per round
       (2 / 16), TAIL = extra harness lines after the talk, '|'-separated (e.g. '60 -|130 UP|shot x'); the final
       state is saved as <name>_end.ss in <outdir>.
e.g.   python3 tools/talktest.py log4/out/LoG4.gba /tmp/t herc 4:1:120:400 7 301   (West City, Hercule, fence done)"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import clipcheck as C
rom, S, name, place, obj = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]); pre = [int(f) for f in sys.argv[6:]]
W, A_, x, y = (int(v) for v in place.split(':'))
R = C.Rom(open(rom, 'rb').read()); T, hook = C.make_test_rom(R, keep_story=os.environ.get("STORY") == "1")
FB, BASE = 0x30010BD, 0x08000000
u = lambda o: struct.unpack_from('<I', T, o)[0]
e = R.entry(W, A_)
lst = u(u(e + 0x14) - BASE + 4 * obj) - BASE; talk = u(lst - 8 + 20)
ex = T[e + 3]; old = T[u(e + 0x10) - BASE:u(e + 0x10) - BASE + 8 * ex]
o = len(T); T += struct.pack('<IIHHHHI', 0x0800742D, 0x0800770D, x - 40, y - 40, x + 40, y + 40, talk)
t = len(T); T += old + struct.pack('<II', 0, BASE + o)
T[e + 3] = ex + 1; struct.pack_into('<I', T, e + 0x10, BASE + t)
struct.pack_into('<II', T, hook + 16, (1 << 4) | (W << 8) | (A_ << 16) | (1 << 24), (y << 16) | x)
open(S + '/q2.gba', 'wb').write(T)
l = C.BOOT + ['3 DOWN', '200 -']
bytes_ = {}
for f in pre: bytes_[FB + f // 8] = bytes_.get(FB + f // 8, 0) | 1 << (f % 8)
l += ['w8 %x %x' % kv for kv in bytes_.items()]
k = 0
for rnd in range(int(os.environ.get("ROUNDS", 2))):
    l += ['4 A', '30 -']
    for i in range(int(os.environ.get("SHOTS", 16))): l += ['shot %s_%d_%02d' % (name, rnd, i), '4 A', '40 -']
    l += ['120 -']
l += [x for x in os.environ.get('TAIL', '').split('|') if x] + ['save %s_end' % name, 'shot %s_end' % name, 'dump %s_flags %x 40' % (name, FB + 30)]
C.run(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness'), S + '/q2.gba', l, S)
fl = open(S + '/%s_flags.bin' % name, 'rb').read()
print(name, 'talk list %x' % talk, 'flags', {n: bool(fl[n // 8 - 30] >> (n % 8) & 1) for n in (300, 301, 302, 303)})
