"""Scouter map (SELECT in the field) for Dr. Gero's Lab: replaces Snake Way's scouter map (index 31) with a lab schematic.

Format (decoded 2026-10-31, see RE_NOTES "Scouter map"):
  header ROM 0x74CA24: [u32 count 0x37][u32 -> table 0x74C948 of map-struct pointers] ...
  map struct: [tileset ptr (WFZ container; tile ids index it directly)][0][count2][ptr][ptr][u32 n areas][n record ptrs]
  area record: [u8 world][u8 area][u16 visited-flag bit] [rect x0,y0,x1,y1 as 4 u32][same rect again]
               [w*h u16 tile map, not-visited look (grey)] [w*h u16 tile map, visited look (blue)]   (w = x1-x0, h = y1-y0)
  The map shown is the one whose records contain the current (world, area); the 0x08004A88 routine sets the visited bit.
  Snake Way's tiles use fill 96 / outline 7 (blue) and fill 114 / outline 117 (grey); the frame layers use tiles 879+.
"""
import struct, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import unpack

BASE = 0x08000000
TABLE = 0x74C948
SNAKE = 31
BLUE = (96, 7)
GREY = (114, 117)

# rooms in screen tiles (x0, y0, x1, y1), end exclusive; a room may include a 1-column corridor on its left
LAYOUT = {
    61: dict(rect=(5, 8, 11, 12), box=(5, 8, 11, 12), icon='cylinders'),
    62: dict(rect=(11, 8, 18, 12), box=(12, 8, 18, 12), icon='tank'),
    63: dict(rect=(18, 8, 25, 12), box=(19, 8, 25, 12), icon='pod'),
}
# (world, area) -> layout room, visited bit (Snake Way's own bits: 0xF3 was 1:1, 0xF2 1:2, 0xF1 1:5)
AREAS = [((1, 1), 61, 0xF3), ((1, 61), 61, 0xF3), ((1, 62), 62, 0xF2), ((1, 63), 63, 0xF1), ((1, 64), 62, 0xF2), ((1, 65), 63, 0xF1)]


def draw():
    """Returns (fill mask, outline mask) for the whole 240x160 schematic."""
    H, W = 160, 240
    fill = np.zeros((H, W), bool); line = np.zeros((H, W), bool)
    yy, xx = np.mgrid[0:H, 0:W]
    for r in LAYOUT.values():
        x0, y0, x1, y1 = [v * 8 for v in r['box']]
        fill[y0 + 1:y1 - 1, x0 + 1:x1 - 1] = True
    # corridors (left column of rooms 62 and 63), 8 px tall through the middle row
    for r in (LAYOUT[62], LAYOUT[63]):
        cx = r['rect'][0] * 8; cy = (r['box'][1] + r['box'][3]) * 4
        fill[cy - 3:cy + 3, cx - 2:cx + 10] = True
    # outline = fill boundary (1 px)
    pad = np.pad(fill, 1)
    inner = pad[1:-1, 1:-1] & pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    line |= fill & ~inner
    # icons (outline colour) inside each room
    def ring(cx, cy, r): return np.abs(np.hypot(yy - cy, xx - cx) - r) < 0.75
    for n, r in LAYOUT.items():
        x0, y0, x1, y1 = [v * 8 for v in r['box']]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if r['icon'] == 'cylinders':
            for dx in (-10, 0, 10): line |= ring(cx + dx, cy, 3.5)
        elif r['icon'] == 'tank':
            line[int(cy) - 8:int(cy) + 8, int(cx) - 5] = True; line[int(cy) - 8:int(cy) + 8, int(cx) + 5] = True
            line |= ring(cx, cy - 8, 5) & (yy < cy - 8); line[int(cy) + 8, int(cx) - 5:int(cx) + 6] = True
        elif r['icon'] == 'pod':
            line |= ring(cx, cy, 9); line |= ring(cx, cy, 4)
    return fill, line


def apply(rom, at):
    """rom: bytearray. Writes the new tileset, records and map struct at `at`; repoints table entry 31. Returns end."""
    cur = [at]
    def put(data):
        a = cur[0]; rom[a:a + len(data)] = data; cur[0] = (a + len(data) + 3) & ~3
        return BASE + a
    old = struct.unpack_from('<I', rom, TABLE + 4 * SNAKE)[0] - BASE
    tiles = np.frombuffer(bytes(unpack(rom, struct.unpack_from('<I', rom, old)[0] - BASE)[0]), np.uint8).reshape(-1, 8, 8)
    tiles = [t for t in tiles]
    index = {t.tobytes(): i for i, t in enumerate(tiles)}
    def tid(t):
        k = t.tobytes()
        if not t.any(): return 0
        if k not in index: index[k] = len(tiles); tiles.append(t.copy())
        return index[k]
    fill, line = draw()
    pics = {}
    for name, (f, o) in (('grey', GREY), ('blue', BLUE)):
        img = np.zeros(fill.shape, np.uint8); img[fill] = f; img[line] = o; pics[name] = img
    recs = []
    for (w, a), room, bit in AREAS:
        x0, y0, x1, y1 = LAYOUT[room]['rect']
        maps = []
        for look in ('grey', 'blue'):
            m = [tid(pics[look][ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]) for ty in range(y0, y1) for tx in range(x0, x1)]
            maps.append(struct.pack('<%dH' % len(m), *m))
        rect = struct.pack('<4I', x0, y0, x1, y1)
        recs.append(put(struct.pack('<BBH', w, a, bit) + rect + rect + maps[0] + maps[1]))
    assert len(tiles) < 879, 'scouter tiles would overlap the frame tiles'
    blk = b''.join(t.tobytes() for t in tiles)
    tset = put(struct.pack('<II', 0, len(blk)) + blk)
    S = put(struct.pack('<6I', tset, 0, 0, 0, 0, len(recs)) + struct.pack('<%dI' % len(recs), *recs))
    struct.pack_into('<I', rom, TABLE + 4 * SNAKE, S)
    return cur[0]


if __name__ == '__main__':      # preview of the schematic: python3 tools/scouter.py out.png
    from PIL import Image
    f, l = draw(); img = np.zeros(f.shape + (3,), np.uint8); img[f] = (32, 32, 248); img[l] = (0, 248, 248)
    Image.fromarray(img).resize((480, 320), Image.NEAREST).save(sys.argv[1])
