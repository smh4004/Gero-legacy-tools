"""Sprite frame audit: does every animation frame of every actor fit the OBJ VRAM space its actor reserves?

Why (2026-11-03, the user's trailer v8 report: garbage under everyone's feet at 0:20, the drone vs the Quartermaster):
BF uploads an object's current frame with sub_0800F3F8: memcpy(0x06010000 + obj[+0xC] * 32, obj[+0x44], obj[+0x48])
with obj[+0x48] = frame[6] * frame[7] and no bounds check. The space reserved for the object is obj[+0xE] = its actor
record's u16 at +2, in bytes (sub_0800EB60 allocates it; e.g. 1024 = 32 tiles for a 32x32 8bpp sprite). Before the upload, sub_0800EF94 (0x0800F3B4 loop)
decodes the frame's pieces (12 bytes each from frame+8: w = +2, h = +3, tile data pointer = +8) one after another into
the object's EWRAM buffer obj[+0x40]. So a frame bigger than the reservation writes over the next objects' tiles (the
shared shadow tile sits there) and, at the end of OBJ VRAM, wraps to tile 0; and a garbage "frame" (an animation
played past its frame list, or a slot the actor doesn't have - BF never checks either) does the same with random
sizes, and overruns the EWRAM buffer too.
This audit checks the data side: every frame reachable from every actor's slots must have 1-32 pieces, pointers into
the ROM, tile blocks of type 0/1 whose size word equals the piece's w*h, and frame and piece sizes within the actor's
reservation. tools/framegrd.py is the run-time side (a hook at 0x0800F38C): the same
checks on every frame the engine is about to decode, so a bad one is skipped instead of written over VRAM / EWRAM.
usage: python3 tools/frameaudit.py <rom> [actor table address hex, default C00000]   (exit 1 on any problem)"""
import struct, sys

BASE = 0x08000000


def audit(rom, table=0xC00000):
    u32 = lambda a: struct.unpack_from('<I', rom, a)[0]
    ok = lambda p: BASE <= p < BASE + len(rom)
    problems, actors, frames = [], 0, 0
    i = 1                                  # actor 0 is a dummy record in BF itself (no real slots)
    while True:
        p = u32(table + 4 * i)
        if not ok(p): break
        r = p - BASE; n = rom[r]; alloc = struct.unpack_from('<H', rom, r + 2)[0]   # bytes
        actors += 1
        for s in range(n):
            ap = u32(r + 0x54 + 4 * s)
            if ap == 0: continue
            if not ok(ap): problems.append((i, s, None, 'animation pointer %08X outside the ROM' % ap)); continue
            fc = u32(ap - BASE)
            if not 0 < fc < 256: problems.append((i, s, None, 'frame count %d' % fc)); continue
            for k in range(fc * 4):
                fp = u32(ap - BASE + 4 + 4 * k)
                if fp == 0: continue
                frames += 1
                if not ok(fp): problems.append((i, s, k, 'frame pointer %08X outside the ROM' % fp)); continue
                if fp & 3: problems.append((i, s, k, 'frame pointer %08X not word-aligned' % fp)); continue
                f = fp - BASE; cnt = u32(f); size = rom[f + 6] * rom[f + 7]
                if not 1 <= cnt <= 32: problems.append((i, s, k, '%d pieces' % cnt)); continue
                tot = 0; bad = None
                for q in range(cnt):
                    pc = f + 8 + 12 * q
                    tot += rom[pc + 2] * rom[pc + 3]
                    if not ok(u32(pc + 8)) or u32(pc + 8) & 3: bad = 'piece %d data pointer %08X outside the ROM' % (q, u32(pc + 8))
                    blk = u32(pc + 8) - BASE
                    if not bad and ok(u32(pc + 8)) and (u32(blk) > 1 or u32(blk + 4) != rom[pc + 2] * rom[pc + 3]):
                        bad = 'piece %d tile block type %d / size %d, piece is %d' % (q, u32(blk), u32(blk + 4), rom[pc + 2] * rom[pc + 3])
                if bad: problems.append((i, s, k, bad))
                elif size > alloc or tot > alloc:
                    problems.append((i, s, k, 'frame %d bytes (pieces %d) > reserved %d' % (size, tot, alloc)))
        i += 1
    return actors, frames, problems


if __name__ == '__main__':
    rom = open(sys.argv[1], 'rb').read()
    a, f, pr = audit(rom, int(sys.argv[2], 16) if len(sys.argv) > 2 else 0xC00000)
    print('frameaudit: %d actors, %d frames, %d problems' % (a, f, len(pr)))
    seen = {}
    for i, s, k, msg in pr:
        seen.setdefault((i, msg.split(' ')[0]), []).append((s, k, msg))
    for (i, _), lst in sorted(seen.items())[:60]:
        print('  actor %d: %d frame(s), e.g. slot %s frame %s: %s' % (i, len(lst), lst[0][0], lst[0][1], lst[0][2]))
    sys.exit(1 if pr else 0)
