@ Ki recharge per character (LoG4). BF's field update (0x0800E21C) only refills ki every ~10 s (accumulator += 0x6E per
@ frame, 3% of max ki when it wraps). This hook adds a fast recharge for the active character (r5 = its record,
@ 0x03001560 + 0x68 * c): the combat drone (character 2) and Seventeen / Eighteen (characters 1 / 3 once flag 306,
@ the conversion, is set; in either outfit) get
@ max(1, max ki / 32) every PERIOD frames (drone 12: full bar in ~6 s; androids 8: ~4 s). Everyone else is unchanged.
@ Then it runs the instructions it replaced and returns to 0x0800E228 (r0 = r5) or 0x0800E2F0 (no BF tick).
@ Entered from 0x0800E21C by: ldr r1,[pc,#4]; mov lr,pc; bx r1; nop; .word hook_regen|1 (12 bytes, to 0x0800E227).
	.syntax unified
	.thumb
	.equ COUNTER, 0x0203FF04          @ EWRAM word, unused by BF (fadepal.s uses 0x0203FF00)
	.global hook_regen
	.align 2
hook_regen:
	ldr r1, =0x03001560
	subs r2, r5, r1
	cmp r2, #0xD0                      @ character 2 = the combat drone
	bne 1f
	movs r3, #12
	b 3f
1:	cmp r2, #0x68                      @ character 1 = Lapis / 17
	beq 2f
	movs r0, #0x9C
	lsls r0, r0, #1                    @ 0x138 = character 3 = Lazuli / 18
	cmp r2, r0
	bne 9f
2:	ldr r0, =0x030010E3                @ flag 306 (the conversion is done) = byte 0x030010BD + 38, bit 2
	ldrb r0, [r0]
	lsls r0, r0, #29
	bpl 9f
	movs r3, #8
3:	ldr r1, =COUNTER
	ldr r0, [r1]
	adds r0, #1
	cmp r0, r3
	blo 4f
	movs r0, #0
	ldrh r2, [r5, #0x1C]               @ max ki
	lsrs r2, r2, #5
	bne 5f
	movs r2, #1
5:	ldrh r3, [r5, #0x1A]               @ ki
	adds r3, r3, r2
	ldrh r2, [r5, #0x1C]
	cmp r3, r2
	bls 6f
	adds r3, r2, #0
6:	strh r3, [r5, #0x1A]
4:	str r0, [r1]
9:	ldr r0, [r4, #0xc]                 @ BF: accumulator += 0x6E; tick when it passes 0x10000
	adds r0, #0x6e
	str r0, [r4, #0xc]
	lsrs r0, r0, #16
	beq 7f
	adds r0, r5, #0
	ldr r1, =0x0800E229
	bx r1
7:	ldr r1, =0x0800E2F1
	bx r1
	.pool
