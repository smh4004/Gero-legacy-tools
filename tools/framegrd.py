"""Sprite frame guard (2026-11-03): BF never checks an animation slot against the actor's slot count, nor a frame number
against the animation's frame count, so an enemy whose behaviour plays a slot or frame its sprite doesn't have
(e.g. the Quartermaster: BF's Grenadier sprite with the fighter behaviour 0x8A) hands the frame decoder a garbage
"frame". The decoder then copies its pieces into the object's EWRAM buffer and uploads w*h bytes to the object's OBJ
VRAM tiles with no size check (sub_0800F3F8), writing over the following objects' tiles (the shared shadow tile, the
HUD) and wrapping to tile 0 - the garbage under everyone's feet in the user's trailer v8 report.
This hook sits where sub_0800EF94 takes a new frame (0x0800F38C: str r0,[r4,#0x30]; ldrb w; ldrb h; muls; str len)
and only lets a frame through if it looks like every real frame in the game does (tools/frameaudit.py checks the data):
  - the frame record is in the ROM and word-aligned, with 1-32 pieces;
  - its size w*h and the sum of its pieces fit the object's reserved OBJ VRAM (obj+0xE, in bytes);
  - every piece's tile block is in the ROM, word-aligned, of type 0 (raw) or 1 (compressed), and its size word equals
    the piece's w*h (true for all 28,356 pieces in LoG4 and BF).
Anything else is skipped exactly like an unchanged frame (return 0: nothing decoded, nothing uploaded), so the object
keeps showing its last good frame."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import outfit

SITE = 0xF38C
ORIG = bytes.fromhex('20638279c1794a43a264')          # str r0,[r4,#0x30]; ldrb r2,[r0,#6]; ldrb r1,[r0,#7]; muls r2,r1; str r2,[r4,#0x48]

HOOK = r'''
	.syntax unified
	.thumb
	.global hook_frame
	.align 2
hook_frame:                        @ from 0x0800F38C: r0 = new frame record, r4 = object; r1-r3, r5-r7 free
	str r0, [r4, #0x30]
	lsls r1, r0, #30               @ word-aligned
	bne bad
	lsrs r1, r0, #25               @ 0x08000000-0x09FFFFFF
	cmp r1, #4
	bne bad
	ldrh r5, [r4, #0xe]            @ reserved OBJ VRAM in bytes (the actor record's u16 at +2)
	ldrb r2, [r0, #6]
	ldrb r1, [r0, #7]
	muls r2, r1
	cmp r2, r5
	bhi bad
	ldr r6, [r0]                   @ piece count 1..32
	subs r1, r6, #1
	cmp r1, #31
	bhi bad
	adds r7, r0, #0                @ pieces: 12 bytes each from frame+8, w +2, h +3, tile block +8
	adds r7, #8
	movs r3, #0
1:	ldrb r1, [r7, #2]
	ldrb r2, [r7, #3]
	muls r1, r2                    @ piece size
	adds r3, r3, r1
	ldr r2, [r7, #8]               @ tile block: [u32 type 0/1][u32 size = w*h]
	lsls r0, r2, #30
	bne bad
	lsrs r0, r2, #25
	cmp r0, #4
	bne bad
	ldr r0, [r2]
	cmp r0, #1
	bhi bad
	ldr r0, [r2, #4]
	cmp r0, r1
	bne bad
	adds r7, #12
	subs r6, #1
	bne 1b
	cmp r3, r5
	bhi bad
	ldr r0, [r4, #0x30]            @ good: the original instructions, back to 0x0800F396
	ldrb r2, [r0, #6]
	ldrb r1, [r0, #7]
	muls r2, r1
	str r2, [r4, #0x48]
	ldr r3, =0x0800F397
	bx r3
	.global hook_frame_bad
bad:                               @ like an unchanged frame: movs r0,#0; b epilogue (0x0800F388). Tests watch this PC.
hook_frame_bad:
@COUNTER@
	ldr r3, =0x0800F389
	bx r3
	.pool
'''
COUNT = '''	ldr r3, =0x%08X               @ test builds only (LOG4_GUARD_COUNTER): count rejected frames
	ldr r0, [r3]
	adds r0, #1
	str r0, [r3]'''


def apply(rom, at, counter=None):
    """Assemble the hook at ROM offset `at` and patch the call site. `counter`: a RAM word to count rejects in (test
    ROMs only, e.g. 0x0203FF80; release builds never pass it). Returns (end offset, address of the reject
    branch, for tests: tools/tracer <rom> <state> <keys> <steps> p<addr> counts rejected frames)."""
    assert bytes(rom[SITE:SITE + 10]) == ORIG, 'frame decoder changed at 0x0800F38C'
    src = os.path.join(HERE, '..', 'log4', 'out', '_framegrd.s')
    open(src, 'w').write(HOOK.replace('@COUNTER@', COUNT % counter if counter else ''))
    code, sym = outfit.assemble(src, 0x08000000 + at)
    assert set(rom[at:at + len(code)]) <= {0xFF, 0x00}, 'framegrd space not free'
    rom[at:at + len(code)] = code
    # ldr r1,[pc,#0]; bx r1; .word hook|1; nop   (0x0800F38C .. 0x0800F395)
    rom[SITE:SITE + 10] = bytes.fromhex('00490847') + struct.pack('<I', sym['hook_frame'] | 1) + bytes.fromhex('c046')
    return at + len(code), sym['hook_frame_bad']
