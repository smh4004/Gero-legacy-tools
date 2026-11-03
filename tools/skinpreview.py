"""Preview the frames an actor gets from build_actors (drawn sheets + LoG2 animations), with its `recolor` applied.
usable: python3 tools/skinpreview.py bf.gba log12.gba <actor name> <out.png> [recolor json string]
Collects every frame through sprites.FRAME_HOOK into one contact sheet (palette = master OBJ registry)."""
import sys, os, json, numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sprites, artclean


def frames(bf, l2, name, recolor=None):
    art = os.path.join(HERE, '..', 'log4', 'art')
    regs = artclean.registries(os.path.join(art, 'clean'))
    ctx = lambda act: (regs.get(act, regs[None]).usable(), artclean.palette_rgb(regs.get(act, regs[None])))
    cfg = json.load(open(os.path.join(HERE, '..', 'log4', 'actors.json')))
    a = dict(cfg[name])
    if recolor is not None: a['recolor'] = recolor
    got = []; seen = set()
    def hook(key, f):
        if sprites.CUR_ACTOR != name: return
        h = (f.shape, f.tobytes())
        if h not in seen: seen.add(h); got.append((key, np.array(f)))
    sprites.FRAME_HOOK = hook
    rom = bytearray(bf) + bytearray(0x1000000 - len(bf))
    keys = list(cfg); cfg = {k: cfg[k] for k in keys[:keys.index(name)]}; cfg[name] = a   # earlier entries may be its template
    sprites.build_actors(rom, cfg, os.path.join(art, 'clean'), 0xC00000, l2, ctx)
    sprites.FRAME_HOOK = None
    return got, artclean.palette_rgb(regs[None])


def sheet(got, pal, cols=16, scale=2):
    cw = max(f.shape[1] for _, f in got); ch = max(f.shape[0] for _, f in got)
    rows = (len(got) + cols - 1) // cols
    img = np.full((rows * ch, cols * cw, 3), 96, np.uint8)
    pal = np.array(pal, np.uint8)
    for i, (_, f) in enumerate(got):
        r, c = divmod(i, cols); rgb = pal[f]; m = f != 0
        sub = img[r * ch:r * ch + f.shape[0], c * cw:c * cw + f.shape[1]]; sub[m] = rgb[m]
    return Image.fromarray(img).resize((img.shape[1] * scale, img.shape[0] * scale), Image.NEAREST)


if __name__ == '__main__':
    bf = open(sys.argv[1], 'rb').read(); l2 = open(sys.argv[2], 'rb').read()[0x800000:]
    rc = json.loads(sys.argv[5]) if len(sys.argv) > 5 else None
    got, pal = frames(bf, l2, sys.argv[3], rc)
    print(len(got), 'frames; indices used:', sorted(set(np.concatenate([f.ravel() for _, f in got]).tolist())))
    sheet(got, pal).save(sys.argv[4])
