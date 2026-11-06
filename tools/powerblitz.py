"""Power Blitz (Seventeen) / Infinity Bullet (Eighteen): a rapid-fire ki blast skill (user 2026-11-05: "a rapid fire ki
blast attack, I want 18 to have a pink version and 17 to have a blue version"; "call Android 18's power blitz
'Infinity Bullet' ... nothing different from 17's version aside from color and name").

BF's Energy Blast (skill 7): use = 0x08019F72 (EP cost = max EP * 0xCCD >> 16, then a 12-byte action of class
0x0804DC14 on the player object, animation state 3). The action's update sub_0801AF3C counts the player object's +0x12
each frame: at 16 it fires (sub_0800FF44 + sub_08019858(buf, obj, 1): the player projectile, sub_080197B4); from 40 on
it fires again only on a new B press (+0x11 = 3 - hand, counter back to 16), else it ends (vtable +0x28).
The new skill copies that with its own update: after the first blast it fires every GAP frames for as long as B is
HELD (the input getter's +2 bit 1; +4 is the new-press bit Energy Blast uses), each blast costing max EP * COST >> 16,
and ends when B is let go or EP runs out. Its blasts are the Energy Blast projectile, so tools/kifx.py's hook colours
them per twin (17 blue, 18 pink).
Skill ids: 22 (BF Super Saiyan 3, UI 1350/1351) = Power Blitz and 21 (an unused copy of Super Saiyan's record) =
Infinity Bullet, given UI 1352/1353 (BF's Ultra Volleyball Attack strings: skill 23, which only Gotenks, character 5,
starts with; LoG4 never plays him). Not 23 itself: the table at 0x71DB04 ends inside record 23 (its last 8 bytes are a
literal pool: 0x03001C4C, 0x03001068); writing it broke other skills (2026-11-05, found in testing). No LoG4
character has 21 or 22. Same record for both apart from the name (renamed in log4/text/ui.txt). The twins get them at
the conversion (act2_siblings.scene)."""
import os, struct
import outfit

SKILLS = 0x71DB04                       # 24-byte records: [u16 name UI, u16 desc UI][usable][use][u32][icon][icon]
BLAST_ID, IDS = 7, {22: (1350, 1351), 21: (1352, 1353)}     # id: (name UI, description UI)
VTABLE, VT_N = 0x4DC14, 9               # Energy Blast's action class (relative entries: target + 1 - table)
GAP = 6                                 # frames between blasts while B is held
COST = 0x666                            # EP per blast: max EP * COST >> 16 (2.5 %; Energy Blast: 0xCCD = 5 %)

ASM = r'''
	.syntax unified
	.thumb
	.global pb_use
	.global pb_update
	.global pb_vtable
	.align 2
pb_use:                             @ r0 = character record, r1 = player object (as Energy Blast's 0x08019F72)
	push {r4, r5, r6, lr}
	adds r5, r1, #0
	adds r4, r0, #0
	movs r0, #0x1c
	ldrsh r0, [r4, r0]              @ max EP
	ldr r3, =%(cost)d
	muls r0, r3, r0
	ldr r1, =0xFFFF
	adds r0, r0, r1
	asrs r1, r0, #16
	adds r0, r4, #0
	ldr r3, =0x08013599             @ take the EP
	bl via_r3
	ldrb r0, [r4, #0x15]            @ the selected skill's level byte
	lsls r0, r0, #1
	adds r0, r0, r4
	adds r0, #0x2e
	ldrb r6, [r0]
	movs r0, #0xc
	ldr r3, =0x0803D5B9             @ new 12-byte action
	bl via_r3
	cmp r0, #0
	beq 1f
	ldr r1, =pb_vtable
	str r1, [r0]
	movs r1, #0
	strb r1, [r0, #4]
	str r6, [r0, #8]
1:	adds r6, r0, #0
	movs r1, #3
	adds r0, r5, #0
	ldr r3, =0x0800ECDB             @ animation state 3 (Energy Blast's throw)
	bl via_r3
	adds r1, r6, #0
	adds r0, r5, #0
	ldr r3, =0x0800ED19             @ attach the action
	bl via_r3
	pop {r4, r5, r6}
	pop {r0}
	bx r0

pb_update:                          @ r0 = action, r1 = player object
	push {r4, r5, r6, r7, lr}
	sub sp, #0x20
	adds r7, r0, #0
	adds r4, r1, #0
	ldrh r0, [r4, #0x12]
	adds r0, #1
	lsls r0, r0, #16
	lsrs r0, r0, #16
	strh r0, [r4, #0x12]
	cmp r0, #%(next)d
	bhs 2f
	cmp r0, #16
	bne 9f
	movs r0, #1                     @ the first blast
	strb r0, [r4, #0x11]
	b 5f
2:	ldr r1, [r4]                    @ B still held? (input +2 bit 1)
	movs r2, #0x84
	ldr r2, [r2, r1]
	adds r1, r2, r1
	adds r0, r4, #0
	bl via_r1
	ldrh r0, [r0, #2]
	lsls r0, r0, #30
	bpl 8f
	ldr r1, [r4]                    @ the character record
	movs r2, #0x80
	ldr r2, [r2, r1]
	adds r1, r2, r1
	adds r0, r4, #0
	bl via_r1
	adds r5, r0, #0
	movs r0, #0x1c
	ldrsh r0, [r5, r0]
	ldr r3, =%(cost)d
	muls r0, r3, r0
	ldr r1, =0xFFFF
	adds r0, r0, r1
	asrs r6, r0, #16
	adds r0, r5, #0
	adds r1, r6, #0
	ldr r3, =0x080134B9             @ enough EP?
	bl via_r3
	cmp r0, #0
	beq 8f
	adds r0, r5, #0
	adds r1, r6, #0
	ldr r3, =0x08013599             @ take it
	bl via_r3
	ldrb r0, [r4, #0x11]            @ the other hand
	movs r1, #3
	subs r0, r1, r0
	strb r0, [r4, #0x11]
	movs r0, #16
	strh r0, [r4, #0x12]
5:	mov r0, sp                      @ fire
	adds r1, r4, #0
	ldr r3, =0x0800FF45
	bl via_r3
	mov r0, sp
	adds r1, r4, #0
	movs r2, #1
	ldr r3, =0x08019859
	bl via_r3
	b 9f
8:	ldr r1, [r4]                    @ done: end the action (vtable +0x28)
	movs r2, #0x28
	ldr r2, [r2, r1]
	adds r2, r2, r1
	adds r0, r4, #0
	movs r1, #0
	bl via_r2
9:	add sp, #0x20
	pop {r4, r5, r6, r7}
	pop {r0}
	bx r0
via_r1:	bx r1
via_r2:	bx r2
via_r3:	bx r3
	.pool
	.align 2
pb_vtable:
	.space %(vt)d
'''


def apply(rom, at):
    at = (at + 3) & ~3
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'log4', 'out', '_powerblitz.s')
    open(src, 'w').write(ASM % {'cost': COST, 'next': 16 + GAP, 'vt': 4 * VT_N})
    code, sym = outfit.assemble(src, 0x08000000 + at)
    assert set(rom[at:at + len(code)]) <= {0xFF, 0x00}, 'power blitz space not free'
    code = bytearray(code)
    vt = sym['pb_vtable']
    for k in range(VT_N):                                   # the class, its entries relative to the new table
        rel = struct.unpack_from('<i', rom, VTABLE + 4 * k)[0]
        target = 0x08000000 + VTABLE + rel
        if k == 1: target = sym['pb_update'] | 1
        struct.pack_into('<i', code, vt - 0x08000000 - at + 4 * k, target - vt)
    rom[at:at + len(code)] = code
    blast = bytearray(rom[SKILLS + 24 * BLAST_ID:SKILLS + 24 * BLAST_ID + 24])
    assert struct.unpack_from('<I', blast, 8)[0] == 0x08019F73, 'Energy Blast use moved'
    assert struct.unpack_from('<HH', rom, SKILLS + 24 * 22) == (1350, 1351), 'skill 22 is not BF Super Saiyan 3'
    for i, (nm, ds) in IDS.items():
        rec = bytearray(blast)
        struct.pack_into('<HH', rec, 0, nm, ds)                                     # its own name / description
        struct.pack_into('<I', rec, 8, sym['pb_use'] | 1)
        rom[SKILLS + 24 * i:SKILLS + 24 * i + 24] = rec
    return at + len(code)
