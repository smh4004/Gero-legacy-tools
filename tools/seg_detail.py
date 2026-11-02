import sys, struct, json, os, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import decompress_stream
import numpy as np
from PIL import Image, ImageDraw
SZ = {0: [(8,8),(16,16),(32,32),(64,64)], 1: [(16,8),(32,8),(32,16),(64,32)], 2: [(8,16),(8,32),(16,32),(32,64)]}
rom = open(sys.argv[1], 'rb').read(); paloff = int(sys.argv[2], 16)
frames = json.load(open(sys.argv[3])); segs = {s['seg']: s for s in json.load(open(sys.argv[4]))}
ids = [int(x) for x in sys.argv[5].split(',')]; out = sys.argv[6]; per = int(sys.argv[7]) if len(sys.argv) > 7 else 30
pal = np.zeros((256, 3), np.uint8); p = rom[paloff + 768: paloff + 1536]
for i in range(256): pal[i] = [p[3*i] & 0xF8, p[3*i+1] & 0xF8, p[3*i+2] & 0xF8]
offs = [o for o, a in frames]; attr = dict(frames)
def render(off):
    a = attr[off]; a0, a1 = a & 0xFFFF, a >> 16; shape, size = (a0 >> 14) & 3, (a1 >> 14) & 3
    w, h = SZ[shape][size]; s = struct.unpack_from('<I', rom, off + 4)[0]
    data, _ = decompress_stream(rom, off + 8, s)
    tw = w // 8; n = min(len(data) // 64, tw * (h // 8)); idx = np.zeros((h, w), np.uint8)
    for t in range(n):
        idx[(t // tw) * 8:(t // tw) * 8 + 8, (t % tw) * 8:(t % tw) * 8 + 8] = np.frombuffer(data[64*t:64*t+64], np.uint8).reshape(8, 8)
    return idx
BG = (34, 36, 44); cell = 50
W = Image.new('RGB', (per * cell, len(ids) * (cell * 2 + 14)), BG); d = ImageDraw.Draw(W)
for r, sid in enumerate(ids):
    sg = segs[sid]; i0 = bisect.bisect_left(offs, sg['start']); i1 = bisect.bisect_right(offs, sg['end'])
    mem = offs[i0:i1]; pick = [mem[int(k * (len(mem) - 1) / max(1, per - 1))] for k in range(min(per, len(mem)))]
    y0 = r * (cell * 2 + 14)
    d.text((2, y0), '#%d' % sid, fill=(255, 220, 120))
    for j, o in enumerate(pick):
        try: idx = render(o)
        except Exception: continue
        rgb = pal[idx]; rgb[idx == 0] = BG
        im = Image.fromarray(rgb).resize((idx.shape[1] * 2, idx.shape[0] * 2), Image.NEAREST); im.thumbnail((cell - 2, cell * 2 - 2))
        W.paste(im, (j * cell + 1, y0 + 12))
        d.text((j * cell + 1, y0 + cell * 2), '%X' % (o >> 8), fill=(120, 120, 135))
W.save(out)
