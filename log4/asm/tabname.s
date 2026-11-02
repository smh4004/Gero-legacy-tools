@ Party tabs on the Status / Inventory / Skills / Journal screens (LoG4). BF draws each party member's tab with a fixed
@ UI string, 158 + character (0x08014FE0-0x080150D4: ldr r1,[r6,#4*(158+c)] with r6 = the UI pointer table, then
@ 0x08015FFC(list = [r5+0x2C], text, tab = c)). After the conversion (flag 306) characters 1 and 3 are Seventeen and
@ Eighteen, so their tabs say "17" / "18" (UI 1707 / 1708) instead of Lapis / Lazuli (UI 159 / 161).
@ Entered from 0x08014FFE (character 1, returns to 0x0801500A) and 0x0801503A (character 3, returns to 0x08015048) by
@ ldr r3,[pc,#4]; bx r3; nop; .word tab1|1 (or tab3|1).
	.syntax unified
	.thumb
	.global tab1
	.global tab3
	.align 2
tab1:
	ldr r0, =4*159
	ldr r1, =4*1707
	movs r2, #1
	bl pick
	ldr r3, =0x0801500B
	bx r3
tab3:
	ldr r0, =4*161
	ldr r1, =4*1708
	movs r2, #3
	bl pick
	ldr r3, =0x08015049
	bx r3
@ r0 = offset of the human name, r1 = offset of the android name, r2 = tab; r5 / r6 as in BF's code
pick:
	push {lr}
	ldr r3, =0x030010E3                @ flag 306 = byte 0x030010BD + 38, bit 2
	ldrb r3, [r3]
	lsls r3, r3, #29
	bpl 1f
	adds r0, r1, #0
1:	ldr r1, [r6, r0]
	ldr r0, [r5, #0x2C]
	ldr r3, =0x08015FFD
	bl 2f
	pop {r3}
	bx r3
2:	bx r3
	.ltorg
