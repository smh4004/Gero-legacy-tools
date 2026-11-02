"""Title logo subtitle: replace "BUU'S FURY (TM)" under the Dragon Ball Z wordmark with LoG4's subtitle.

The logo is map 0x29B934 (area 0:98 room 1). BG3 = "Dragon Ball Z" alone, BG2 = + first word, BG1 = full logo (+ (R));
the intro reveals them in turn. The subtitle box is rebuilt from BG3's pixels and the new text is drawn in the same style
as the original: yellow->orange vertical gradient fill (8, 122, 123, 124, 28), darker-yellow edge shading (36-38),
1 px black outline (1) and a green glow (44 -> 47, then 95). Written as a new map record with tools/mapedit.py.
"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_dilation, binary_erosion
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mapedit

LOGO_M = 0x29B934
AREA = (0, 98)
BOX = (40, 86, 226, 118)          # x0, y0, x1, y1 of the subtitle + (TM) region in the 256x256 layer canvas
FONT = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
FILL = [8, 8, 8, 122, 122, 123, 123, 124, 124, 28, 28, 28, 28, 28, 28, 28]


def text_mask(text, cap=14, spacing=1):
    """Binary glyph mask, `cap` px cap height, rendered 8x and box-downsampled."""
    S = 8
    f = ImageFont.truetype(FONT, cap * S * 100 // 72)
    widths = [f.getbbox(ch)[2] for ch in text]
    W = sum(widths) + spacing * S * len(text) + 4 * S; H = cap * S * 2
    im = Image.new('L', (W, H)); d = ImageDraw.Draw(im); x = 2 * S
    for ch, wd in zip(text, widths):
        d.text((x, 0), ch, font=f, fill=255); x += wd + spacing * S
    a = np.array(im, np.float32)
    ys, xs = np.nonzero(a > 0); a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = -(-a.shape[0] // S) * S, -(-a.shape[1] // S) * S
    a = np.pad(a, ((0, h - a.shape[0]), (0, w - a.shape[1])))
    small = a.reshape(h // S, S, w // S, S).mean((1, 3))
    return small > 110


def styled(mask):
    """mask -> (index image, opaque mask) with the original subtitle's colours; adds a 4 px margin."""
    m = np.pad(mask, 4)
    o1 = binary_dilation(m) & ~m
    g = [binary_dilation(m, iterations=k + 1) & ~binary_dilation(m, iterations=k) for k in range(1, 4)]
    img = np.zeros(m.shape, np.uint8)
    ys, xs = np.nonzero(m); top, bot = ys.min(), ys.max()
    for y, x in zip(ys, xs):
        img[y, x] = FILL[min(len(FILL) - 1, (y - top) * len(FILL) // max(1, bot - top + 1))]
    edge = m & ~binary_erosion(m)                       # darker yellow rim inside the outline on the upper half
    for y, x in zip(*np.nonzero(edge)):
        if img[y, x] == 8: img[y, x] = 37
    img[o1] = 1
    for k, col in enumerate((44, 46, 95)): img[g[k]] = col
    return img, (img != 0)


def apply(rom, text_full, text_first, at):
    """rom: bytearray. Rebuilds the logo map with the new subtitle; repoints area 0:98 room 1. Returns end offset."""
    layers = mapedit.load(rom, LOGO_M)
    base = layers[3][0]
    x0, y0, x1, y1 = BOX
    for li, txt in ((1, text_full), (2, text_first)):
        can = layers[li][0].copy()
        can[y0:y1, x0:x1] = base[y0:y1, x0:x1]          # erase the old subtitle and (TM)
        img, op = styled(text_mask(full_or(txt)))
        h, w = img.shape
        # centre under the wordmark: the full subtitle is centred, the first word keeps the same left edge
        full_w = styled(text_mask(text_full))[0].shape[1]
        left = (x0 + x1) // 2 - full_w // 2
        top = y0 + max(0, (y1 - y0 - h) // 2)
        assert left >= 0 and left + w <= can.shape[1] and top + h <= can.shape[0]
        reg = can[top:top + h, left:left + w]
        reg[op] = img[op]
        layers[li] = (can, layers[li][1])
    newM, end = mapedit.save(rom, LOGO_M, layers, at)
    import areas
    import areas as _A; count = _A.area_count(rom)
    table = struct.unpack_from('<I', rom, 0x8A58)[0] - 0x08000000
    e = areas.entry(rom, AREA[0], AREA[1], table, count)
    st = struct.unpack_from('<I', rom, e + 0x2C)[0] - 0x08000000
    assert struct.unpack_from('<I', rom, st)[0] == 0x08000000 + LOGO_M + 4
    struct.pack_into('<I', rom, st, newM + 4)
    return end


def full_or(t): return t


if __name__ == '__main__':          # preview: python3 tools/logo.py <rom> <out.png>
    rom = bytearray(open(sys.argv[1], 'rb').read())
    apply(rom, "GERO'S LEGACY", "GERO'S", 0xF40000)
    import areas
    table = struct.unpack_from('<I', rom, 0x8A58)[0] - 0x08000000
    import areas as _A; count = _A.area_count(rom)
    st = struct.unpack_from('<I', rom, areas.entry(rom, 0, 98, table, count) + 0x2C)[0] - 0x08000000
    M = struct.unpack_from('<I', rom, st)[0] - 4 - 0x08000000
    lay = mapedit.load(rom, M)
    p = rom[0x701B0:0x701B0 + 768]; pal = np.frombuffer(bytes(p), np.uint8).reshape(256, 3)
    row = np.concatenate([pal[lay[k][0][40:130, 0:240]] for k in (1, 2, 3)], 1)
    Image.fromarray(row).resize((row.shape[1] * 2, row.shape[0] * 2), Image.NEAREST).save(sys.argv[2])
