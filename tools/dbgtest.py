"""Debug-ROM launcher test: boot the debug ROM (New Game -> the debug room 17:120), then walk down into an added walk-in
trigger that runs a debug list (the same list an NPC there runs when talked to) and screenshot what follows.
usage: python3 tools/dbgtest.py <debug rom> <outdir> <name> <list name>
env:   SHOTS = dialogue pages to screenshot (16); TAIL = extra harness lines, '|'-separated."""
import os, sys, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import clipcheck as C
rom, S, name, lname = sys.argv[1:5]
named = json.load(open(os.environ.get('NAMED') or os.path.join(os.path.dirname(os.path.abspath(rom)), 'named_lists_debug.json')))
R = C.Rom(open(rom, 'rb').read()); T = bytearray(R.r); BASE = 0x08000000
u = lambda o: struct.unpack_from('<I', T, o)[0]
e = R.entry(17, 120); ex = T[e + 3]; old = T[u(e + 0x10) - BASE:u(e + 0x10) - BASE + 8 * ex] if ex else b''
T += bytes((-len(T)) % 4)
ax, ay = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'log4', 'debug', 'areas_debug.json')))['arrive']
o = len(T); T += struct.pack('<IIHHHHI', 0x0800742D, 0x080077DF, ax - 16, ay + 14, ax + 40, ay + 44, named[lname])   # just below the arrival
t = len(T); T += old + struct.pack('<II', 0, BASE + o)
T[e + 3] = ex + 1; struct.pack_into('<I', T, e + 0x10, BASE + t)
os.makedirs(S, exist_ok=True); open(S + '/dt.gba', 'wb').write(T)
BOOT = ['30 -', '4 START', '30 -', '4 A'] * 16 + ['30 -', '4 A'] * 110 + ['200 -']   # title, New Game, intro, room text
l = BOOT + ['shot %s_room' % name] + [x for x in os.environ.get('PRE', '').split('|') if x] + ['24 DOWN', '30 -']
for i in range(int(os.environ.get('SHOTS', 16))): l += ['shot %s_%02d' % (name, i), '4 A', '50 -']
l += [x for x in os.environ.get('TAIL', '').split('|') if x] + ['save %s_end' % name, 'shot %s_end' % name,
                                                                'dump %s_area 3001980 4' % name]
C.run(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness'), S + '/dt.gba', l, S)
a = struct.unpack('<I', open(os.path.join(S, name + '_area.bin'), 'rb').read())[0] - BASE
print(name, lname, 'ended in area %d:%d' % (T[a], T[a + 1]) if 0 <= a < len(T) else hex(a))
