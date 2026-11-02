import sys, struct, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import decompress_stream
import numpy as np
from PIL import Image, ImageDraw
SZ = {0: [(8,8),(16,16),(32,32),(64,64)], 1: [(16,8),(32,8),(32,16),(64,32)], 2: [(8,16),(8,32),(16,32),(32,64)]}
rom = open(sys.argv[1], 'rb').read(); base = int(sys.argv[2], 16); paloff = int(sys.argv[3], 16)
framelist = json.load(open(sys.argv[4])); prefix = sys.argv[5]; lo = int(sys.argv[6], 16)
pal = np.zeros((256, 3), np.uint8); p = rom[paloff + 768: paloff + 1536]
for i in range(256): pal[i] = [p[3*i] & 0xF8, p[3*i+1] & 0xF8, p[3*i+2] & 0xF8]
def u32(a): return struct.unpack_from('<I', rom, a)[0]
frames = [(o, a) for o, a in framelist if o >= lo]
def render(off, attr):
    a0, a1 = attr & 0xFFFF, attr >> 16; shape, size = (a0 >> 14) & 3, (a1 >> 14) & 3
    if shape == 3: return None
    w, h = SZ[shape][size]; s = struct.unpack_from('<I', rom, off + 4)[0]
    try: data, _ = decompress_stream(rom, off + 8, s)
    except Exception: return None
    tw = w // 8; n = min(len(data) // 64, tw * (h // 8))
    idx = np.zeros((h, w), np.uint8)
    for t in range(n):
        tile = np.frombuffer(data[64*t:64*t+64], np.uint8).reshape(8, 8)
        idx[(t // tw) * 8:(t // tw) * 8 + 8, (t % tw) * 8:(t % tw) * 8 + 8] = tile
    return idx
sigs = []; imgs = []
for off, attr in frames:
    idx = render(off, attr)
    if idx is None or (idx != 0).sum() < 30: sigs.append(None); imgs.append(None); continue
    h = np.bincount(idx[idx != 0], minlength=256).astype(float); h /= np.linalg.norm(h)
    sigs.append(h); imgs.append(idx)
segs = []; cur = []; mean = None
for k, s in enumerate(sigs):
    if s is None: continue
    if mean is not None and float(mean @ s) / (np.linalg.norm(mean) + 1e-9) < 0.55 and len(cur) >= 3:
        segs.append(cur); cur = []; mean = None
    cur.append(k); mean = s.copy() if mean is None else mean * 0.85 + s * 0.15
if cur: segs.append(cur)
segs = [s for s in segs if len(s) >= 6]
print('frames', len(frames), 'segments', len(segs))
# representative: frame with most pixels among the segment, plus 2 more spread
cols = 10; cw, ch = 150, 96
rows = (len(segs) + cols - 1) // cols
W = Image.new('RGB', (cols * cw, rows * ch), (36, 38, 46)); d = ImageDraw.Draw(W)
meta = []
for n, sg in enumerate(segs):
    picks = [sg[len(sg) // 5], max(sg, key=lambda k: (imgs[k] != 0).sum()), sg[(4 * len(sg)) // 5]]
    x0, y0 = (n % cols) * cw, (n // cols) * ch
    for j, k in enumerate(picks):
        idx = imgs[k]; rgb = pal[idx]; rgb[idx == 0] = (36, 38, 46)
        im = Image.fromarray(rgb); im.thumbnail((46, 64)); 
        W.paste(im, (x0 + 2 + j * 48, y0 + 2))
    d.text((x0 + 3, y0 + ch - 24), '#%d  %X' % (n, frames[sg[0]][0]), fill=(235, 235, 240))
    d.text((x0 + 3, y0 + ch - 13), '%d frames' % len(sg), fill=(150, 150, 165))
    meta.append(dict(seg=n, start=frames[sg[0]][0], end=frames[sg[-1]][0], frames=len(sg)))
W.save(prefix + '.png'); json.dump(meta, open(prefix + '.json', 'w'), indent=0)
print(W.size)
