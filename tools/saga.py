"""Save-slot chapter name (bug found 2026-11-02: every save said "Red Ribbon Science").

The save/load screens show a chapter name under each slot. The slot builder (0x08004BC0) runs the script that
ROM 0x0877CCA4 points at (BF: a packed type-4 record at 0x0877CC50) and stores its result (a UI string index) at
slot +4. BF's script walks a chain of BF story flags (13, 43, 54, 73, 76, 119, 121, 125, 137, 147) and returns
UI 602 + the number of them set. LoG4 never sets those flags, so every save showed UI 602 (chapter 1's name).

LoG4's script checks the chapter-start flags from the newest chapter back and returns that chapter's name
(UI 602-613). It is written unpacked (record byte 2 = 0: code at record + 3) and the pointer is repointed."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenes

PTR = 0x77CCA4
BF_RECORD = 0x0877CC50
# (chapter-start flag, UI name), newest first; set in the chapter's start list (log4/scenes)
CHAPTERS = [(390, 612),   # secret chapter "First Steps" (fs_start)
            (380, 611),   # ch10 "The Last Stand" (ch10_start)
            (360, 610),   # ch9 "Years of Terror"
            (340, 609),   # ch8 "The Massacre"
            (330, 608),   # ch7 "Activation"
            (304, 607),   # ch6 "Taken" (set by the chapter 6 card list)
            (300, 606),   # ch5 "Siblings" (ch5_start)
            (320, 605),   # ch4 "The First Androids"
            (315, 604),   # ch3 "The Boy Called Goku"
            (310, 603)]   # ch2 "An Enemy Bullet"
DEFAULT = 602             # ch1 "Red Ribbon Science"


def push(v): return bytes([0x00, v]) if 0 <= v < 256 else b'\x01' + scenes.enc_varint(v)


def script():
    out = b''
    for flag, ui in CHAPTERS:
        ret = push(ui) + b'\x11'                       # push name; END
        # JZ's s16 (big-endian) counts from its own operand: skip the operand (2) and the return
        out += push(flag) + b'\x02\x1b' + b'\x13' + struct.pack('>h', 2 + len(ret)) + ret
    return out + push(DEFAULT) + b'\x11'


def apply(rom, at):
    assert struct.unpack_from('<I', rom, PTR)[0] == BF_RECORD, 'saga script pointer changed'
    rec = b'\x01\x00\x00' + script()
    assert set(rom[at:at + len(rec)]) <= {0xFF}, 'saga script space not free at %x' % at
    rom[at:at + len(rec)] = rec
    struct.pack_into('<I', rom, PTR, 0x08000000 + at)
    return at + len(rec)


if __name__ == '__main__':
    print(script().hex(' '))
