"""Level-up crash fix (user report 2026-11-02: "Energy attack level requested for attack which doesn't exist for
player!" after a kill). BF's level-up event (0x0877C9E8, steps at 0x0877C6D8..) checks, for the levelling character,
the attack levels of two BF moves per character (char 0: 14/15, 1: 17/6, 2: 16/8, 3: 4/11, 4: 10/2) with native 0xEA
(sub_08013BCC) at levels 25/50/75/100, then teaches "X learned Y Level 2". The VM has no short-circuit, so 0xEA runs on
every level-up, and LoG4's characters no longer have those moves (Gero [7], drone [7, 8], human twins [8], androids
without Masenko / Flame Kamehameha) -> assertion. Fix: each `pushn 2 (char, skill); call 0xEA` (6 bytes) becomes
`push 0; pop; push 69` (attack level 69 = already learned, so no BF move-upgrade lines with Goku's / Gohan's names),
and the two asserts in natives 0xE9 / 0xEA (BL 0x0803DF14 at 0x08013B94 / 0x08013BFA) become NOPs as a safety net."""
import re, struct

SCRIPT_LO, SCRIPT_HI = 0x77C600, 0x77CA00
NEW = bytes.fromhex('00 00 14 01 81 0a')
ASSERT_BLS = (0x13B94, 0x13BFA)


def apply(rom):
    seg = bytes(rom[SCRIPT_LO:SCRIPT_HI])
    hits = [SCRIPT_LO + m.start() for m in re.finditer(rb'\x1d\x02..\x02\xea', seg, re.S)]
    assert len(hits) == 18, 'level-up script changed: %d attack-level checks' % len(hits)
    for a in hits: rom[a:a + 6] = NEW
    for a in ASSERT_BLS:
        h1, h2 = struct.unpack_from('<HH', rom, a)
        assert h1 >> 11 == 0x1E and h2 >> 11 == 0x1F, 'not a BL at %x' % a
        struct.pack_into('<HH', rom, a, 0x46C0, 0x46C0)      # mov r8, r8 (nop) x2
    return len(hits)
