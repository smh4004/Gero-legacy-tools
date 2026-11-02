import sys, struct, pickle, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import decompress_stream
import numpy as np
from PIL import Image, ImageDraw
SZ = {0: [(8,8),(16,16),(32,32),(64,64)], 1: [(16,8),(32,8),(32,16),(64,32)], 2: [(8,16),(8,32),(16,32),(32,64)]}
rom = open(sys.argv[1], 'rb').read(); base = int(sys.argv[2], 16); paloff = int(sys.argv[3], 16)
banks = json.load(open(sys.argv[4])); step = int(sys.argv[5]); outp = sys.argv[6]
pal = np.zeros((256, 3), np.uint8)
p = rom[paloff + 768: paloff + 1536]   # OBJ half of the master palette
for i in range(256): pal[i] = [p[3*i] & 0xF8, p[3*i+1] & 0xF8, p[3*i+2] & 0xF8]
def u32(a): return struct.unpack_from('<I', rom, a)[0]
recs = sorted(r for b in banks for r in b['recs'])
# dedupe by block pointer, keep ROM order of blocks
seen = set(); frames = []
for r in recs:
    ptr = u32(r + 4)
    if ptr in seen: continue
    seen.add(ptr); frames.append((ptr - base, u32(r)))
frames.sort()
pick = frames[::step]
cols = 48; cell = 34
rows = (len(pick) + cols - 1) // cols
W = Image.new('RGB', (cols * cell, rows * (cell + 9)), (40, 40, 48)); d = ImageDraw.Draw(W)
meta = []
for k, (off, attr) in enumerate(pick):
    a0, a1 = attr & 0xFFFF, attr >> 16
    shape, size = (a0 >> 14) & 3, (a1 >> 14) & 3
    if shape == 3: continue
    w, h = SZ[shape][size]
    typ, s = struct.unpack_from('<II', rom, off)
    try: data, _ = decompress_stream(rom, off + 8, s)
    except Exception: continue
    tw = w // 8; n = min(len(data) // 64, tw * (h // 8))
    img = np.zeros((h, w, 3), np.uint8); img[:] = (40, 40, 48)
    for t in range(n):
        tile = np.frombuffer(data[64*t:64*t+64], np.uint8).reshape(8, 8)
        ty, tx = (t // tw) * 8, (t % tw) * 8
        m = tile != 0
        blk = img[ty:ty+8, tx:tx+8]; blk[m] = pal[tile][m]
    im = Image.fromarray(img); im.thumbnail((32, 32))
    x, y = (k % cols) * cell, (k // cols) * (cell + 9)
    W.paste(im, (x + 1, y + 1)); d.text((x + 1, y + cell - 1), '%X' % (off >> 12), fill=(150, 150, 160))
    meta.append((k, off))
W.save(outp); json.dump(meta, open(outp + '.json', 'w'))
print('frames', len(frames), 'shown', len(pick), 'size', W.size)
