"""Import a labelled sprite sheet as drawn by an image generator from the art prompts: magenta (#FF00FF) panels, one per
animation view (DOWN, UP, RIGHT, in that order), separated by dark label bars, frames left to right.
Writes one raw strip at native pixel scale (frames down..., up..., right..., transparent background) for
tools/intake.py, and optionally strips a black ground shadow.

usage: python3 tools/bandsheet.py <sheet.png> <out.png> [--native-height 30] [--shadow] [--views 3]
--native-height: the frame height (shadow included) the art should have at 1x, used to find the pixel scale.
--shadow: drop near-black pixels in the bottom 7 rows of each frame (eyes are black too, so only there)."""
import os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artclean


def bands(mag):
    rows = mag.mean(1) > 0.5
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
    return sorted([b for b in boxes if b[4] >= min_frac * big], key=lambda b: b[0])


def main(src, dst, native_h=30, shadow=False):
    im = np.array(Image.open(src).convert('RGBA')).astype(int)
    mag = (im[..., 0] > 190) & (im[..., 1] < 90) & (im[..., 2] > 190)
    frames = []
    for (y0, y1) in bands(mag):
        sub = mag[y0:y1]
        boxes = components(~sub)
        hs = [b[3] - b[1] for b in boxes]
        guess = np.median(hs) / native_h
        for (x0, by0, x1, by1, _) in boxes:
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
            frames.append(px)
    H = max(f.shape[0] for f in frames) + 4
    W = sum(f.shape[1] + 6 for f in frames)
    S = np.zeros((H, W, 4), np.uint8); x = 3
    for f in frames:
        S[H - 2 - f.shape[0]:H - 2, x:x + f.shape[1]] = f; x += f.shape[1] + 6      # feet on one baseline
    Image.fromarray(S).save(dst)
    print('%s: %d frames, %dx%d strip' % (os.path.basename(src), len(frames), W, H))
    return frames


if __name__ == '__main__':
    a = sys.argv[1:]
    nh = int(a[a.index('--native-height') + 1]) if '--native-height' in a else 30
    main(a[0], a[1], nh, '--shadow' in a)
