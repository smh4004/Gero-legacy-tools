"""Which BF OBJ palette indices each actor uses (all frames, all directions). Output run6/objpal_usage.json"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from anims import Actors, ACTOR_COUNT, BASE
rom = open(sys.argv[1] if len(sys.argv) > 1 else 'bf.gba', 'rb').read()
A = Actors(rom); out = {}
for i in range(ACTOR_COUNT):
    try: a = A.actor(i)
    except Exception: continue
    used = set()
    for sp in a['slots']:
        fr = A.anim(sp) if sp else None
        if not fr: continue
        for k in fr:
            for fp in k:
                if not A.ok(fp): continue
                f = fp - BASE; n = A.u32(f)
                if not (0 < n <= 16): continue
                for q in range(n):
                    p = f + 4 + 16 * q
                    im = A.piece_img(A.u32(p + 8), A.u32(p + 12))
                    if im is not None: used |= set(np.unique(im).tolist())
    used.discard(0)
    out[i] = dict(cls=a['cls'], n=a['n'], used=sorted(used))
os.makedirs('run6', exist_ok=True); json.dump(out, open('run6/objpal_usage.json', 'w'))
print(len(out))
