@ LoG4: per-world master palette.
@ Replaces the body of 0x08007074 (palette fade: r0,r1,r2 = target R,G,B, r3 = amount 0..256) through a
@ bx-pc veneer at its entry. The source palette is WORLDPAL[current world] (world = first byte of the current
@ AreaEntry, pointer at IWRAM 0x03001980), or the original master palette 0x080701B0 when that entry is 0.
@ While the pointer isn't a field area (menus such as Switch Character put something else there) the last field
@ world's palette is used, so act-specific sprite colours stay right on menu screens.
    .equ LASTWORLD, 0x0203FF00   @ EWRAM byte, unused by BF (0x0203FC00-0x0203FFF5 stay zero in every state tested)
    .syntax unified
    .text
    .thumb
    .global fadepal
    .thumb_func
fadepal:
    push {r4, r5, r6, r7, lr}
    ldr  r6, =LASTWORLD          @ last valid field world + 1 (0 = none yet)
    ldr  r4, =0x03001980
    ldr  r4, [r4]
    cmp  r4, #0
    beq  6f
    ldrb r4, [r4]
    cmp  r4, #31
    bhi  6f                      @ menus (e.g. Switch Character) leave a non-area pointer here
    adds r5, r4, #1
    strb r5, [r6]                @ remember this world
    b    7f
6:  ldrb r4, [r6]                @ not in a field area: keep the last field world's palette
    cmp  r4, #0
    beq  1f
    subs r4, #1
7:  ldr  r5, =WORLDPAL
    lsls r4, r4, #2
    ldr  r4, [r5, r4]
    cmp  r4, #0
    bne  2f
1:  ldr  r4, =0x080701B0
2:  movs r5, #0xff
    adds r5, #1
    cmp  r3, r5
    ble  3f
    adds r3, r5, #0
    b    4f
3:  cmp  r3, #0
    bge  4f
    movs r3, #0
4:  muls r2, r3
    adds r7, r2, #0
    muls r0, r3
    muls r1, r3
    mov  lr, r1
    mov  ip, r0
    movs r2, #5
    lsls r2, r2, #24
    movs r0, #1
    subs r1, r5, r3
    lsls r0, r0, #9
5:  ldrb r5, [r4, #1]
    ldrb r3, [r4]
    ldrb r6, [r4, #2]
    muls r5, r1
    add  r5, lr
    muls r3, r1
    add  r3, ip
    asrs r5, r5, #11
    muls r6, r1
    adds r6, r6, r7
    lsls r5, r5, #5
    asrs r3, r3, #11
    orrs r3, r5
    asrs r6, r6, #11
    lsls r5, r6, #10
    orrs r3, r5
    strh r3, [r2]
    adds r2, #2
    adds r4, #3
    subs r0, #1
    bne  5b
    pop  {r4, r5, r6, r7, pc}
    .ltorg
    .align 2
    .global WORLDPAL
WORLDPAL:
    .space 128
