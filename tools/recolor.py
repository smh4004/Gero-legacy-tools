"""Alternate outfits by recolouring an actor's frames (arrays of BF OBJ palette indices). Only existing palette colours
are used (user rule 2026-11-02: never add, merge or change palette colours for this).

Spec (actors.json "recolor"):
  {"anchors": {"neck": [idx...], "waist": [idx...]},       per-frame rows (see below)
   "rules": [{"from": [idx...], "to": [idx...]}            pairwise
             {"from": [idx...], "ramp": [idx...]}          by brightness rank (from's darkest -> ramp's first)
             ... "where": {"below": "neck", "above": "waist", "interior": true, "not_near": [idx...]}]}
Anchors per frame: "neck" = top row of the widest band of the neck set inside the upper 60% of the figure (fallback 0.30 of its height),
"waist" = first row of the waist set below the neck (fallback 0.62), or with "waist_last" the last row of that set. "below"/"above" are strict. "interior" skips
pixels 4-adjacent to transparency (outlines stay black). "not_near" skips pixels 4-adjacent to the listed indices
(e.g. eyes next to skin). "touching" keeps only connected patches that touch the listed colours. Rules all read the original frame, so they never chain."""
import json, os
import numpy as np

_pal = None


def palette():
    global _pal
    if _pal is None:
        import artclean
        here = os.path.dirname(os.path.abspath(__file__))
        regs = artclean.registries(os.path.join(here, '..', 'log4', 'art', 'clean'))
        _pal = np.array(artclean.palette_rgb(regs[None]), float)
    return _pal


def lum(i):
    r, g, b = palette()[i]; return 0.299 * r + 0.587 * g + 0.114 * b


def _pairs(rule):
    src = rule['from']
    if 'to' in rule: return dict(zip(src, rule['to']))
    ramp = rule['ramp']; s = sorted(src, key=lum); n = len(s)
    return {c: ramp[min(len(ramp) - 1, int(k * len(ramp) / n))] for k, c in enumerate(s)}


def _near(mask):
    m = np.zeros_like(mask)
    m[1:] |= mask[:-1]; m[:-1] |= mask[1:]; m[:, 1:] |= mask[:, :-1]; m[:, :-1] |= mask[:, 1:]
    return m


def anchors(f, spec):
    rows = np.nonzero((f != 0).any(1))[0]
    if not len(rows): return {}
    top, bot = rows[0], rows[-1]; h = bot - top + 1
    a = {'top': top, 'bottom': bot}
    an = spec.get('anchors', {})
    neck = None
    if 'neck' in an:
        cnt = np.isin(f, an['neck']).sum(1); cnt[int(top + 0.6 * h) + 1:] = 0
        if cnt.any():                                      # the widest band (a scarf / collar), not a stray fist
            neck = int(cnt.argmax())
            while neck > top and cnt[neck - 1] > 0: neck -= 1
    a['neck'] = neck if neck is not None else top + int(0.30 * h)
    waist = None
    if 'waist' in an:
        r = np.nonzero(np.isin(f, an['waist']).any(1))[0]; r = r[r > a['neck']]
        if len(r): waist = r[0]
    a['waist'] = waist if waist is not None else top + int(0.62 * h)
    if 'waist_last' in an:                                  # waist = last row of the set (e.g. a vest's colours)
        r = np.nonzero(np.isin(f, an['waist_last']).any(1))[0]; r = r[r > a['neck']]
        if len(r): a['waist'] = r[-1]
    a['feet'] = bot + 1                                    # "feet" = first row of the set below the waist (boots)
    if 'feet' in an:
        r = np.nonzero(np.isin(f, an['feet']).any(1))[0]; r = r[r > a['waist']]
        if len(r): a['feet'] = r[0]
    return a


def make(spec):
    if isinstance(spec, str): spec = json.loads(spec)
    rules = [(_pairs(r), r.get('where', {})) for r in spec['rules']]

    def recol(f):
        f = np.asarray(f); out = f.copy(); a = None
        transparent = _near(f == 0)
        for pairs, w in rules:
            lut = np.arange(256, dtype=f.dtype)
            for s, d in pairs.items(): lut[s] = d
            m = np.isin(f, list(pairs))
            if not m.any(): continue
            if w:
                if a is None: a = anchors(f, spec)
                if not a: continue
                rr = np.arange(f.shape[0])[:, None]
                if 'below' in w: m &= rr > a[w['below']]
                if 'above' in w: m &= rr < a[w['above']]
                if 'below_eq' in w: m &= rr >= a[w['below_eq']]
                if w.get('interior'): m &= ~transparent
                if 'not_near' in w: m &= ~_near(np.isin(f, w['not_near']))
                if 'touching' in w:                        # keep only patches that touch these colours (drops
                    from scipy.ndimage import label        # free-floating attack swooshes drawn in sleeve colours)
                    lab, n = label(m, structure=np.ones((3, 3)))
                    near = _near(np.isin(f, w['touching']))
                    keep = np.unique(lab[near & m]); m &= np.isin(lab, keep[keep > 0])
            out[m] = lut[f[m]]
        return out
    return recol
