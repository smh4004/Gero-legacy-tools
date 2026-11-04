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
	.equ S17DELTA, 0x03001101         @ Super 17's Strength bonus, saved with the game: the flag byte for flags 544-551
	.equ FLASH, 0x0203FF08            @ (2026-11-03) Super 17 white flash: frames left (EWRAM word, unused by BF)
	.equ FLASHLEN, 46                 @ frames (the flash_levels table below)
	.equ FLASHCNT, 0x0203FF0C         @ BLDCNT as it was before the flash (restored at the end)
	.global hook_regen
	.align 2
@ Super 17 (user 2026-11-03: Strength x1.5). While Seventeen (character 1) is in form 15, half his Strength is added on
@ top and remembered in S17DELTA; when he leaves the form (B again, ki ran out, outfit change), the same amount comes
@ off. Checked every frame for the active character only, so a change while 17 is benched is fixed when he's back.
hook_regen:
@ White flash (user 2026-11-03: "like the fusion dance", as Super 13 gets in his cutscene). Started below when Seventeen
@ enters form 15; each frame BLDCNT = brighten BG0-3 + OBJ + backdrop and BLDY = flash_levels[frames left] (0-16),
@ then BLDCNT goes back to the area's own value. BF fades with palettes, so BLDY is otherwise unused.
	ldr r2, =FLASH
	ldr r3, [r2]
	cmp r3, #0
	beq 19f
	subs r3, #1
	str r3, [r2]
	ldr r1, =0x04000050
	cmp r3, #0
	bne 18f
	ldr r0, =FLASHCNT
	ldrh r0, [r0]
	strh r0, [r1]                      @ BLDCNT back
	movs r0, #0
	strh r0, [r1, #4]                  @ BLDY 0
	b 19f
18:	ldr r0, =flash_levels
	ldrb r0, [r0, r3]
	strh r0, [r1, #4]
	movs r0, #0xBF
	strh r0, [r1]
19:
	ldr r1, =0x030015C8                @ character 1's record
	cmp r5, r1
	bne 28f
	ldr r2, =S17DELTA
	ldrb r3, [r2]
	movs r1, #0x28                     @ STR is at +0x28 (ldrb's immediate only reaches 31)
	ldrb r0, [r5, #0x14]               @ current form
	cmp r0, #15
	bne 25f
	cmp r3, #0
	bne 28f                            @ already boosted
	ldrb r0, [r5, r1]                  @ STR
	lsrs r3, r0, #1
	bne 21f
	movs r3, #1
21:	adds r0, r0, r3
	cmp r0, #255
	bls 22f
	movs r0, #255
22:	strb r0, [r5, r1]
	strb r3, [r2]
	ldr r2, =FLASH                     @ he just transformed: start the white flash (not already running)
	ldr r3, [r2]
	cmp r3, #0
	bne 28f
	ldr r0, =0x04000050
	ldrh r0, [r0]
	ldr r1, =FLASHCNT
	strh r0, [r1]
	movs r3, #FLASHLEN
	str r3, [r2]
	b 28f
25:	cmp r3, #0
	beq 28f
	ldrb r0, [r5, r1]
	subs r0, r0, r3
	bcs 26f
	movs r0, #0
26:	strb r0, [r5, r1]
	movs r3, #0
	strb r3, [r2]
28:
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
	.align 2
flash_levels:                          @ BLDY by frames left (time order: a quick strobe, hold white, ~0.4 s fade)
	.byte 0, 1, 2, 2, 3, 4, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 12, 12, 13, 14, 14, 15, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 8, 0, 4, 10, 16, 16, 16, 16, 12, 6
	.align 2
