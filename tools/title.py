"""Title screen: replace Buu's Fury's title picture with log4/art/raw/U1_title.png (the user's Gero's Legacy screenshot).

How the title works (decoded 2026-10-31, see RE_NOTES "Title screen"):
  - The picture is a linear 240x160 8bpp bitmap in a WFZ container (0x3BE3D4, size 0x9600). The title code decompresses
    it to EWRAM and an IWRAM routine (0x030003BC) cuts it into 600 BG1 tiles. Bitmap literals: 0x5414 (title setup) and
    0x1E744 / 0x1E9E0 (other title entry points).
  - Palette: 0x080053CC copies the 256-colour palette at literal 0x5458 (= 0x5652C, shared by the splash, legal and other
    front-end screens) into the BG and OBJ palettes. A new palette is written and only that literal is repointed; every
    index used by the other front-end bitmaps and by the menu drawn over the title keeps its colour.
  - Menus: START/OPTIONS (0x08005228) and STORY/VERSUS (0x0801E4E0) items are made with centre (x, y) = (0x78, 0x78) and
    (0x78, 0x86). The new art has a bar at the bottom, so both menus are moved side by side into it, and the darkened
    menu box is switched off (identity lookup table).
"""
import os, struct, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import unpack

BASE = 0x08000000
OLD_BITMAP = 0x3BE3D4
BITMAP_LITERALS = (0x5414, 0x1E744, 0x1E9E0)
PAL_LITERAL, OLD_PAL = 0x5458, 0x5652C
FRONT_END_BITMAPS = (0x55620, 0x6F9EC8, 0x6FA398, 0x6FABF4, 0x7319E0, 0x732384, 0x732604)
MENU_OVERLAY = [1, 2, 6, 16, 17, 24, 25, 28, 30, 31, 32, 62, 64, 65, 77, 78, 79, 80, 93, 109, 110, 111, 112, 113, 114,
                115, 127, 138, 204, 208]     # indices the menu draws over the title (measured in the emulator)
# menu item centres: instruction addresses (movs rX, #imm) for item 1 x, item 1 y, item 2 x, item 2 y
# The bar in the art spans x 47-193, y 140-154; an item's text sits 3 px above its y, the cursor 31-15 px left of its x.
# Item x 86 / 166 balance [cursor + START] ... [OPTIONS] in the bar (8 px margins); y 150 centres the text vertically.
MENU_IMMS = {0x524A: 86, 0x5256: 150, 0x5284: 166, 0x5294: 150,             # START / OPTIONS
             0x1E4EE: 86, 0x1E502: 150, 0x1E52E: 166, 0x1E53E: 150}        # STORY / VERSUS (UI 3/4, shortened)
# The menu box darkens the picture through an index lookup table (0x56A2C, built for the old palette; IWRAM 0x0300031C).
# The new art has its own bar, so the title's three entry points get an identity table: no box is drawn.
LUT_LITERALS = (0x5418, 0x1E748, 0x1E9E4)
OLD_LUT = 0x56A2C


def to15(rgb): return (rgb >> 3).astype(np.int64)


def build(rom, art_path):
    """-> (bitmap bytes 240*160, palette bytes 512)."""
    pal = np.frombuffer(bytes(rom[OLD_PAL:OLD_PAL + 512]), '<u2').astype(np.int64)
    old = np.frombuffer(bytes(unpack(rom, OLD_BITMAP)[0]), np.uint8)
    keep = {0} | set(MENU_OVERLAY)
    for o in FRONT_END_BITMAPS: keep |= set(np.frombuffer(bytes(unpack(rom, o)[0]), np.uint8).tolist())
    slots = [i for i in range(1, 256) if i not in keep]
    img = Image.open(art_path).convert('RGB').resize((240, 160), Image.BOX)
    q = img.quantize(colors=len(slots), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qp = np.array(q.getpalette()[:3 * len(slots)], np.int64).reshape(-1, 3)
    newpal = pal.copy()
    for s, c in zip(slots, qp):
        c5 = c >> 3; newpal[s] = c5[0] | (c5[1] << 5) | (c5[2] << 10)
    # map every pixel to the nearest of all usable entries (fixed ones included), in 5-bit RGB
    cand = [i for i in range(1, 256)]
    crgb = np.stack([newpal[cand] & 31, (newpal[cand] >> 5) & 31, (newpal[cand] >> 10) & 31], 1)
    px = to15(np.array(img).reshape(-1, 3))
    best = np.zeros(len(px), np.int64); bestd = np.full(len(px), 1 << 40)
    for j, c in enumerate(crgb):
        d = ((px - c) ** 2).sum(1); m = d < bestd; best[m] = j; bestd[m] = d[m]
    bmp = np.array(cand, np.uint8)[best]
    return bmp.tobytes(), newpal.astype('<u2').tobytes(), len(slots)


def apply(rom, art_path, at):
    bmp, pal, n = build(rom, art_path)
    cur = at
    def put(data):
        nonlocal cur
        a = cur; rom[a:a + len(data)] = data; cur = (a + len(data) + 3) & ~3
        return BASE + a
    b = put(struct.pack('<II', 0, len(bmp)) + bmp)
    p = put(pal)
    for lit in BITMAP_LITERALS:
        assert struct.unpack_from('<I', rom, lit)[0] == BASE + OLD_BITMAP
        struct.pack_into('<I', rom, lit, b)
    assert struct.unpack_from('<I', rom, PAL_LITERAL)[0] == BASE + OLD_PAL
    struct.pack_into('<I', rom, PAL_LITERAL, p)
    lut = put(bytes(range(256)))
    for lit in LUT_LITERALS:
        assert struct.unpack_from('<I', rom, lit)[0] == BASE + OLD_LUT
        struct.pack_into('<I', rom, lit, lut)
    for addr, imm in MENU_IMMS.items():
        assert rom[addr + 1] & 0xF8 == 0x20, 'expected movs rX, #imm at %x' % addr
        rom[addr] = imm
    return cur, n


# ---------- legal screen (front-end bitmap 0x55620, literal 0x4EFC; BG palette at 0x5652C, grey ramp below) ----------
LEGAL_BITMAP, LEGAL_LITERAL = 0x55620, 0x4EFC
LEGAL_GREYS = [(0, 1), (40, 111), (56, 112), (80, 113), (120, 115), (144, 116), (192, 118), (216, 119), (248, 2)]
LEGAL_TITLE = "Dragon Ball Z: Gero's Legacy"


def legal_bitmap(rom, title=LEGAL_TITLE):
    """The legal text screen with its first line (the game's name, rows 36-49) redrawn: Liberation Sans 9.6 px with a
    1/4 px stroke (rendered at 4x, box-filtered down: matches the original's weight), mapped to the screen's grey ramp."""
    from PIL import ImageDraw, ImageFont
    a = np.frombuffer(bytes(unpack(rom, LEGAL_BITMAP)[0]), np.uint8).reshape(160, 240).copy()
    S = 4
    f = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', int(9.6 * S))
    im = Image.new('L', (240 * S, 14 * S), 0); d = ImageDraw.Draw(im)
    w = d.textlength(title, font=f) + 2
    d.text(((240 * S - w) / 2, 1 * S), title, font=f, fill=255, stroke_width=1, stroke_fill=255)
    g = np.array(im.resize((240, 14), Image.BOX)).astype(np.int64)
    levels = np.array([l for l, _ in LEGAL_GREYS]); idx = np.array([i for _, i in LEGAL_GREYS], np.uint8)
    q = idx[np.abs(g[..., None] - levels[None, None]).argmin(-1)]
    ys, xs = np.nonzero(g > 20)
    shift = 47 - ys.max()                        # descenders end on row 47, as in the original line (rows 39-47)
    a[36:50] = 1
    for y, x in zip(*np.nonzero(q != 1)):
        a[y + shift, x] = q[y, x]
    return a


def legal_apply(rom, at):
    a = legal_bitmap(rom)
    data = a.tobytes()
    # (2026-11-06) BF's legal-screen code also reads the word just BEFORE the bitmap (ldr =bitmap; subs #4; ldr: its
    # IWRAM pointer 0x03003300, compiler-pooled there) and writes through it, so that word moves along with the bitmap
    # (without it the code wrote through junk to 0xFFFEFDFD)
    assert struct.unpack_from('<I', rom, LEGAL_LITERAL)[0] == BASE + LEGAL_BITMAP
    rom[at:at + 12 + len(data)] = bytes(rom[LEGAL_BITMAP - 4:LEGAL_BITMAP]) + struct.pack('<II', 0, len(data)) + data
    struct.pack_into('<I', rom, LEGAL_LITERAL, BASE + at + 4)
    return (at + 12 + len(data) + 3) & ~3


if __name__ == '__main__':      # preview: python3 tools/title.py <rom> <art> <out.png>
    rom = bytearray(open(sys.argv[1], 'rb').read())
    bmp, pal, n = build(rom, sys.argv[2])
    p = np.frombuffer(pal, '<u2').astype(np.int64)
    rgb = np.stack([(p & 31) << 3, ((p >> 5) & 31) << 3, ((p >> 10) & 31) << 3], 1).astype(np.uint8)
    Image.fromarray(rgb[np.frombuffer(bmp, np.uint8).reshape(160, 240)]).resize((480, 320), Image.NEAREST).save(sys.argv[3])
    print('new colours', n)
