"""LoG4 art cleanup + quantize: turn image-generator output into GBA-legal pixel art.

Pipeline per asset:
  1. load + background removal (existing alpha, flat/magenta key, or border flood fill)
  2. pixel-grid detection (generators draw "fake pixels" at N x scale, often off-grid) and
     mode-downsampling to true 1x pixels (no averaging, so no new blended colors)
  3. alpha binarize (GBA has no partial transparency)
  4. frame split (spec cols x rows, or auto by connected components)
  5. colour reduction: k-means in CIELAB to <= max_colors, then
     sprites/portraits -> nearest colour in Buu's Fury's shared OBJ palette (or a free slot if allowed),
     ui -> its own palette (<= 240 colours)
  6. stray-pixel cleanup, baseline alignment into fixed cells
  7. outputs: indexed PNG (index 0 = transparent), 4x preview, JSON report with warnings

Usage:  python3 artclean.py <spec.json> <raw_dir> <out_dir>
Spec entry example:
  {"id": "P1_android17_dash", "file": "P1_android17_dash.png", "kind": "sprite",
   "cell": [32, 32], "frames": {"cols": 4, "rows": 1}, "max_colors": 16, "allow_new_colors": 2}
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OBJPAL = json.load(open(os.path.join(HERE, 'bf_objpal.json')))


# ---------- colour ----------
def srgb_to_lab(rgb):
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def gba_round(rgb):
    return (np.asarray(rgb, np.int64) >> 3) << 3


def kmeans(lab, k, iters=25, seed=0):
    rng = np.random.default_rng(seed)
    uniq = np.unique(lab.round(2), axis=0)
    if len(uniq) <= k:
        return uniq
    # k-means++ init
    cent = [lab[rng.integers(len(lab))]]
    for _ in range(1, k):
        d = np.min(((lab[:, None] - np.array(cent)[None]) ** 2).sum(-1), 1)
        cent.append(lab[rng.choice(len(lab), p=d / d.sum())])
    cent = np.array(cent)
    for _ in range(iters):
        a = np.argmin(((lab[:, None] - cent[None]) ** 2).sum(-1), 1)
        new = np.array([lab[a == j].mean(0) if (a == j).any() else cent[j] for j in range(k)])
        if np.allclose(new, cent): break
        cent = new
    return cent


# ---------- 1. background ----------
def remove_background(rgba, tol=14.0):
    a = rgba[..., 3]
    if (a < 250).mean() > 0.02:                      # already has real transparency
        return rgba
    rgb = rgba[..., :3]
    lab = srgb_to_lab(rgb)
    H, W = a.shape
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    bg = np.median(border, 0)
    close = np.sqrt(((lab - bg) ** 2).sum(-1)) < tol
    # flood fill from the border through "close" pixels only (keeps interior same-colour areas)
    mask = np.zeros_like(close)
    stack = [(y, x) for y in range(H) for x in (0, W - 1) if close[y, x]] + \
            [(y, x) for x in range(W) for y in (0, H - 1) if close[y, x]]
    while stack:
        y, x = stack.pop()
        if mask[y, x]: continue
        mask[y, x] = True
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and close[ny, nx] and not mask[ny, nx]:
                stack.append((ny, nx))
    out = rgba.copy(); out[mask, 3] = 0
    return out


# ---------- 2. pixel grid ----------
def _edge_profile(lab, alpha, axis):
    d = np.sqrt((np.diff(lab, axis=axis) ** 2).sum(-1))
    d = np.maximum(d - 6.0, 0.0)         # ignore noise / JPEG ripple below ~6 dE; keep real colour edges
    d = d + 10 * np.abs(np.diff(alpha.astype(float) / 255, axis=axis))
    return d.sum(axis=1 - axis)          # energy at each boundary position


def _best_offset_score(prof, s, tot):
    n = len(prof); ks = np.arange(int(n / s) + 2)
    offs = np.arange(0, s, 0.25)
    idx = np.round(offs[:, None] + ks[None, :] * s).astype(int) - 1     # boundary index of each grid line
    ok = (idx >= 0) & (idx < n)
    vals = np.where(ok, prof[np.clip(idx, 0, n - 1)], 0).sum(1) / tot * s
    j = int(np.argmax(vals))
    return float(vals[j]), float(offs[j])


def detect_scale(rgba, smin=1, smax=40):
    """Square-pixel grid detection on both axes jointly.
    Returns (scale_x, scale_y, offset_x, offset_y, strength); the scale may be fractional."""
    lab = srgb_to_lab(rgba[..., :3]); al = rgba[..., 3]
    px, py = _edge_profile(lab, al, 1), _edge_profile(lab, al, 0)
    tx, ty = px.sum() + 1e-9, py.sum() + 1e-9
    lim = min(smax, min(len(px), len(py)) / 4)
    def joint(s):
        a, ox = _best_offset_score(px, s, tx); b, oy = _best_offset_score(py, s, ty)
        return (a + b) / 2, ox, oy
    cands = np.arange(max(2.0, smin), lim + 1e-9, 0.05)
    if not len(cands): return 1.0, 1.0, 0.0, 0.0, 0.0
    res = [(*joint(s), s) for s in cands]
    top = max(r[0] for r in res)
    # multiples of the true pixel size tie with it, divisors reach only ~1/2: smallest strong scale wins
    first = min((r for r in res if r[0] >= 0.75 * top), key=lambda r: r[3])
    fine = [(*joint(s), s) for s in np.arange(first[3] - 0.08, first[3] + 0.081, 0.01) if s >= 2]
    sc, ox, oy, s = max(fine)
    if top < 1.6:                           # no convincing grid: art is already 1x
        return 1.0, 1.0, 0.0, 0.0, top
    return s, s, ox, oy, top


KEY_LAB = srgb_to_lab(np.array([[255, 0, 255]]))[0]   # generator key colour (background)
DARK_DL, DARK_FRAC, DARK_MARGIN = 50, 0.12, 0.12   # portrait line keeping (luma drop, share of block, edge margin)


def mode_downsample(rgba, sx, sy, ox, oy, keep_dark=False):
    """One output pixel per (sx, sy) block, by majority colour. keep_dark: when the block holds a thin darker
    feature (mouth, eye line, crease) that would lose the vote, keep the dark pixels instead (portraits)."""
    if sx == 1 and sy == 1: return rgba
    H, W = rgba.shape[:2]
    nx, ny = int((W - ox) / sx), int((H - oy) / sy)
    out = np.zeros((ny, nx, 4), np.uint8)
    f = DARK_MARGIN if keep_dark else 0.2
    mx, my = sx * f, sy * f                              # ignore block edges (anti-aliasing lives there)
    for j in range(ny):
        y0, y1 = int(np.ceil(oy + j * sy + my)), int(np.floor(oy + (j + 1) * sy - my))
        for i in range(nx):
            x0, x1 = int(np.ceil(ox + i * sx + mx)), int(np.floor(ox + (i + 1) * sx - mx))
            blk = rgba[y0:max(y1, y0 + 1), x0:max(x1, x0 + 1)].reshape(-1, 4)
            if len(blk) == 0: continue
            if (blk[:, 3] >= 128).mean() < 0.5:
                continue                                 # transparent
            op = blk[blk[:, 3] >= 128, :3]
            q = (op >> 2).astype(np.int64)               # vote on slightly coarsened colours
            keys = q[:, 0] * 4096 + q[:, 1] * 64 + q[:, 2]
            vals, cnt = np.unique(keys, return_counts=True)
            win = op[keys == vals[np.argmax(cnt)]]
            col = np.median(win, 0)
            if keep_dark and len(op) > 3:
                # judge on the whole block (no edge margin): a thin line often sits right on a block edge
                fb = rgba[int(oy + j * sy):int(oy + (j + 1) * sy), int(ox + i * sx):int(ox + (i + 1) * sx)].reshape(-1, 4)
                fop = fb[fb[:, 3] >= 128, :3]
                lum = fop @ np.array([0.299, 0.587, 0.114]); ml = float(np.dot(col, [0.299, 0.587, 0.114]))
                dark = lum < ml - DARK_DL
                if len(fop) and dark.mean() >= DARK_FRAC: col = np.median(fop[dark], 0)
            out[j, i, :3] = col; out[j, i, 3] = 255
    return out


# ---------- 4. frames ----------
def split_frames(rgba, spec):
    fr = spec.get('frames')
    if fr and fr.get('cols'):
        cols, rows = fr['cols'], fr.get('rows', 1)
        H, W = rgba.shape[:2]; cw, ch = W / cols, H / rows
        return [rgba[int(r * ch):int((r + 1) * ch), int(c * cw):int((c + 1) * cw)] for r in range(rows) for c in range(cols)]
    # auto: connected components of opaque pixels (8-neighbour, gap tolerant by 1px dilation)
    op = rgba[..., 3] > 0
    H, W = op.shape
    lab = -np.ones((H, W), int); comps = []
    dil = op.copy(); dil[1:] |= op[:-1]; dil[:-1] |= op[1:]; dil[:, 1:] |= op[:, :-1]; dil[:, :-1] |= op[:, 1:]
    for y in range(H):
        for x in range(W):
            if dil[y, x] and lab[y, x] < 0:
                st = [(y, x)]; lab[y, x] = len(comps); pts = []
                while st:
                    cy, cx = st.pop(); pts.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < H and 0 <= nx < W and dil[ny, nx] and lab[ny, nx] < 0:
                                lab[ny, nx] = len(comps); st.append((ny, nx))
                ys, xs = zip(*pts)
                comps.append((min(ys), min(xs), max(ys) + 1, max(xs) + 1, len(pts), len(comps)))
    big = max((c[4] for c in comps), default=0)
    comps = [c for c in comps if c[4] >= max(12, 0.05 * big)]      # drop specks and noise islands
    rowh = np.median([c[2] - c[0] for c in comps]) if comps else 1
    comps.sort(key=lambda c: (round(c[0] / max(rowh, 1)), c[1]))
    return [rgba[c[0]:c[2], c[1]:c[3]] * (lab[c[0]:c[2], c[1]:c[3], None] == c[5]) for c in comps]


# ---------- 5. colour ----------
class PaletteRegistry:
    """Tracks free OBJ palette slots handed out to new colours.
    Global registry: slots nothing in the game uses (valid in every act). Act registry (parent = global): slots freed in
    that act's worlds by the per-world palettes; usable existing colours are limited to what the act keeps."""
    def __init__(self, path, free_list=None, usable_base=None, parent=None):
        self.path = path
        self.data = json.load(open(path)) if os.path.exists(path) else {'assigned': {}}
        self.free_list = free_list if free_list is not None else OBJPAL['unused']
        self.usable_base = usable_base
        self.parent = parent
    def all_assigned(self):
        d = dict(self.parent.all_assigned()) if self.parent else {}
        d.update(self.data['assigned']); return d
    def usable(self):
        base = self.usable_base if self.usable_base is not None else [i for i in range(1, 256) if OBJPAL['used'][i] > 0]
        return sorted((set(base) | {int(k) for k in self.all_assigned()}) - {0})   # 0 = transparent, never a colour
    def free(self):
        taken = {int(k) for k in self.data['assigned']}
        return [i for i in self.free_list if i not in taken]
    def assign(self, rgb, owner):
        for k, v in self.all_assigned().items():
            if tuple(v['rgb']) == tuple(rgb): return int(k)
        fr = self.free()
        if not fr: return None
        self.data['assigned'][str(fr[0])] = {'rgb': list(map(int, rgb)), 'owner': owner}
        return fr[0]
    def save(self): json.dump(self.data, open(self.path, 'w'), indent=1)


# OBJ palette slots the Switch Character screen (save point) overwrites with its own UI colours, measured 2026-11-01.
# That screen also loads the master palette directly (no per-world act palette). So sheets of characters that can be
# picked there use only global colours and avoid these slots (FilteredRegistry 'menu', see act_of).
MENU_SLOTS = {2, 8, 9, 103, 193, 217, 218, 223, 224, 225, 236}
MENU_VISIBLE = ('P1', 'P2', 'P3', 'P4')          # playable Android 17 / 18, Lapis, Lazuli


class FilteredRegistry:
    """A view of another registry (the global one) that never uses or hands out the excluded slots."""
    def __init__(self, base, exclude):
        self.b, self.ex = base, set(exclude)
        self.path, self.data = base.path, base.data
    def all_assigned(self): return self.b.all_assigned()
    def usable(self): return [i for i in self.b.usable() if i not in self.ex]
    def free(self): return [i for i in self.b.free() if i not in self.ex]
    def assign(self, rgb, owner):
        for k, v in self.all_assigned().items():
            if int(k) not in self.ex and tuple(v['rgb']) == tuple(rgb): return int(k)
        fr = self.free()
        if not fr: return None
        self.b.data['assigned'][str(fr[0])] = {'rgb': list(map(int, rgb)), 'owner': owner}
        return fr[0]
    def save(self): self.b.save()


def palette_rgb(reg):
    pal = np.array(OBJPAL['pal'], np.int64)
    for k, v in reg.all_assigned().items(): pal[int(k)] = v['rgb']
    return pal


def de94(l1, l2, kL=2.0):
    """CIE94 colour difference (kL=2 tolerates lightness shifts more than hue shifts)."""
    dL = l1[..., 0] - l2[..., 0]; C1 = np.hypot(l1[..., 1], l1[..., 2]); C2 = np.hypot(l2[..., 1], l2[..., 2]); dC = C1 - C2
    da = l1[..., 1] - l2[..., 1]; db = l1[..., 2] - l2[..., 2]; dH2 = np.maximum(da * da + db * db - dC * dC, 0)
    return np.sqrt((dL / kL) ** 2 + (dC / (1 + 0.045 * C1)) ** 2 + dH2 / (1 + 0.015 * C1) ** 2)


def map_to_game_palette(frames_rgba, max_colors, allow_new, reg, owner, warn, de_new=10.0, direct=False):
    """direct: map every pixel to its nearest palette colour (keeps thin features; portraits) instead of via k-means centroids."""
    ops = np.concatenate([f[f[..., 3] > 0][:, :3] for f in frames_rgba if (f[..., 3] > 0).any()])
    lab = srgb_to_lab(ops)
    cent = kmeans(lab, max_colors)
    pal = palette_rgb(reg)
    usable = reg.usable()
    plab = srgb_to_lab(pal[usable])
    idx_for = []; new_used = 0; worst = 0.0
    for c in cent:
        d = np.sqrt(((plab - c) ** 2).sum(-1)); j = int(np.argmin(d))
        if d[j] > de_new and new_used < allow_new:
            # convert centroid back to RGB by nearest original pixel, then GBA-round
            k = int(np.argmin(((lab - c) ** 2).sum(-1)))
            slot = reg.assign(gba_round(ops[k]), owner)
            if slot is not None:
                new_used += 1; idx_for.append(slot); continue
            warn.append('no free palette slot left for a colour %.1f dE away' % d[j])
        worst = max(worst, float(d[j])); idx_for.append(usable[j])
    if worst > 12: warn.append('largest colour shift %.1f dE (visible) - consider allow_new_colors' % worst)
    out = []
    for f in frames_rgba:
        o = np.zeros(f.shape[:2], np.uint8)
        m = f[..., 3] > 0
        if m.any():
            l = srgb_to_lab(f[m][:, :3])
            if direct:
                cand = sorted(set(usable) | set(idx_for)); clab = srgb_to_lab(pal[cand])
                a = np.argmin(de94(l[:, None], clab[None]), 1)
                v = np.array(cand)[a]
            else:
                a = np.argmin(((l[:, None] - cent[None]) ** 2).sum(-1), 1)
                v = np.array(idx_for)[a]
            v[((l - KEY_LAB) ** 2).sum(-1) < 35 ** 2] = 0     # leftover magenta key fringe -> transparent
            o[m] = v
        out.append(o)
    used = sorted(set(np.concatenate([x[x > 0] for x in out]).tolist())) if direct else sorted(set(idx_for))
    return out, used, new_used


def despeckle(idx):
    """Replace single pixels whose 4 neighbours all share one other colour (generator noise)."""
    o = idx.copy(); H, W = idx.shape
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            n = [idx[y - 1, x], idx[y + 1, x], idx[y, x - 1], idx[y, x + 1]]
            if n[0] == n[1] == n[2] == n[3] != idx[y, x]:
                o[y, x] = n[0]
    return o


# ---------- 6. placement ----------
def place_in_cell(idx, cell, warn, label, keep_top=False):
    cw, ch = cell
    ys, xs = np.nonzero(idx)
    out = np.zeros((ch, cw), np.uint8)
    if not len(ys): warn.append('%s: empty frame' % label); return out
    crop = idx[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    if (w > cw or h > ch) and keep_top:                 # portraits keep the head and lose the torso
        warn.append('%s: %dx%d art does not fit the %dx%d cell (cropped at the bottom)' % (label, w, h, cw, ch))
        crop = crop[:ch, max(0, (w - cw) // 2):max(0, (w - cw) // 2) + cw]; h, w = crop.shape
    elif w > cw or h > ch:                              # sprites: shrink the whole pose to fit, never cut it off
        f = min(cw / w, ch / h)
        nw, nh = max(1, int(w * f)), max(1, int(h * f))
        warn.append('%s: %dx%d pose shrunk to %dx%d to fit the %dx%d cell' % (label, w, h, nw, nh, cw, ch))
        yi = (np.arange(nh) * h / nh).astype(int); xi = (np.arange(nw) * w / nw).astype(int)
        crop = crop[yi][:, xi]; h, w = crop.shape
    x0 = (cw - w) // 2; y0 = ch - h                      # feet on the bottom row
    out[y0:y0 + h, x0:x0 + w] = crop
    return out


# ---------- outputs ----------
def save_indexed(idx, pal, path):
    im = Image.fromarray(idx, 'P')
    flat = [int(v) for c in pal for v in c][:768]; flat += [0] * (768 - len(flat))
    im.putpalette(flat); im.info['transparency'] = 0
    im.save(path, transparency=0)


def preview(idx_list, pal, path, scale=4):
    pal = np.asarray(pal, np.uint8)
    tiles = []
    for idx in idx_list:
        rgb = pal[idx].copy(); rgb[idx == 0] = (255, 0, 255)
        tiles.append(np.kron(rgb, np.ones((scale, scale, 1), np.uint8)))
    h = max(t.shape[0] for t in tiles); gap = np.full((h, 4, 3), 40, np.uint8)
    row = np.concatenate(sum([[np.pad(t, ((0, h - t.shape[0]), (0, 0), (0, 0)), constant_values=40), gap] for t in tiles], []), 1)
    Image.fromarray(row).save(path)


def process(spec, raw_dir, out_dir, reg):
    warn = []
    src = np.array(Image.open(os.path.join(raw_dir, spec['file'])).convert('RGBA'))
    kind = spec.get('kind', 'sprite')
    if kind != 'ui':                                   # full screens have no background to key out
        src = remove_background(src)
    if kind == 'ui' and not spec.get('scale'):
        W, H = spec.get('size', [240, 160])                # screen art: the target size fixes the scale
        sx, sy, ox, oy, strength = src.shape[1] / W, src.shape[0] / H, 0.0, 0.0, 0.0
    elif spec.get('scale'):
        sx = sy = float(spec['scale']); _, _, ox, oy, strength = detect_scale(src, smin=sx, smax=sx + 0.01)
    else:
        sx, sy, ox, oy, strength = detect_scale(src)
    px = mode_downsample(src, sx, sy, ox, oy, keep_dark=(kind == 'portrait'))
    px[..., 3] = np.where(px[..., 3] >= 128, 255, 0)
    rep = {'id': spec['id'], 'detected_scale': [round(sx, 2), round(sy, 2)], 'grid_offset': [round(ox, 2), round(oy, 2)], 'grid_strength': round(float(strength), 2),
           'native_size': [int(px.shape[1]), int(px.shape[0])]}
    if kind == 'ui':
        W, H = spec.get('size', [240, 160])
        im = Image.fromarray(px, 'RGBA')
        if im.size != (W, H):
            warn.append('snapped image is %dx%d, resized to %dx%d with nearest-neighbour' % (im.size + (W, H)))
            im = im.resize((W, H), Image.NEAREST)
        n = spec.get('max_colors', 240)
        q = im.convert('RGB').quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        pal = np.array(q.getpalette()[:3 * n]).reshape(-1, 3)
        pal = gba_round(pal)
        idx = np.array(q, np.uint8) + 1                   # keep index 0 for transparency
        pal = np.vstack([[[255, 0, 255]], pal])
        idx[np.array(im)[..., 3] == 0] = 0
        frames = [idx]; rep['colors'] = int(len(np.unique(idx)))
    else:
        raw_frames = split_frames(px, spec)
        cell = spec.get('cell', [32, 32] if kind == 'sprite' else [48, 56])
        th = spec.get('target_height')
        def bbox_h(f):
            ys = np.nonzero(f[..., 3])[0]; return (ys.max() - ys.min() + 1) if len(ys) else 0
        hs = [bbox_h(f) for f in raw_frames if bbox_h(f)]
        bad = (not hs) or max(hs) > cell[1] or (th and abs(np.median(hs) - th) > 0.25 * th)
        if spec.get('scale') and hs:      # a forced scale is trusted (KO / lying poses break the height heuristic)
            bad = False
        if bad:
            # grid snap was unreliable (smooth/fractional generator output): resample each frame to its target height
            th = th or cell[1] - 2
            full = split_frames(src, spec)
            fh = [bbox_h(f) for f in full if bbox_h(f)]
            ref = float(np.median(fh)) if fh else th               # one scale for the whole sheet keeps sizes consistent
            sc = ref / th
            raw_frames = []
            for f in full:
                ys, xs = np.nonzero(f[..., 3])
                if not len(ys): raw_frames.append(np.zeros((1, 1, 4), np.uint8)); continue
                crop = f[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
                d = mode_downsample(crop, sc, sc, 0.0, 0.0, keep_dark=(kind == 'portrait')); d[..., 3] = np.where(d[..., 3] >= 128, 255, 0)
                raw_frames.append(d)
            rep['detected_scale'] = [round(sc, 2), round(sc, 2)]; rep['mode'] = 'resample to target height %d' % th
            if not spec.get('target_height'):
                warn.append('grid not detected; resampled to %dpx tall - set target_height to control the size' % th)
        else:
            rep['mode'] = 'pixel grid'
        cap = spec.get('max_colors', 16 if kind == 'sprite' else 32)
        idxs, used, new = map_to_game_palette(raw_frames, cap, spec.get('allow_new_colors', 0), reg, spec['id'], warn,
                                              direct=spec.get('direct_map', kind == 'portrait'))
        frames = [place_in_cell(despeckle(i), cell, warn, '%s frame %d' % (spec['id'], n), keep_top=(kind == 'portrait')) for n, i in enumerate(idxs)]
        pal = palette_rgb(reg)
        rep.update({'frames': len(frames), 'colors': len(used), 'palette_indices': used, 'new_palette_slots': new})
    os.makedirs(out_dir, exist_ok=True)
    for n, f in enumerate(frames):
        save_indexed(f, pal, os.path.join(out_dir, '%s_%02d.png' % (spec['id'], n)))
    preview(frames, pal, os.path.join(out_dir, '%s_preview.png' % spec['id']))
    rep['warnings'] = warn
    return rep


def plan_new_colors(reg, specs, raw_dir, owner, k=None, de_min=6.0, step=6):
    """Fill a registry's free slots with the colours that best reduce the error across ALL its sheets at once
    (weighted k-means on the pixels the existing palette matches badly). Deterministic for a given art set."""
    k = len(reg.free()) if k is None else min(k, len(reg.free()))
    if k <= 0 or not specs: return 0
    pal = palette_rgb(reg); usable = reg.usable(); plab = srgb_to_lab(pal[usable])
    bad = []
    for sp in specs:
        path = os.path.join(raw_dir, sp['file'])
        if not os.path.exists(path): continue
        im = Image.open(path).convert('RGBA'); im.thumbnail((im.width // 2, im.height // 2))
        a = np.array(im)
        if sp.get('kind', 'sprite') != 'ui': a = remove_background(a)
        op = a[..., 3] >= 128
        er = op[1:-1, 1:-1] & op[:-2, 1:-1] & op[2:, 1:-1] & op[1:-1, :-2] & op[1:-1, 2:]   # skip anti-aliased edges
        px = a[1:-1, 1:-1][er][::step, :3]
        if not len(px): continue
        l = srgb_to_lab(px); d = de94(l[:, None], plab[None]).min(1)
        bad.append(l[d > de_min])
    if not bad: return 0
    bad = np.concatenate(bad)
    if len(bad) < 50: return 0
    if len(bad) > 40000: bad = bad[np.random.default_rng(0).choice(len(bad), 40000, replace=False)]
    cent = kmeans(bad, k)
    lab_all = bad; n = 0
    for c in cent:
        j = int(np.argmin(((lab_all - c) ** 2).sum(-1)))     # a real pixel colour near the centroid
        rgb = gba_round(lab_to_srgb(lab_all[j]))
        if reg.assign(rgb, owner) is not None: n += 1
    return n


def lab_to_srgb(lab):
    L, a, b = lab
    fy = (L + 16) / 116; fx = fy + a / 500; fz = fy - b / 200
    def finv(t): return t ** 3 if t ** 3 > 216 / 24389 else (116 * t - 16) / (24389 / 27)
    xyz = np.array([finv(fx) * 0.95047, finv(fy), finv(fz) * 1.08883])
    M = np.linalg.inv(np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]))
    c = np.clip(M @ xyz, 0, 1)
    c = np.where(c > 0.0031308, 1.055 * c ** (1 / 2.4) - 0.055, 12.92 * c)
    return np.clip(np.round(c * 255), 0, 255).astype(np.int64)


def registries(out_dir):
    """Global registry plus one per act, from log4/art/palette_plan.json (tools/palette_plan.py) when it exists."""
    plan_path = os.path.join(out_dir, '..', 'palette_plan.json')
    if not os.path.exists(plan_path):
        return {None: PaletteRegistry(os.path.join(out_dir, 'palette_alloc.json'))}
    plan = json.load(open(plan_path))
    g = PaletteRegistry(os.path.join(out_dir, 'palette_alloc.json'), plan['global_free'], plan['base'])
    regs = {None: g, 'menu': FilteredRegistry(g, MENU_SLOTS)}
    for name, a in plan['acts'].items():
        regs[name] = PaletteRegistry(os.path.join(out_dir, 'palette_alloc_%s.json' % name), a['free'], a['keep_colors'], g)
    # first run after a reset: plan every registry's new colours from the whole art set (log4/art/specs.json); the
    # menu-visible characters plan first, so they get the global free slots
    all_specs_path = os.path.join(out_dir, '..', 'specs.json'); raw_dir = os.path.join(out_dir, '..', 'raw')
    if os.path.exists(all_specs_path):
        all_specs = json.load(open(all_specs_path))
        fresh_global = not os.path.exists(g.path)
        for name in ['menu', None] + [k for k in regs if k not in ('menu', None)]:
            r = regs[name]
            if name in ('menu', None) and not fresh_global: continue
            if name not in ('menu', None) and os.path.exists(r.path): continue
            mine = [s_ for s_ in all_specs if act_of(s_, out_dir) == name and s_.get('kind') != 'ui']
            n = plan_new_colors(r, mine, raw_dir, 'plan:%s' % (name or 'global'))
            print('-- palette: planned %d new colours for %s (%d sheets)' % (n, name or 'all acts', len(mine)))
            r.save()
    return regs


def act_of(spec, out_dir):
    if 'act' in spec: return spec['act']
    if spec['id'].split('_')[0] in MENU_VISIBLE: return 'menu'    # shown on the Switch Character screen
    plan_path = os.path.join(out_dir, '..', 'palette_plan.json')
    if not os.path.exists(plan_path): return None
    pid = spec['id'].split('_')[0]
    for name, a in json.load(open(plan_path))['acts'].items():
        if pid in a['art']: return name
    return None


def main(spec_path, raw_dir, out_dir):
    specs = json.load(open(spec_path))
    regs = registries(out_dir)
    reports = []
    for sp in specs:
        reg = regs.get(act_of(sp, out_dir), regs[None])
        try:
            r = process(sp, raw_dir, out_dir, reg)
            r['act'] = act_of(sp, out_dir)
        except FileNotFoundError:
            r = {'id': sp['id'], 'warnings': ['raw file %s not found - skipped' % sp['file']]}
        reports.append(r)
        print('%-28s scale %-3s colours %-4s %s' % (r['id'], r.get('detected_scale', '-'), r.get('colors', '-'),
                                                   ('; '.join(r['warnings']) or 'ok')))
    for r_ in regs.values(): r_.save()
    json.dump(reports, open(os.path.join(out_dir, 'report.json'), 'w'), indent=1)
    return reports


if __name__ == '__main__':
    main(*sys.argv[1:4])
