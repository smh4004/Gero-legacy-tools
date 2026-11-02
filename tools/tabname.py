"""Party tab names after the conversion (log4/asm/tabname.s): characters 1 / 3 read "17" / "18" once flag 306 is set."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import outfit
SITES = {'tab1': (0x14FFE, '48083158e86a012200f0'),    # lsrs r0,r1,#1; ldr r1,[r6,r0]; ldr r0,[r5,#0x2c]; movs r2,#1; bl..
         'tab3': (0x1503A, 'a12080003158e86a0322')}    # movs r0,#0xa1; lsls; ldr r1,[r6,r0]; ldr r0,[r5,#0x2c]; movs r2,#3


def apply(rom, src, at):
    for name, (site, orig) in SITES.items():
        assert bytes(rom[site:site + 10]).hex() == orig, 'tab site %s changed' % name
    code, sym = outfit.assemble(src, 0x08000000 + at)
    assert set(rom[at:at + len(code)]) <= {0xFF}, 'tabname hook space not free'
    rom[at:at + len(code)] = code
    for name, (site, _) in SITES.items():
        lit = (site + 4 + 3) & ~3                                   # first 4-aligned slot after ldr; bx
        assert lit + 4 <= site + 10
        imm = (lit - ((site + 4) & ~3)) // 4
        rom[site:site + 2] = struct.pack('<H', 0x4B00 | imm)        # ldr r3,[pc,#imm*4]
        rom[site + 2:site + 4] = bytes.fromhex('1847')              # bx r3
        for a in range(site + 4, lit, 2): rom[a:a + 2] = bytes.fromhex('c046')
        struct.pack_into('<I', rom, lit, sym[name] | 1)
    return at + len(code)
