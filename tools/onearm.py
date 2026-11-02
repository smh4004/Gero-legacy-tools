"""Remove Future Gohan's left arm from a LoG2 frame (8bpp LoG2 OBJ indices, 0 = transparent).

LoG2's Future Gohan (actor record 153, likely) is drawn before he loses his left arm. The sprite is ~16 px wide, its
arms are bare skin (sleeveless gi) joined to the face and the open chest, so the edit is geometric:
  front  (facing the camera)  his left arm is on the image's right: skin/wristband right of the torso goes
  back   (facing away)        mirrored: left of the torso
  side   (facing left, the unflipped LoG2 frame): the near arm is his left; its skin drawn over the torso is
         repainted gi orange and skin trailing behind the body is removed. The same pixels are shown mirrored for
         facing right, where the near arm is his right one, so that view is taken from the edited frame too
         (the LoG2 sprite itself shares one image for both side views).
  none   unchanged (KO frames lying on the ground)
"""
import numpy as np

SKIN = [17, 18, 19, 20, 21, 22, 23, 116, 120]
BLUE = [79, 80, 81]
GI = [32, 33, 34, 35]
DARK = [1, 215]


def _rows_below_neck(a):
    gi = np.isin(a, GI).any(1)
    return int(np.argmax(gi)) if gi.any() else a.shape[0]


def remove_arm(a, mode):
    if mode == 'none': return a
    a = a.copy(); h, w = a.shape
    skin = np.isin(a, SKIN); blue = np.isin(a, BLUE); gi = np.isin(a, GI)
    neck = _rows_below_neck(a)
    below = np.arange(h)[:, None] >= neck
    body = (gi | blue) & below
    if not body.any(): return a
    if mode in ('front', 'back'):
        cols = np.nonzero(body)[1]
        cx = np.median(cols)
        # torso half width: the narrowest gi row span between shoulder and belt (arms excluded by the median)
        spans = []
        for y in range(neck, h):
            xs = np.nonzero(gi[y])[0]
            if len(xs) >= 3: spans.append((xs.min(), xs.max()))
        if not spans: return a
        lo = int(np.median([s[0] for s in spans])); hi = int(np.median([s[1] for s in spans]))
        xx = np.arange(w)[None, :]
        out = (xx > hi) if mode == 'front' else (xx < lo)
        rm = out & below & (skin | blue | np.isin(a, DARK))
        # keep the feet/boots: only rows above the bottom quarter of the body
        feet = np.arange(h)[:, None] >= neck + int(0.62 * (h - neck))
        rm &= ~feet
        a[rm] = 0
        return a
    if mode == 'side':
        for y in range(neck, h):
            xs = np.nonzero(gi[y] | blue[y])[0]
            if not len(xs): continue
            lo, hi = xs.min(), xs.max()
            for x in range(w):
                if not skin[y, x]: continue
                if lo < x < hi:                                   # near arm over the torso -> gi
                    nb = [a[y, x + d] for d in (1, -1, 2, -2) if 0 <= x + d < w and a[y, x + d] in GI]
                    a[y, x] = nb[0] if nb else 34
                elif x >= hi:                                     # trailing behind the back
                    a[y, x] = 0
        return a
    raise ValueError(mode)


SSJ_MID, SSJ_HI, SSJ_SHADE, SSJ_EDGE = 46, 44, 138, 23   # LoG2 Super Saiyan hair: yellow, pale, gold, brown outline


def ssj_hair(a):
    """Recolour the black hair of a LoG2 frame gold (Super Saiyan): the dark pixels connected to the top of the head
    above the neck (the gi's first row). Eyes stay dark (enclosed by skin, not connected to the hair)."""
    from scipy import ndimage
    a = a.copy(); h, w = a.shape
    neck = _rows_below_neck(a)
    dark = np.isin(a, DARK) & (np.arange(h)[:, None] < neck)
    lab, n = ndimage.label(dark, np.ones((3, 3), bool))
    if not n: return a
    sizes = ndimage.sum(dark, lab, range(1, n + 1))
    hair = lab == 1 + int(np.argmax(sizes))
    opaque = a > 0
    edge = hair & ~ndimage.binary_erosion(opaque, ndimage.generate_binary_structure(2, 1), border_value=0)
    shade = a == 215
    ring = hair & ~edge & ndimage.binary_dilation(edge, ndimage.generate_binary_structure(2, 1))
    a[hair] = SSJ_MID
    a[hair & shade] = SSJ_HI
    a[ring] = SSJ_SHADE
    a[edge] = SSJ_EDGE
    return a
