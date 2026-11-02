"""Ki recharge per character (log4/asm/kiregen.s): hook at 0x0800E21C into BF's field ki refill."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import outfit
SITE = 0xE21C
ORIG = bytes.fromhex('e0686e30e060000c64d0281c')       # ldr r0,[r4,#0xc]; adds #0x6e; str; lsrs; beq; adds r0,r5,#0


def apply(rom, src, at):
    assert bytes(rom[SITE:SITE + 12]) == ORIG, 'ki refill site changed'
    code, sym = outfit.assemble(src, 0x08000000 + at)
    assert set(rom[at:at + len(code)]) <= {0xFF}, 'kiregen hook space not free'
    rom[at:at + len(code)] = code
    # ldr r1,[pc,#4]; mov lr,pc; bx r1; nop; .word hook|1  (pc at 0x0800E220 -> literal at 0x0800E224)
    rom[SITE:SITE + 12] = bytes.fromhex('0149fe460847c046') + struct.pack('<I', sym['hook_regen'] | 1)
    return at + len(code)
