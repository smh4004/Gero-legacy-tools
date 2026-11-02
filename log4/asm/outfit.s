@ Outfit swap (LoG4): BF's Great Saiyaman skill (skill 18) hard-codes Gohan's forms 10 <-> 14. These hooks pick the
@ target by the character's current form: Lapis/17 (forms 9-18) 10 <-> 14, Lazuli/18 (forms 21-25) 21 <-> 23.
@ Assembled at 0x08F7E000 (tools/outfit.py). r5 = character record, r6 = form table (0x086B82EC).
	.syntax unified
	.thumb
	.global hook_in, hook_out
	.align 2
hook_in:                       @ from 0x0801C5F2 (was: movs r0,#14; strb r0,[r5,#0x14]; r0 = table + 14*24)
	ldrb r0, [r5, #0x14]
	movs r1, #14
	cmp r0, #21
	blo 1f
	movs r1, #23
1:	strb r1, [r5, #0x14]
	lsls r0, r1, #1
	adds r0, r0, r1
	lsls r0, r0, #3
	adds r0, r0, r6
	mov r1, lr                 @ lr = 0x0801C5F8 (mov lr,pc at the site; no Thumb bit)
	adds r1, #5                @ -> 0x0801C5FC | 1: the original bl sub_0801711C
	bx r1
	.align 2
hook_out:                      @ from 0x0801C2D2 (was: movs r0,#10; strb; r0 = table + 10*24; bl sub_0801711C)
	push {lr}                  @ lr = 0x0801C2D8
	ldrb r0, [r5, #0x14]
	movs r1, #10
	cmp r0, #21
	blo 1f
	movs r1, #21
1:	strb r1, [r5, #0x14]
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
