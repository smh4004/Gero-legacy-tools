"""Ki effect colours for Seventeen and Eighteen (user 2026-11-03: "recolor 17 and 18's ki blasts to blue ... make the
Kamehameha for them both recolored green and rename it to Full Power Energy Wave").

Energy Blast (skill 7): the projectile's frames are raw 8bpp tiles at ROM 0x71300C-0x71370C, picked through the frame
table 0x0871370C (4 directions x 4 records of 12 bytes: s8 dx, s8 dy, u8 w, u8 h, u16 attr0, u16 attr1, u32 tiles).
The same frames are used by every character's blast and by enemy projectiles (sub_08027CBC), so they are not edited:
a blue copy (tiles + table) is written here, and the player projectile's constructor sub_080197B4 is hooked at
0x080197F2 (ldrb r0,[r4,#0x10]; ldr r2,=table ... str r1,[r4,#0x50]) to use the copy when the current character
(G[0] = IWRAM 0x03001068) is 1 or 3 (Lapis / 17, Lazuli / 18; they only get the blast at the conversion). The impact
burst (record 0x087137CC, shared and loaded from a literal) keeps BF's colours.
Electric Kamehameha (skill 6, now "Full Power Energy Wave"): its pieces (0x721218-0x722318: horizontal, vertical,
sparkles) are referenced only by its own frame tables (0x724714-0x7248A0 vertical, 0x724898-0x724A18 horizontal), and in LoG4 only 17 and 18 have the skill, so the
tiles are recoloured in place, green.
Colours: each pixel's colour gets the target hue (same saturation and brightness) and is mapped to the nearest colour
that already exists in the OBJ palette, using only slots whose colour is still BF's (LoG4 put new colours in some
unused slots; slot 255 shows pink in game). The palette itself is not touched."""
import colorsys, json, os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import outfit

BLAST_TILES = (0x71300C, 0x71370C)
BLAST_TABLE, BLAST_RECS = 0x71370C, 16
BEAM_TILES = (0x721218, 0x722318)       # horizontal pieces, vertical pieces (0x721A18-), sparkles (0x722218-)
SITE = 0x197F2
ORIG = bytes.fromhex('207cbc4a41000918090189182165')     # ldrb r0,[r4,#0x10]; ldr r2,=0x0871370C; ... str r1,[r4,#0x50]
BLUE, GREEN = 215 / 360, 125 / 360
# OBJ slots whose in-game colour (PRAM dumped in Act 3 fights, 17:38 and 17:34, 2026-11-03) is not BF's: LoG4's portraits
# and new sprites live there. Never map effect pixels onto them (slot 53 showed pink, 229 dark grey).
IN_GAME_CHANGED = {8, 9, 14, 53, 102, 103, 151, 193, 194, 217, 218, 219, 223, 224, 225, 226, 229, 236, 254, 255}

HOOK = r'''
	.syntax unified
	.thumb
	.global hook_blast
	.align 2
hook_blast:                        @ from 0x080197F2: r4 = new projectile, r0-r3 free; back to 0x08019800
	ldrb r0, [r4, #0x10]           @ direction
	ldr r2, =0x0871370C            @ BF's frames
	ldr r1, =0x03001068            @ G[0] = current character
	ldrb r1, [r1]
	cmp r1, #1
	beq 1f
	cmp r1, #3
	bne 2f
1:	ldr r2, =blue_table
2:	lsls r1, r0, #1
	adds r1, r1, r0
	lsls r1, r1, #4
	adds r1, r1, r2
	str r1, [r4, #0x50]
	ldr r3, =0x08019801
	bx r3
	.pool
	.align 2
blue_table:
	.space %d
'''


def palette():
    return np.array(json.load(open(os.path.join(HERE, 'bf_objpal.json')))['pal'], np.int32)


def rom_objpal(rom):
    v = struct.unpack_from('<256H', rom, 0x5652C)          # the game's RGB555 OBJ palette copy
    return np.array([[(c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3] for c in v], np.int32)


def remap(pal, hue, ok=None):
    """Palette index -> index of the nearest existing colour with the target hue (0 stays 0). ok: allowed targets."""
    hsv = [colorsys.rgb_to_hsv(*(c / 255.0)) for c in pal]
    ok = np.array([i for i in range(1, 255) if ok is None or i in ok])
    out = np.arange(256)
    for i in range(1, 256):
        h, s, v = hsv[i]
        if s < 0.12: continue                        # whites and greys stay (the hot core of the blast)
        r, g, b = colorsys.hsv_to_rgb(hue, s, v)
        want = np.array([r, g, b]) * 255
        d = ((pal[ok] - want) ** 2).sum(1)
        out[i] = int(ok[int(np.argmin(d))])
    return out


def apply(rom, at):
    pal = palette(); cur = rom_objpal(rom)
    same = {i for i in range(256) if tuple(cur[i]) == tuple(pal[i])} - IN_GAME_CHANGED
    blue, green = remap(pal, BLUE, same), remap(pal, GREEN, same)
    # beam: in place
    a, b = BEAM_TILES
    rom[a:b] = bytes(green[np.frombuffer(bytes(rom[a:b]), np.uint8)].astype(np.uint8))
    # blast: hook + table copy (assembled first to learn where blue_table lands), then the recoloured tiles after it
    src = os.path.join(HERE, '..', 'log4', 'out', '_kifx.s')
    open(src, 'w').write(HOOK % (12 * BLAST_RECS))
    code, sym = outfit.assemble(src, 0x08000000 + at)
    assert set(rom[at:at + len(code) + (BLAST_TILES[1] - BLAST_TILES[0])]) <= {0xFF, 0x00}, 'kifx space not free'
    tiles_at = (at + len(code) + 3) & ~3
    t0, t1 = BLAST_TILES
    rom[tiles_at:tiles_at + (t1 - t0)] = bytes(blue[np.frombuffer(bytes(rom[t0:t1]), np.uint8)].astype(np.uint8))
    tab = bytearray(rom[BLAST_TABLE:BLAST_TABLE + 12 * BLAST_RECS])
    for k in range(BLAST_RECS):
        p = struct.unpack_from('<I', tab, 12 * k + 8)[0] - 0x08000000
        assert t0 <= p < t1, hex(p)
        struct.pack_into('<I', tab, 12 * k + 8, 0x08000000 + tiles_at + (p - t0))
    code = bytearray(code)
    bt = sym['blue_table'] - 0x08000000 - at
    code[bt:bt + len(tab)] = tab
    rom[at:at + len(code)] = code
    assert bytes(rom[SITE:SITE + 14]) == ORIG, 'projectile constructor changed'
    # ldr r1,[pc,#4]; bx r1; nop; .word hook|1; nop; nop  (0x080197F2 .. 0x080197FF)
    rom[SITE:SITE + 14] = bytes.fromhex('01490847c046') + struct.pack('<I', sym['hook_blast'] | 1) + bytes.fromhex('c046c046')
    return tiles_at + (t1 - t0)
