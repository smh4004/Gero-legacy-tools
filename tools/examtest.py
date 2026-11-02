"""Examine-spot test: arrive below (or beside) an examine rect, walk into it, press A, screenshot. Unlike listtest this
adds no trigger of its own, so it shows whether the real rect can be reached and fires.
usage: python3 tools/examtest.py <rom> <outdir> <name> <world:area:x:y> <dir UP|DOWN|LEFT|RIGHT> [frames] [preset flag ...]"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import clipcheck as C
rom, S, name, place, d = sys.argv[1:6]; frames = int(sys.argv[6]) if len(sys.argv) > 6 else 60
pre = [int(f) for f in sys.argv[7:]]
W, A_, x, y = (int(v) for v in place.split(':'))
R = C.Rom(open(rom, 'rb').read()); T, hook = C.make_test_rom(R, keep_story=True, keep_enemies=False)
struct.pack_into('<II', T, hook + 16, (1 << 4) | (W << 8) | (A_ << 16) | (1 << 24), (y << 16) | x)
os.makedirs(S, exist_ok=True); open(S + '/et.gba', 'wb').write(T)
FB = 0x30010BD; b = {}
for f in pre: b[FB + f // 8] = b.get(FB + f // 8, 0) | 1 << (f % 8)
l = C.BOOT + ['w8 %x %x' % kv for kv in b.items()] + ['3 DOWN', '200 -'] + \
    (d.split('|') if '|' in d else ['%d %s' % (frames, d)]) + ['20 -', 'shot %s_at' % name, '4 A', '40 -', 'shot %s_a1' % name, '4 A', '50 -', 'shot %s_a2' % name]
C.run(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness'), S + '/et.gba', l, S)
