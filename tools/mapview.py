"""Render a map with a 16 px coordinate grid and the walkable floor tinted, for placing doors, NPCs and spots.
usage: python3 tools/mapview.py <out.png> bf:<world>:<area> | l2:<map ptr hex> | out:<world>:<area> [scale]
  bf:w:a   a Buu's Fury area's map (bf.gba)       l2:0x..  a LoG2 map record (log2.gba)
  out:w:a  an area of the built ROM (log4/out/LoG4.gba), e.g. a new area with its doors (rects drawn in red,
           event spots in yellow)"""
import os, sys, struct
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import maprender, clipcheck as C

ROOT = os.path.join(HERE, '..')


def l2_mask(l2, M):
    """A LoG2 map's floor mask (+0x38; tools/mapimport copies it verbatim): rows of 256 tiles, 1 = walkable."""
    from mapimport import wfz_data
    p = struct.unpack_from('<I', l2, M + 0x38)[0] - 0x08800000
    return np.unpackbits(np.frombuffer(wfz_data(l2, p), np.uint8), bitorder='little').reshape(-1, 256)


def view(spec, scale=2):
    kind, _, rest = spec.partition(':')
    if kind == 'l2':
        G = maprender.Game(os.path.join(ROOT, 'log2.gba'), 0x08800000, 0x3ECD1C)
        M = int(rest, 16); mask = None; exits = []
        mask = l2_mask(G.rom, M)
    else:
        rom = 'bf.gba' if kind == 'bf' else os.path.join('log4', 'out', 'LoG4.gba')
        R = C.Rom(open(os.path.join(ROOT, rom), 'rb').read())
        w, a = map(int, rest.split(':'))
        M = R.map_of(w, a); mask = R.walk_mask(M)
        exits = R.exits(w, a) if kind == 'out' else []
        G = maprender.Game(os.path.join(ROOT, rom), 0x08000000, 0x701B0)
    im, _ = G.render(M)
    im = im.convert('RGB'); W, H = im.size
    if mask is not None:
        a = np.array(im).astype(np.float32)
        th, tw = min(mask.shape[0], H // 8), min(256, W // 8)
        big = np.kron(mask[:th, :tw], np.ones((8, 8), np.uint8)).astype(bool)
        sub = a[:th * 8, :tw * 8]
        sub[big] = sub[big] * 0.6 + np.array([0, 110, 60])
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    im = im.resize((W * scale, H * scale), Image.NEAREST); d = ImageDraw.Draw(im)
    for x in range(0, W, 16):
        d.line([(x * scale, 0), (x * scale, H * scale)], fill=(255, 255, 255) if x % 64 == 0 else (90, 90, 90))
        if x % 64 == 0: d.text((x * scale + 2, 2), str(x), fill=(255, 255, 0))
    for y in range(0, H, 16):
        d.line([(0, y * scale), (W * scale, y * scale)], fill=(255, 255, 255) if y % 64 == 0 else (90, 90, 90))
        if y % 64 == 0: d.text((2, y * scale + 2), str(y), fill=(255, 255, 0))
    for e in exits:
        x0, y0, x1, y1 = e['rect']
        d.rectangle([x0 * scale, y0 * scale, x1 * scale, y1 * scale], outline=(255, 40, 40) if e['kind'] == 'warp' else (255, 230, 0), width=2)
    return im


if __name__ == '__main__':
    out, spec = sys.argv[1], sys.argv[2]
    view(spec, int(sys.argv[3]) if len(sys.argv) > 3 else 2).save(out)
