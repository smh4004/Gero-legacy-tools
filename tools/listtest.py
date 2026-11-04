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
R = C.Rom(open(rom, 'rb').read()); T, hook = C.make_test_rom(R, keep_story=os.environ.get("STORY") == "1", keep_enemies=os.environ.get("NOENEMIES") != "1")
FB, BASE = 0x30010BD, 0x08000000
u = lambda o: struct.unpack_from('<I', T, o)[0]
e = R.entry(W, A_)
ex = T[e + 3]; old = T[u(e + 0x10) - BASE:u(e + 0x10) - BASE + 8 * ex]
RW = int(os.environ.get('RECT', 40))   # trigger half-size; env RECT (enemysweep: 96, as an area can move the player 40-60 px on arrival)
o = len(T); T += struct.pack('<IIHHHHI', 0x0800742D, 0x0800770D, max(x - RW, 0), max(y - RW, 0), x + RW, y + RW, named[lname])
ONESHOT = 509        # env ONESHOT=1: the injected trigger only fires while flag 509 (free) is clear; the harness sets it
                     # right after the first A press, so later A presses can't start the list again
cond = 0
if os.environ.get('ONESHOT'):          # (2026-11-03) an exit's condition is a script pointer (0x2NNNN only works for
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'log4'))   # enemy records: the
    from areagen import hexcond        # old 0x20000 + flag was a pointer to nowhere and the list ran on every A press)
    cond = BASE + len(T); T += bytes.fromhex(hexcond(('clear', ONESHOT))[4:])
    while len(T) % 4: T += b'\x00'
t = len(T); T += old + struct.pack('<II', cond, BASE + o)
T[e + 3] = ex + 1; struct.pack_into('<I', T, e + 0x10, BASE + t)
struct.pack_into('<II', T, hook + 16, (1 << 4) | (W << 8) | (A_ << 16) | (1 << 24), (y << 16) | x)
os.makedirs(S, exist_ok=True); open(S + '/lt.gba', 'wb').write(T)
bytes_ = {}
for f in pre: bytes_[FB + f // 8] = bytes_.get(FB + f // 8, 0) | 1 << (f % 8)
# preset flags go in BEFORE the DOWN press that warps to the test area, so its arrival events already see them
# (written after the warp, an arrival scene had already started with the flags clear). The bytes are OR-ed into the
# flags the opening left, read once from a boot-only run.
OPENING = {}
if bytes_:
    cache = os.environ.get('BOOTFLAGS') or os.path.join(S, '_bootflags.bin')   # BOOTFLAGS: share one across runs
    if not os.path.exists(cache):
        C.run(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness'), S + '/lt.gba',
              C.BOOT + ['dump _bootflags %x 70' % FB], S)
        if cache != os.path.join(S, '_bootflags.bin'): os.replace(os.path.join(S, '_bootflags.bin'), cache)
    bf_ = open(cache, 'rb').read()
    OPENING = {FB + i: bf_[i] for i in range(len(bf_))}
l = C.BOOT + ['w8 %x %x' % (a, v | OPENING.get(a, 0)) for a, v in bytes_.items()] + ['3 DOWN', '%d -' % int(os.environ.get('ARRIVE', 200))]   # ARRIVE: frames before the A press
l += [x for x in os.environ.get('PRE', '').split('|') if x]      # PRE = harness lines before the A press
l += ['4 A', '30 -']
H_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness')
if os.environ.get('ONESHOT'):
    # (2026-11-03) the area's exits are instantiated in EWRAM when it loads (their conditions are checked then, not per
    # press), so a flag set now can't switch the trigger off: run up to here, find the trigger's rect in its EWRAM copy
    # and move it off the map, then go on from a saved state
    C.run(H_, S + '/lt.gba', l + ['dump _ltew 2000000 40000', 'save _lt1'], S)
    ew_ = open(os.path.join(S, '_ltew.bin'), 'rb').read()
    pat = struct.pack('<HHHH', max(x - RW, 0), max(y - RW, 0), x + RW, y + RW)
    hits = [i for i in range(0, len(ew_) - 8, 2) if ew_[i:i + 8] == pat]
    l = ['1 -', 'load _lt1', 'w8 %x %x' % (FB + ONESHOT // 8, 1 << (ONESHOT % 8))]
    for h in hits: l += ['w8 %x %x' % (0x2000000 + h + k, v) for k, v in enumerate(struct.pack('<4H', 0x7FF0, 0x7FF0, 0x7FF0, 0x7FF0))]   # far off the map
    if not hits: print('listtest: trigger rect not found in EWRAM (ONESHOT can fire again)')
for i in range(int(os.environ.get("SHOTS", 16))): l += ['shot %s_%02d' % (name, i), '4 A', '50 -']
l += [x for x in os.environ.get('TAIL', '').split('|') if x] + ['save %s_end' % name, 'shot %s_end' % name, 'dump %s_flags %x 40' % (name, FB + 30)]
C.run(H_, S + '/lt.gba', l, S)
print(name, 'list', lname, hex(named[lname]))
