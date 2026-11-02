import sys, struct, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import decompress_stream
import numpy as np
from PIL import Image, ImageDraw
SZ = {0: [(8,8),(16,16),(32,32),(64,64)], 1: [(16,8),(32,8),(32,16),(64,32)], 2: [(8,16),(8,32),(16,32),(32,64)]}
rom = open(sys.argv[1], 'rb').read(); paloff = int(sys.argv[2], 16)
frames = json.load(open(sys.argv[3])); segs = json.load(open(sys.argv[4])); prefix = sys.argv[5]
pal = np.zeros((256, 3), np.uint8); p = rom[paloff + 768: paloff + 1536]
for i in range(256): pal[i] = [p[3*i] & 0xF8, p[3*i+1] & 0xF8, p[3*i+2] & 0xF8]
offs = [o for o, a in frames]; attr = dict(frames)
import bisect
def render(off):
    a = attr[off]; a0, a1 = a & 0xFFFF, a >> 16; shape, size = (a0 >> 14) & 3, (a1 >> 14) & 3
    w, h = SZ[shape][size]; s = struct.unpack_from('<I', rom, off + 4)[0]
    data, _ = decompress_stream(rom, off + 8, s)
    tw = w // 8; n = min(len(data) // 64, tw * (h // 8)); idx = np.zeros((h, w), np.uint8)
    for t in range(n):
        idx[(t // tw) * 8:(t // tw) * 8 + 8, (t % tw) * 8:(t % tw) * 8 + 8] = np.frombuffer(data[64*t:64*t+64], np.uint8).reshape(8, 8)
    return idx
BG = (34, 36, 44); per = 24; cols = 6; cw, ch = 250, 120
for sh in range(0, len(segs), per):
    part = segs[sh:sh + per]
    W = Image.new('RGB', (cols * cw, ((len(part) + cols - 1) // cols) * ch), BG); d = ImageDraw.Draw(W)
    for n, sg in enumerate(part):
        i0 = bisect.bisect_left(offs, sg['start']); i1 = bisect.bisect_right(offs, sg['end'])
        members = offs[i0:i1]
        rend = []
        for o in members:
            try:
                idx = render(o)
                if (idx != 0).sum() > 40: rend.append(idx)
            except Exception: pass
        rend.sort(key=lambda x: -(x != 0).sum())
        picks = rend[:1] + rend[len(rend)//3:len(rend)//3+1] + rend[2*len(rend)//3:2*len(rend)//3+1] + rend[-1:]
        x0, y0 = (n % cols) * cw, (n // cols) * ch
        for j, idx in enumerate(picks[:4]):
            rgb = pal[idx]; rgb[idx == 0] = BG
            im = Image.fromarray(rgb).resize((idx.shape[1] * 2, idx.shape[0] * 2), Image.NEAREST); im.thumbnail((58, 92))
            W.paste(im, (x0 + 2 + j * 60, y0 + 2))
        d.rectangle((x0, y0 + ch - 20, x0 + cw - 4, y0 + ch - 2), fill=(20, 20, 26))
        d.text((x0 + 4, y0 + ch - 17), '#%d %X (%d fr)' % (sg['seg'], sg['start'], sg['frames']), fill=(255, 220, 120))
    W.save('%s_%d.png' % (prefix, sh // per))
print('sheets', (len(segs) + per - 1) // per)
