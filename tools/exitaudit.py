"""Exit audit (2026-11-03, user: "doors that aren't doors"): find what looks like a way out but isn't one.
  A. native doorways: exits of the source map's own area (Buu's Fury areas used through map_from) that no LoG4 exit,
     walk-in or examine spot covers (LoG4 replaced every area's exits with its own);
  B. open edges: walkable floor that runs into the edge of the map's art (a path leading off screen) where no LoG4
     exit / walk-in / examine spot is.
Each candidate gets a crop (out dir) for review; the fix is either a real exit or a visible reason (a walk-in or
examine message: "it's locked", "rubble blocks the way"), so the player is never left guessing.
usage: python3 tools/exitaudit.py <built rom> <outdir> [w:a ...]"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import clipcheck as C, maprender

ROOT = os.path.join(HERE, '..')


def overlaps(r, rects, pad=16):
    x0, y0, x1, y1 = r
    return any(not (x1 + pad <= a or a2 + pad <= x0 or y1 + pad <= b or b2 + pad <= y0) for a, b, a2, b2 in rects)


def segments(mask_line):
    out, s = [], None
    for i, v in enumerate(list(mask_line) + [0]):
        if v and s is None: s = i
        if not v and s is not None: out.append((s, i)); s = None
    return out


def audit(rom_path, outdir, only=None):
    R = C.Rom(open(rom_path, 'rb').read()); BF = C.Rom(open(os.path.join(ROOT, 'bf.gba'), 'rb').read())
    G = maprender.Game(rom_path, 0x08000000, 0x701B0)
    cfg = json.load(open(os.path.join(ROOT, 'log4', 'areas.json')))
    allv = {(v['world'], v['area']): v for v in cfg['new_areas'] + cfg['areas']}
    os.makedirs(outdir, exist_ok=True)
    found = []
    for (w, a), v in sorted(allv.items()):
        if only and '%d:%d' % (w, a) not in only: continue
        try:
            M = R.map_of(w, a); mask = R.walk_mask(M); ours = [tuple(e['rect']) for e in R.exits(w, a)]
            im, _ = G.render(M)
        except Exception as ex:
            found.append((w, a, 'error', str(ex), None)); continue
        rgb = np.asarray(im.convert('RGB'))
        nz = np.nonzero(rgb.sum(2) > 24)
        if not len(nz[0]): continue
        H, W = nz[0].max() + 1, nz[1].max() + 1; Y0, X0 = nz[0].min(), nz[1].min()
        th, tw = min(mask.shape[0], H // 8 + 1), min(256, W // 8 + 1)
        m = mask[:th, :tw]
        cands = []
        # B. open edges: floor in the outermost tile row / column of the art
        bands = {'top': (m[max(Y0 // 8, 0)], lambda s, e: (s * 8, Y0, e * 8, Y0 + 8)),
                 'bottom': (m[min((H - 1) // 8, th - 1)], lambda s, e: (s * 8, H - 8, e * 8, H)),
                 'left': (m[:, max(X0 // 8, 0)], lambda s, e: (X0, s * 8, X0 + 8, e * 8)),
                 'right': (m[:, min((W - 1) // 8, tw - 1)], lambda s, e: (W - 8, s * 8, W, e * 8))}
        for side, (line, rect) in bands.items():
            for s, e in segments(line):
                if e - s < 2: continue                     # a single floor tile at the edge is noise
                r = rect(s, e)
                if not overlaps(r, ours): cands.append(('open edge (%s)' % side, r))
        # A. native doorways of the BF area this map was taken from
        src = v.get('map_from')
        for _ in range(4):
            if isinstance(src, list) and tuple(src) in allv and tuple(src) != (w, a):
                nxt = allv[tuple(src)].get('map_from')
                if not nxt or nxt == src: break
                src = nxt
            else: break
        if isinstance(src, list) and tuple(src) not in allv:
            try:
                for e in BF.exits(*src):
                    r = tuple(e['rect'])
                    if r[2] - r[0] <= 0 or r[3] - r[1] <= 0: continue
                    if not overlaps(r, ours, pad=8): cands.append(('native BF doorway of %d:%d (%s)' % (src[0], src[1], e['kind']), r))
            except Exception: pass
        for kind, r in cands:
            found.append((w, a, kind, r, (W, H)))
            x0, y0, x1, y1 = r
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            box = (max(0, cx - 120), max(0, cy - 80), max(0, cx - 120) + 240, max(0, cy - 80) + 160)
            crop = im.convert('RGB').crop(box); d = ImageDraw.Draw(crop)
            d.rectangle([x0 - box[0], y0 - box[1], x1 - box[0], y1 - box[1]], outline=(255, 0, 255), width=2)
            for q in ours:
                d.rectangle([q[0] - box[0], q[1] - box[1], q[2] - box[0], q[3] - box[1]], outline=(255, 255, 0))
            crop.save(os.path.join(outdir, 'x_%d_%d_%d_%d.png' % (w, a, x0, y0)))
    return found


if __name__ == '__main__':
    f = audit(sys.argv[1], sys.argv[2], set(sys.argv[3:]) or None)
    for x in f: print(x)
    print('%d candidates' % len(f))
