@ Outfit swap (LoG4): BF's Great Saiyaman skill (skill 18) hard-codes Gohan's forms 10 <-> 14. These hooks step the
@ character to the next form of its outfit cycle instead (tables below, indexed by the current form; 0xFF = no change):
@   Lapis/17:  10 old clothes -> 14 android -> (11 casual -> 12 jacket, once flag 440) -> 10;  Super 17 (15): no change
@   (user 2026-11-03: the gold-haired Super 17 is gone; it looked too much like a Super Saiyan)
@   Lazuli/18: 21 old clothes -> 23 android -> (22 red/yellow -> 24 red/black -> 25 tracksuit, once flag 440) -> 21
@ Flag n = bit n%8 of IWRAM byte 0x030010BD + n/8. BF picks the costume-in or -out animation from form +0x16 (0xFF = out);
@ both hooks pick the same way, so the order is the same whichever animation plays.
@ Assembled at 0x08F7E000 (tools/outfit.py). r5 = character record, r6 = form table (0x086B82EC).
	.syntax unified
	.thumb
	.global hook_in, hook_out
	.align 2
pick:                          @ r0 = current form -> r1 = next form (r0, r2, r3 clobbered)
	ldr r2, =0x030010F4        @ flag 440 (extra outfits): byte 0x030010BD + 55, bit 0
	ldrb r2, [r2]
	ldr r3, =next_plain
	lsls r2, r2, #31
	beq 1f
	ldr r3, =next_all
1:	ldrb r1, [r3, r0]
	cmp r1, #0xFF
	bne 2f
	movs r1, r0
2:	bx lr
hook_in:                       @ from 0x0801C5F2 (was: movs r0,#14; strb r0,[r5,#0x14]; r0 = table + 14*24)
	push {lr}
	ldrb r0, [r5, #0x14]
	bl pick
	strb r1, [r5, #0x14]
	lsls r0, r1, #1
	adds r0, r0, r1
	lsls r0, r0, #3
	adds r0, r0, r6
	pop {r1}                   @ lr = 0x0801C5F8 (mov lr,pc at the site; no Thumb bit)
	adds r1, #5                @ -> 0x0801C5FC | 1: the original bl sub_0801711C
	bx r1
	.align 2
hook_out:                      @ from 0x0801C2D2 (was: movs r0,#10; strb; r0 = table + 10*24; bl sub_0801711C)
	push {lr}                  @ lr = 0x0801C2D8
	ldrb r0, [r5, #0x14]
	bl pick
	strb r1, [r5, #0x14]
	lsls r0, r1, #1
	adds r0, r0, r1
	lsls r0, r0, #3
	adds r0, r0, r6
	ldr r2, =0x0801711D
	bl call_r2
	pop {r1}
	adds r1, #7                @ -> 0x0801C2DE | 1
	bx r1
call_r2:
	bx r2
	.pool
	.align 2
@                    0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
next_plain:
	.byte 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,   14,   10,   10, 0xFF,   10, 0xFF
	.byte 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,   23,   21,   21,   21,   21, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
	.byte 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
next_all:
	.byte 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,   14,   12,   10, 0xFF,   11, 0xFF
	.byte 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,   23,   24,   22,   25,   21, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
	.byte 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
	.align 2

@ Android upgrade: native 165 (remove skill) with skill id 0xF0 (no such skill) raises the character's stats instead.
@ sub_08013ABA(record r0, id r1) starts with a long jump here (0x13ABA); other ids run its first five instructions
@ and go back. Record: +0x16/+0x18 HP/max, +0x1A/+0x1C EP/max, +0x28..+0x2B STR, POW, END, SPD.
	.global hook_rm
	.align 2
hook_rm:
	cmp r1, #0xF0
	beq 3f
	push {r4, r5, r6, r7}
	ldrb r2, [r0, #0xc]
	movs r5, #0
	cmp r2, #0
	ble 2f
	ldr r3, =0x08013AC5
	bx r3
2:	ldr r3, =0x08013B0F
	bx r3
3:	movs r2, r0
	adds r2, #0x28
	ldrb r1, [r2, #0]
	adds r1, #22
	strb r1, [r2, #0]
	ldrb r1, [r2, #1]
	adds r1, #22
	strb r1, [r2, #1]
	ldrb r1, [r2, #2]
	adds r1, #18
	strb r1, [r2, #2]
	ldrb r1, [r2, #3]
	adds r1, #12
	strb r1, [r2, #3]
	ldrh r1, [r0, #0x18]
	adds r1, #230
	strh r1, [r0, #0x18]
	strh r1, [r0, #0x16]
	ldrh r1, [r0, #0x1c]
	adds r1, #70
	strh r1, [r0, #0x1c]
	strh r1, [r0, #0x1a]
	bx lr
	.pool
