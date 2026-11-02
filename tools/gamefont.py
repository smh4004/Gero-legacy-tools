"""The game's dialogue font, lifted from emulator footage (for teaser text in the game's own lettering).

Dialogue text is pure white (255,255,255) on the box. A fully typed page is found where the box's white-pixel count holds
still for a while; its glyphs are cut by empty columns (letters are >= 1 px apart, words >= 4) and matched to a known
script line by the pattern of word lengths (a page is a run of whole words of one line). Each character keeps the bitmap
it shows most often. Cells are 14 rows: 10 above the baseline row's bottom + 3 below for descenders.

usage: python3 tools/gamefont.py build <atlas.npz> <scene files ...> -- <videos (.mkv) or frames (.png) ...>
       python3 tools/gamefont.py render <atlas.npz> "<text>" <out.png> [scale]
"""
import re, subprocess, sys
from collections import Counter, defaultdict
import numpy as np
from PIL import Image

ROWS = (84, 152)                 # dialogue box text rows (below the HUD, above the bottom edge)
UP, DOWN = 10, 3                 # cell rows above / below the baseline row
LETTER_GAP, WORD_GAP = 1, 5
PARTS = {'W': 2, '"': 2}           # characters drawn as separate marks (W = two Vs)


def script_lines(paths):
    out = []
    for p in paths:
        for ln in open(p):
            ln = ln.rstrip('\n')
            m = re.match(r'(say \S+|narrate|journal) (.*)', ln)
            if not m: continue
            txt = m.group(2)
            out.append('Journal Entry: ' + txt if m.group(1) == 'journal' else txt)
    return out


def text_mask(fr):
    """White text pixels of the dialogue box. Two layouts: narration (centred box x 40-200, its yellow left border at
    x ~40) -> text x 44-197; speech (box x 8-160 + portrait) -> text x 14-158."""
    w = (fr[..., 0] == 255) & (fr[..., 1] == 255) & (fr[..., 2] == 255)
    edge = fr[92:146, 36:46].astype(int)
    gold = (edge[..., 0] > 160) & (edge[..., 2] < 60)  # the frame is an orange-yellow gradient
    x0, x1 = (44, 198) if gold.sum(0).max() > 40 else (14, 159)
    m = np.zeros_like(w); m[ROWS[0]:ROWS[1], x0:x1] = w[ROWS[0]:ROWS[1], x0:x1]
    for y in range(ROWS[0], ROWS[1]):                  # box border strokes: white runs of 10+ px (no glyph is that wide)
        r = m[y].astype(np.int8); d = np.diff(np.concatenate([[0], r, [0]]))
        for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
            if b - a >= 10: m[y, a:b] = False
    return m


def page_glyphs(m):
    """-> [line: [word: [glyph bitmap (14 x w bool)]]]"""
    rows = np.where(m.any(1))[0]
    if not len(rows): return []
    bands, start = [], rows[0]                       # lines are 14 px apart with a single empty row between them
    for a, b in zip(rows, rows[1:]):
        if b - a > 1: bands.append([start, a]); start = b
    bands.append([start, rows[-1]])
    merged = []                                      # a thin band (i dots, a lone mark) joins the line just below it
    for bd in bands:
        if merged and merged[-1][1] - merged[-1][0] < 4 and bd[0] - merged[-1][1] <= 3: merged[-1][1] = bd[1]
        else: merged.append(bd)
    bands = merged
    lines = []
    for r0, r1 in bands:
        if r1 - r0 < 5: continue
        cols = np.where(m[r0:r1 + 1].any(0))[0]
        runs, s = [], cols[0]
        for a, b in zip(cols, cols[1:]):
            if b != a + 1: runs.append((s, a, b - a - 1)); s = b
        runs.append((s, cols[-1], 99))
        # drop lone marks (box corner highlights, the page arrow): > 12 px from any other mark on the line
        runs = [r for i, r in enumerate(runs) if not ((runs[i - 1][2] if i else 99) > 12 and r[2] > 12)] if len(runs) > 1 else runs
        if not runs: continue
        bottoms = Counter(int(np.where(m[r0:r1 + 1, a:b + 1].any(1))[0].max()) + r0 for a, b, _ in runs)
        base = bottoms.most_common(1)[0][0]
        words, cur = [], []
        for a, b, gap in runs:
            g = np.zeros((UP + 1 + DOWN, b - a + 1), bool)
            for i, y in enumerate(range(base - UP, base + DOWN + 1)):
                if 0 <= y < m.shape[0]: g[i] = m[y, a:b + 1]
            cur.append(g)
            if gap >= 4: words.append(cur); cur = []
        if cur: words.append(cur)
        lines.append(words)
    return lines


def match(lines, script):
    """Glyph words -> characters, if the page's word lengths are a run of whole words of a script line."""
    words = [w for ln in lines for w in ln]
    lens = [len(w) for w in words]
    for s in script:
        sw = s.split()
        sl = [sum(PARTS.get(c, 1) for c in x) for x in sw]
        for i in range(len(sl) - len(lens) + 1):
            if sl[i:i + len(lens)] == lens:
                out = []
                for w, txt in zip(words, sw[i:i + len(lens)]):
                    k = 0
                    for c in txt:
                        n = PARTS.get(c, 1)
                        gs = w[k:k + n]; k += n
                        g = gs[0] if n == 1 else np.concatenate(sum([[x, np.zeros((x.shape[0], 1), bool)] for x in gs], [])[:-1], 1)
                        out.append((c, g))
                return out
    return None


def frames(src):
    if src.endswith('.png'):
        yield np.array(Image.open(src).convert('RGB')); return
    p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(240 * 160 * 3)
        if len(b) < 240 * 160 * 3: break
        yield np.frombuffer(b, np.uint8).reshape(160, 240, 3)


def plateaus(src, hold=12):
    """Frames whose box text has stopped changing for `hold` frames (fully typed pages); one per page."""
    last, n, done = None, 0, False
    for fr in frames(src):
        m = text_mask(fr)
        if last is not None and m.any() and (m == last).all():
            n += 1
            if n == hold and not done: done = True; yield m
        else:
            n, done = 0, False
        last = m
    if src.endswith('.png') and last is not None and last.any(): yield last


def build(atlas, scenes, srcs):
    """Each distinct page counts once (a page left on screen would otherwise outvote everything); a second pass drops
    pages whose glyphs mostly disagree with the first-pass choice (a mis-cut page shifts every letter after the cut)."""
    script = script_lines(scenes)
    pages, done = [], set()
    for src in srcs:
        for m in plateaus(src):
            key = m.tobytes()
            if key in done: continue
            done.add(key)
            got = match(page_glyphs(m), script)
            if got: pages.append([(c, g) for c, g in got if not (c.isalnum() and not g[:UP].any())])
    def vote(pgs):
        seen = defaultdict(Counter); bm = {}
        for pg in pgs:
            for c, g in pg:
                k = (g.shape[1], g.tobytes()); seen[c][k] += 1; bm[k] = g
        return {c: bm[cnt.most_common(1)[0][0]] for c, cnt in seen.items()}
    first = vote(pages)
    agree = lambda pg: np.mean([g.shape == first[c].shape and (g == first[c]).all() for c, g in pg])
    good = [pg for pg in pages if agree(pg) >= 0.8]
    chars = vote(good)
    np.savez(atlas, **{'c%04x' % ord(c): g for c, g in chars.items()})
    print('distinct pages %d matched, %d consistent, %d characters: %s' % (len(pages), len(good), len(chars), ''.join(sorted(chars))))


def load(atlas):
    z = np.load(atlas)
    return {chr(int(k[1:], 16)): z[k] for k in z.files}


def render(chars, text):
    """-> bool array (14 x w); unknown characters raise KeyError."""
    parts = []
    for i, c in enumerate(text):
        if c == ' ': parts.append(np.zeros((UP + 1 + DOWN, WORD_GAP), bool)); continue
        parts.append(chars[c])
        if i + 1 < len(text) and text[i + 1] != ' ': parts.append(np.zeros((UP + 1 + DOWN, LETTER_GAP), bool))
    return np.concatenate(parts, 1)


if __name__ == '__main__':
    if sys.argv[1] == 'build':
        k = sys.argv.index('--')
        build(sys.argv[2], sys.argv[3:k], sys.argv[k + 1:])
    else:
        g = render(load(sys.argv[2]), sys.argv[3]); s = int(sys.argv[5]) if len(sys.argv) > 5 else 4
        Image.fromarray((np.kron(g, np.ones((s, s), bool)) * 255).astype(np.uint8)).save(sys.argv[4])
