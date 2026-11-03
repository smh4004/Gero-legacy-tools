"""LoG4 outfit swap: BF's Great Saiyaman skill (skill 18, UI 1346/1347) re-pointed so Lapis/17 and Lazuli/18 each
toggle between their old clothes and the android outfit (log4/asm/outfit.s), plus form-table names/portraits.

Sites (decomp asm/code_0801B248.s): sub_0801C5CE (costume in, form <- 14) at 0x1C5F2, sub_0801C2AE (costume out,
form <- 10) at 0x1C2D2. Each becomes ldr r1,[pc]; mov lr,pc; bx r1 -> hook (long call; the hooks live past BL range).
Form table 0x6B82EC (24-byte records): +2/+4 name UI ids, +0xE actor idx, +0x10..+0x15 portrait speaker ids, +0x16
transform target, +0x17 revert target. forms.json may also copy a whole record ("copy": form) and set "actor" (LoG4
actor name), "into" (+0x16) and "back" (+0x17)."""
import json, os, struct, subprocess, tempfile
FORMS = 0x6B82EC
SITE_IN, SITE_OUT = 0x1C5F2, 0x1C2D2
SITE_RM = 0x13ABA                  # sub_08013ABA (remove skill): id 0xF0 = android upgrade (log4/asm/outfit.s hook_rm)


def assemble(src, base):
    d = tempfile.mkdtemp()
    o, elf, b = os.path.join(d, 'a.o'), os.path.join(d, 'a.elf'), os.path.join(d, 'a.bin')
    subprocess.run(['arm-none-eabi-as', '-mcpu=arm7tdmi', src, '-o', o], check=True)
    subprocess.run(['arm-none-eabi-ld', '-Ttext=0x%x' % base, o, '-o', elf], check=True, capture_output=True)
    subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', elf, b], check=True)
    syms = subprocess.run(['arm-none-eabi-nm', elf], capture_output=True, text=True, check=True).stdout
    return open(b, 'rb').read(), {l.split()[2]: int(l.split()[0], 16) for l in syms.splitlines() if len(l.split()) == 3}


def apply(rom, src, at, forms_cfg, ids=None):
    assert rom[SITE_IN:SITE_IN + 10] == bytes.fromhex('0e202875301cff305130'), 'costume-in site changed'
    assert rom[SITE_OUT:SITE_OUT + 8] == bytes.fromhex('0a202875301cf030'), 'costume-out site changed'
    code, sym = assemble(src, 0x08000000 + at)
    assert set(rom[at:at + len(code)]) <= {0xFF}, 'outfit hook space not free'
    rom[at:at + len(code)] = code
    # ldr r1,[pc,#4]; mov lr,pc; bx r1; .word hook|1   (site_out also drops the bl that follows: the hook makes the call)
    rom[SITE_IN:SITE_IN + 10] = bytes.fromhex('0149fe460847') + struct.pack('<I', sym['hook_in'] | 1)
    assert rom[SITE_RM:SITE_RM + 10] == bytes.fromhex('f0b4027b0025002a24dd'), 'remove-skill site changed'
    # ldr r2,[pc,#4]; bx r2; nop; .word hook_rm|1  (0x13AC0 is word aligned)
    rom[SITE_RM:SITE_RM + 10] = bytes.fromhex('014a1047c046') + struct.pack('<I', sym['hook_rm'] | 1)
    rom[SITE_OUT:SITE_OUT + 12] = bytes.fromhex('0149fe460847') + struct.pack('<I', sym['hook_out'] | 1) + bytes.fromhex('c046')
    orig = {int(f): bytes(rom[FORMS + 24 * int(c['copy']):FORMS + 24 * int(c['copy']) + 24])
            for f, c in forms_cfg.items() if not f.startswith('_') and 'copy' in c}
    for f, c in forms_cfg.items():
        if f.startswith('_'): continue
        r = FORMS + 24 * int(f)
        if 'copy' in c: rom[r:r + 24] = orig[int(f)]          # whole record of another form (flags, stats link, ...)
        if 'actor' in c:                                     # +0xE actor idx = actor id + 9 (LoG4 actor by name)
            struct.pack_into('<H', rom, r + 0xE, (ids[c['actor']] if isinstance(c['actor'], str) else c['actor']) + 9)
        if 'into' in c: rom[r + 0x16] = c['into']             # transform target (skill 20), 0xFF = none
        if 'back' in c: rom[r + 0x17] = c['back']             # form it reverts to (0xFF = none)
        if 'names' in c: struct.pack_into('<HH', rom, r + 2, *c['names'])
        if 'portraits' in c: rom[r + 0x10:r + 0x16] = bytes((c['portraits'] * 6)[:6])
    return at + len(code)
