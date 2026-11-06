"""Per-world master palettes for LoG4 (Buu's Fury base).

The palette fade at 0x08007074 is the routine that copies the 512-colour 24-bit master palette (ROM 0x701B0)
into PAL RAM, scaled toward a fade colour. We swap its body for log4/asm/fadepal.s (same code, but the source is
WORLDPAL[world of the current AreaEntry], falling back to the master palette when the entry is 0). The current
AreaEntry pointer lives at IWRAM 0x03001980; its first byte is the world id.

log4/palettes.json: {"<world id>": {"obj": {"<slot>": [r, g, b], ...}, "bg": {...}}} - overrides on top of the
(already LoG4-patched) master palette. Worlds not listed use the master palette.
"""
import json, os, struct
CODE = 0x9F0000
WORLDPAL_OFF = 0xB4          # address of WORLDPAL in fadepal.bin (arm-none-eabi-nm log4/asm/fadepal.elf); rebuild after
                             # editing fadepal.s: cd log4/asm && arm-none-eabi-as -mthumb fadepal.s -o fadepal.o &&
                             # arm-none-eabi-ld -Ttext=0x089F0000 fadepal.o -o fadepal.elf && arm-none-eabi-objcopy -O binary fadepal.elf fadepal.bin
FADE = 0x7074
MASTER = 0x701B0


def apply(rom, asm_bin, pal_json, worldpal_off=WORLDPAL_OFF):
    """pal_json: path to a palettes.json, or an already-merged dict."""
    code = open(asm_bin, 'rb').read()
    assert len(code) == worldpal_off + 128, 'fadepal.bin: WORLDPAL is not at worldpal_off (rebuilt? see WORLDPAL_OFF)'
    rom[CODE:CODE + len(code)] = code
    # veneer at the old entry: bx pc / nop / (ARM) ldr ip,[pc] / bx ip / .word fadepal|1
    rom[FADE:FADE + 16] = struct.pack('<HHIII', 0x4778, 0x46C0, 0xE59FC000, 0xE12FFF1C, 0x08000000 + CODE + 1)
    table = [0] * 32
    spec = pal_json if isinstance(pal_json, dict) else (json.load(open(pal_json)) if os.path.exists(pal_json) else {})
    cur = CODE + 0x400
    master = bytes(rom[MASTER:MASTER + 1536])
    for w, ov in spec.items():
        if w.startswith('_'): continue
        p = bytearray(master)
        for half, base in (('bg', 0), ('obj', 256)):
            for k, rgb in ov.get(half, {}).items():
                p[(base + int(k)) * 3:(base + int(k)) * 3 + 3] = bytes(rgb)
        rom[cur:cur + 1536] = p; table[int(w)] = 0x08000000 + cur; cur += 1536
    rom[CODE + worldpal_off:CODE + worldpal_off + 128] = struct.pack('<32I', *table)
    return sum(1 for t in table if t)


def night_bg(rom, map_off, master=None):
    """BG overrides that turn a map moonlit: every BG colour the map's tiles use (and no others, so dialogue boxes and
    other BG UI keep their colours) is partly desaturated, darkened and pushed toward blue.
    map_off = ROM offset of the map record (M, the area struct's first word - 4 - BASE)."""
    import numpy as np, maprender
    G = maprender.Game.__new__(maprender.Game); G.rom = bytes(rom); G.base = 0x08000000; G._pages = {}
    used = sorted(set(np.unique(G.tiles(map_off)).tolist()) - {0})
    master = master or bytes(rom[MASTER:MASTER + 768])
    out = {}
    for k in used:
        r, g, b = master[3 * k:3 * k + 3]
        l = 0.30 * r + 0.59 * g + 0.11 * b
        r, g, b = (0.45 * c + 0.55 * l for c in (r, g, b))           # 55% toward grey
        rgb = (r * 0.40, g * 0.48, b * 0.80 + 18)                     # darker, blue moonlight
        out[str(k)] = [max(0, min(255, int(round(c)))) for c in rgb]
    return out
