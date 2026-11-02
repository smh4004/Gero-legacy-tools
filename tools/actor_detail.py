import sys, json, numpy as np, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anims import Actors
from PIL import Image, ImageDraw
rom = open(sys.argv[1], 'rb').read(); A = Actors(rom); i = int(sys.argv[2]); out = sys.argv[3]
dirs = [int(x) for x in (sys.argv[4] if len(sys.argv) > 4 else '0').split(',')]
pal = np.array(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bf_objpal.json')))['pal'], np.uint8)
a = A.actor(i); C = 46
anims = [A.anim(s) if s else None for s in a['slots']]
maxf = max((len(x) for x in anims if x), default=1)
rows = [(k, d) for k in range(a['n']) for d in dirs if anims[k]]
W = Image.new('RGB', (70 + maxf * C, len(rows) * C + 4), (32, 34, 42)); dr = ImageDraw.Draw(W)
for r, (k, d) in enumerate(rows):
    y = r * C + 2; dr.text((2, y + 16), 's%d d%d' % (k, d), fill=(230, 230, 120))
    for f, fr in enumerate(anims[k]):
        idx = A.frame(fr[d], canvas=(64, 64), origin=(32, 52)); rgb = pal[idx]; rgb[idx == 0] = (32, 34, 42)
        W.paste(Image.fromarray(rgb).resize((C - 2, C - 2), Image.NEAREST), (70 + f * C, y))
W.save(out)
