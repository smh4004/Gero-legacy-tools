"""Import a labelled sprite sheet as drawn by an image generator from the art prompts: magenta (#FF00FF) panels, one per
animation view (DOWN, UP, RIGHT, in that order), separated by dark label bars, frames left to right.
Writes one raw strip of equal cells at native pixel scale (frames down..., up..., right..., transparent background) for
tools/intake.py, and optionally strips a black ground shadow.

usage: python3 tools/bandsheet.py <sheet.png> <out.png> [--native-height 30] [--shadow] [--scale S]
--native-height: the frame height (shadow included) the art should have at 1x, used to find the pixel scale.
--shadow: drop near-black pixels in the bottom 7 rows of each frame (eyes are black too, so only there)."""
import os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artclean


def bands(mag, im=None):
    rows = mag.mean(1) > 0.5
    if im is not None:                          # a label bar = a row that is mostly dark (sprites never are)
        c = im[..., :3]                         # bars are flat dark grey (~30,30,30); sprite rows mix black and colours
        grey = (c.min(2) >= 15) & (c.max(2) <= 60) & (c.max(2) - c.min(2) <= 12)
        rows = ~(grey.mean(1) > 0.6)
    out, s = [], None
    for y, v in enumerate(rows):
        if v and s is None: s = y
        if not v and s is not None: out.append((s, y)); s = None
    if s is not None: out.append((s, len(rows)))
    return [b for b in out if b[1] - b[0] > 20]


def components(mask, min_frac=0.03):
    from scipy.ndimage import label, binary_dilation
    lab, n = label(binary_dilation(mask, iterations=3))
    boxes = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero((lab == i) & mask)
        if len(ys): boxes.append((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1, len(ys)))
    big = max(b[4] for b in boxes)
    boxes = [b for b in boxes if b[4] >= min_frac * big]
    bodies = [list(b) for b in boxes if b[4] >= 0.25 * big]    # the characters; smaller pieces (swooshes, sparks)
    for b in boxes:                                            # join the nearest character's frame
        if b[4] >= 0.25 * big: continue
        cx = (b[0] + b[2]) / 2
        t = min(bodies, key=lambda c: abs((c[0] + c[2]) / 2 - cx))
        t[0], t[1], t[2], t[3] = min(t[0], b[0]), min(t[1], b[1]), max(t[2], b[2]), max(t[3], b[3])
        t.append(b[3] - b[1])                                  # remember: not part of the body height
    return sorted([tuple(c[:5]) + (c[1] if len(c) == 5 else None,) for c in bodies], key=lambda b: b[0])


def main(src, dst, native_h=30, shadow=False, max_h=32, scale=None):
    im = np.array(Image.open(src).convert('RGBA')).astype(int)
    mag = (im[..., 0] > 150) & (im[..., 1] < 120) & (im[..., 2] > 150) & (abs(im[..., 0] - im[..., 2]) < 80)   # magenta + JPEG fringe
    frames = []
    rows = []
    for (y0, y1) in bands(mag, im):             # unlabelled sheets are one big panel: split it at fully magenta rows
        nm = (~mag[y0:y1]).sum(1)
        busy = (nm > 0) & (nm < 0.97 * mag.shape[1]); s0 = None; gap = 0     # (full-width rows = panel edges)
        for y, v in enumerate(list(busy) + [False] * 4):
            if v:
                if s0 is None: s0 = y
                gap = 0
            elif s0 is not None:
                gap += 1
                if gap >= 4: rows.append((y0 + max(s0 - 2, 0), y0 + y)); s0 = None
    tall = max((b - a for a, b in rows), default=0)
    rows = [(a, b) for a, b in rows if b - a >= 0.3 * tall]          # drop slivers
    for (y0, y1) in rows:
        sub = mag[y0:y1]
        boxes = components(~sub)
        hs = [b[3] - b[1] for b in boxes if b[5] is not None]   # frames without effects give the body height
        guess = scale or np.median(hs or [b[3] - b[1] for b in boxes]) / native_h   # --scale: views of different heights (flying)
        for (x0, by0, x1, by1, _, _) in boxes:
            pad = int(guess * 2)
            ya, yb, xa, xb = max(by0 - pad, 0), min(by1 + pad, y1 - y0), max(x0 - pad, 0), x1 + pad
            crop = im[y0 + ya:y0 + yb, xa:xb].astype(np.uint8).copy()
            crop[..., 3] = np.where(mag[y0 + ya:y0 + yb, xa:xb], 0, 255)
            sx, sy, ox, oy, _ = artclean.detect_scale(crop, smin=max(1, guess * 0.8), smax=guess * 1.25)
            px = artclean.mode_downsample(crop, sx, sy, ox, oy)
            px[..., 3] = np.where(px[..., 3] >= 128, 255, 0)
            ys, xs = np.nonzero(px[..., 3])
            px = px[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            if shadow:
                blk = (px[..., :3].astype(int).sum(2) < 60) & (px[..., 3] > 0)
                blk[:-7] = False
                px[blk] = 0
                ys, xs = np.nonzero(px[..., 3]); px = px[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            if px.shape[0] > max_h:                 # an effect sticks out above the cell (one 32x32 OBJ per frame):
                ov = px.shape[0] - max_h                # move the white effect pixels down over the empty space
                wh = (px[..., :3].astype(int).min(2) > 225) & (px[..., 3] > 0)
                body = (px[..., 3] > 0) & ~wh
                top = np.nonzero(body.any(1))[0][0]
                fx = wh.copy(); fx[top:] = False                    # the effect pixels above the body
                ys, xs = np.nonzero(fx); px[fx] = 0
                for y, x in zip(ys, xs):
                    if px[y + ov, x, 3] == 0: px[y + ov, x] = (248, 248, 248, 255)
                px = px[ov:]
            frames.append(px)
    H = max(f.shape[0] for f in frames) + 4
    CW = max(f.shape[1] for f in frames) + 6                   # equal cells: intake splits by "frames": {"cols": n}
    S = np.zeros((H, CW * len(frames), 4), np.uint8)
    for k, f in enumerate(frames):
        x = k * CW + (CW - f.shape[1]) // 2
        S[H - 2 - f.shape[0]:H - 2, x:x + f.shape[1]] = f                         # feet on one baseline
    Image.fromarray(S).save(dst)
    print('%s: %d frames, %dx%d strip (cells %d wide: spec "frames": {"cols": %d})' % (os.path.basename(src), len(frames), S.shape[1], H, CW, len(frames)))
    return frames


if __name__ == '__main__':
    a = sys.argv[1:]
    nh = int(a[a.index('--native-height') + 1]) if '--native-height' in a else 30
    main(a[0], a[1], nh, '--shadow' in a, scale=float(a[a.index('--scale') + 1]) if '--scale' in a else None)
