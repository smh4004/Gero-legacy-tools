import sys, json, numpy as np, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anims import Actors
from PIL import Image, ImageDraw
rom = open(sys.argv[1], 'rb').read(); A = Actors(rom)
ids = [int(x) for x in sys.argv[2].split(',')]; out = sys.argv[3]; d = int(sys.argv[4]) if len(sys.argv) > 4 else 0
pal = np.array(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bf_objpal.json')))['pal'], np.uint8)
C = 52; maxn = max(A.actor(i)['n'] for i in ids)
W = Image.new('RGB', (60 + maxn * C, len(ids) * (C + 4) + 16), (32, 34, 42)); dr = ImageDraw.Draw(W)
for k in range(maxn): dr.text((60 + k * C + 18, 2), str(k), fill=(200, 200, 120))
for r, i in enumerate(ids):
    a = A.actor(i); y = 16 + r * (C + 4)
    dr.text((2, y + 18), '#%d %02X' % (i, a['cls']), fill=(230, 230, 230))
    for k, sp in enumerate(a['slots']):
        if not sp: continue
        an = A.anim(sp)
        if not an: continue
        idx = A.frame(an[0][d], canvas=(64, 64), origin=(32, 52))
        rgb = pal[idx]; rgb[idx == 0] = (32, 34, 42)
        im = Image.fromarray(rgb).resize((C - 2, C - 2), Image.NEAREST)
        W.paste(im, (60 + k * C, y)); dr.text((60 + k * C + 2, y + C - 12), str(len(an)), fill=(140, 180, 255))
W.save(out)
