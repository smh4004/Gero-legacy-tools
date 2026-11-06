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
    reserve_ewram(rom)
    return at + len(code)


HEAP_WORDS, HEAP_RESERVE = 0x3D738, 0x40


def reserve_ewram(rom):
    """(2026-11-06, user: new game crashed / white and grey screens in Delta and another iPhone emulator) LoG4 keeps
    its RAM words at EWRAM 0x0203FF00-0x0203FFFF (fadepal.s 0x0203FF00, kiregen.s 0x0203FF04-0x0203FF10, the test
    ROMs' guard counter 0x0203FF80). They were thought unused, but BF's heap (init 0x0803D4D0: first block 0x02000800,
    size literal 0x0803D738 = 0xFDFE words, so it runs to 0x0203FFF8) covers them: once it fills that far, BF data
    lands on the Super 17 flash counter (white screen, then a junk BLDCNT: the lab's light layer unblended, grey)
    and LoG4's per-frame writes corrupt BF's blocks (crash). mGBA's timing never filled it that far; VBA-M's did.
    The heap is now 0x40 words shorter (ends 0x0203FEF8), so 0x0203FF00 up is LoG4's alone."""
    assert struct.unpack_from('<I', rom, HEAP_WORDS)[0] == 0xFDFE, 'BF heap size literal changed'
    struct.pack_into('<I', rom, HEAP_WORDS, 0xFDFE - HEAP_RESERVE)
