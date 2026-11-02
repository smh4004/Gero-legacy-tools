"""Unpack BF's type-4 packed step payloads (step-list records whose byte 2 == 4: the VM runner 0x08004098 allocates
4 << 9 bytes and calls the ARM decompressor 0x08049120(dst, record + 4)). Runs the ROM's own routine in unicorn.
usage: python3 tools/unpack4.py rom.gba 0x77cc50 [...]   (ROM offsets of records)"""
import struct, sys
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

DST, STOP = 0x02030000, 0x02020000
import os
IWRAM = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iwram_code.bin'), 'rb').read()


def unpack(rom, rec):
    assert rom[rec + 2] == 4, 'not a packed record'
    mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    mu.mem_map(0x08000000, 0x02000000); mu.mem_write(0x08000000, bytes(rom))
    mu.mem_map(0x02000000, 0x40000); mu.mem_map(0x03000000, 0x8000)
    mu.mem_write(0x03000000, IWRAM[:0x4000])          # IWRAM code (copied there at boot; dump of a running game)
    mu.mem_write(STOP, b'\xfe\xff\xff\xea')            # b . (ARM)
    mu.reg_write(UC_ARM_REG_R0, DST); mu.reg_write(UC_ARM_REG_R1, 0x08000000 + rec + 4)
    mu.reg_write(UC_ARM_REG_SP, 0x03007F00); mu.reg_write(UC_ARM_REG_LR, STOP)
    mu.emu_start(0x08049124, STOP, count=5_000_000)    # ARM entry after the thumb 'bx pc' stub
    return bytes(mu.mem_read(DST, 4 << 9))


if __name__ == '__main__':
    rom = open(sys.argv[1], 'rb').read()
    for a in sys.argv[2:]:
        print(a, unpack(rom, int(a, 16)).hex())
