"""Gero's Legacy hype trailer (v6, 2026-11-02). New format: no dialogue, no artwork. Real gameplay footage, cut on the
music's onsets. Short feature call-outs in a green CRT terminal font (VT323), typed out like Dr. Gero's computer. A
quiet, ominous opening, a fast feature montage, a short tease, and an ending on Gero's terminal typing COMING SOON.
Music: LoG2 "Era of Darkness" (the user's MP3) from 0 s.
usage: python3 trailer6.py <music.mp3> <out.mp4>"""
import os, subprocess, sys, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SP = '/tmp/claude-0/-home-claude/b76ce272-737f-5f00-95c7-c5425ffc809f/scratchpad'
TR, Z = SP + '/tr', SP + '/tz4'
W, H, FPS = 1920, 1080, 30
FONT = TR + '/fonts/VT323.ttf'
GREEN = (120, 255, 150)
rng = random.Random(7)

def clip(name): return (TR if os.path.exists('%s/%s/%s.mkv' % (TR, name, name)) else Z) + '/%s/%s.mkv' % (name, name)

# ---------- the edit: (start, end, clip, src start, speed, crop top, zoom from, zoom to, focus x, focus y, grade)
#   grade = (saturation, brightness, contrast)
DARK, MOOD, LIVE = (0.55, 0.62, 1.12), (0.7, 0.8, 1.1), (1.0, 1.0, 1.06)
SHOTS = [
    (1.0, 6.0, 'lab', 1.3, 0.8, 0, 1.00, 1.12, 0.45, 0.55, DARK),
    (6.0, 11.0, 'pods', 1.3, 0.8, 0, 1.15, 1.00, 0.5, 0.4, DARK),
    (11.0, 15.5, 'rainc', 1.5, 0.8, 10, 1.00, 1.15, 0.38, 0.6, DARK),
    (15.5, 19.6, 'nightw', 0.9, 0.95, 18, 1.05, 1.15, 0.5, 0.55, DARK),
    (19.75, 25.1, 'field', 3.0, 1.0, 20, 1.00, 1.08, 0.5, 0.5, LIVE),
    (25.1, 28.0, 'lapis', 3.6, 1.0, 22, 1.10, 1.18, 0.55, 0.55, LIVE),
    (28.0, 32.75, 'collect', 3.6, 1.0, 22, 1.05, 1.15, 0.6, 0.55, MOOD),
    (32.75, 38.75, 'veg', 1.6, 1.0, 22, 1.00, 1.10, 0.5, 0.5, LIVE),
    (38.75, 43.1, 'tank', 3.6, 1.0, 22, 1.00, 1.10, 0.45, 0.5, LIVE),
    (43.1, 46.75, 'wm', 2.0, 1.0, 0, 1.00, 1.06, 0.5, 0.45, LIVE),
    (46.75, 49.7, 'lookout', 2.9, 1.0, 22, 1.12, 1.2, 0.5, 0.42, LIVE),
    (49.7, 53.45, 'desert', 4.5, 1.0, 22, 1.00, 1.12, 0.6, 0.45, LIVE),
    (53.45, 57.65, 'outfit', 1.4, 1.0, 22, 1.10, 1.25, 0.42, 0.55, LIVE),
    (57.65, 61.6, 's13c', 3.6, 1.0, 22, 1.00, 1.10, 0.5, 0.45, LIVE),
    (61.6, 62.3, 'osc', 2.9, 1.0, 22, 1.0, 1.05, 0.5, 0.5, LIVE),
    (62.3, 63.0, 'nataday', 3.6, 1.0, 22, 1.14, 1.18, 0.5, 0.42, LIVE),
    (63.0, 63.7, 'papaya', 4.0, 1.0, 22, 1.0, 1.05, 0.5, 0.5, LIVE),
    (63.7, 64.45, 'land', 2.5, 1.0, 10, 1.0, 1.05, 0.5, 0.5, LIVE),
    (65.0, 71.4, 'cellinc', 1.0, 0.7, 0, 1.00, 1.35, 0.5, 0.62, (0.6, 0.55, 1.15)),
]
FLASH = [19.75, 32.75, 38.75, 61.6]                 # white hits
DIP = [(5.8, 6.2), (10.8, 11.2), (15.3, 15.7)]      # dips to black in the opening
# ---------- call-outs (start, end, text, where)  where: 'low' lower-left, 'mid' centred
CAPS = [
    (2.4, 5.6, 'BEFORE THE ANDROIDS...', 'mid'),
    (11.8, 15.1, 'A SCIENTIST. TWO RUNAWAYS.', 'mid'),
    (16.2, 19.3, 'THREE ACTS.', 'mid'),
    (20.2, 24.8, 'ACT I // THE DOCTOR', 'low'),
    (25.4, 32.5, 'ACT II // THE TWINS', 'low'),
    (33.1, 38.4, 'ACT III // THE ANDROIDS', 'low'),
    (39.0, 42.9, 'PILOT GERO\'S COMBAT DRONE', 'low'),
    (43.35, 46.5, 'FLY THE WORLD MAP', 'low'),
    (47.0, 49.5, 'SIDE QUESTS. HIDDEN MEMORIES.', 'low'),
    (49.95, 53.2, 'OPTIONAL BOSSES', 'low'),
    (53.7, 57.4, 'CHANGE OUTFITS ON THE FLY', 'low'),
    (57.9, 61.4, 'ALL-NEW BOSS FIGHTS', 'low'),
    (61.75, 64.3, 'LEGACY OF GOKU II MAPS // BUU\'S FURY ENGINE', 'low'),
    (66.3, 71.0, 'SPECIMEN STATUS: ALIVE', 'mid'),
]
TERM_START, END = 71.8, 86.0
TERM = [  # (time, text) lines typed on Gero's terminal
    (72.4, 'RED RIBBON ARMY // RESEARCH DIVISION'),
    (73.6, 'DR. GERO - PRIVATE TERMINAL'),
    (75.0, '> LOAD PROJECT "GERO\'S LEGACY"'),
    (76.6, '#BAR'),
    (79.2, '> STATUS'),
    (80.2, 'COMING SOON'),
]
OFF = 84.6                                          # CRT power-off

_font = {}
def font(sz):
    if sz not in _font: _font[sz] = ImageFont.truetype(FONT, sz)
    return _font[sz]

_cache = {}
def text_layer(s, sz, cursor):
    """RGBA strip: phosphor-green text + glow + optional block cursor."""
    k = (s, sz, cursor)
    if k in _cache: return _cache[k]
    f = font(sz); x0, y0, x1, y1 = f.getbbox(s + 'M')
    w, h = x1 + 40, max(y1, sz) + 30
    base = Image.new('L', (w, h), 0); d = ImageDraw.Draw(base)
    d.text((20, 10), s, font=f, fill=255)
    if cursor:
        cx = 20 + (f.getlength(s) if s else 0) + 4
        d.rectangle([cx, 10 + sz * 0.18, cx + sz * 0.42, 10 + sz * 0.92], fill=255)
    glow = base.filter(ImageFilter.GaussianBlur(sz / 9))
    a = np.maximum(np.array(base, np.float32), np.array(glow, np.float32) * 0.85)
    lay = np.zeros((h, w, 4), np.float32); lay[..., :3] = GREEN; lay[..., 3] = a / 255
    _cache[k] = lay
    return lay


def blit(frame, lay, x, y, alpha=1.0):
    h, w = lay.shape[:2]
    x, y = int(x), int(y); x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x or y1 <= y: return
    l = lay[:y1 - y, :x1 - x]; a = l[..., 3:4] * alpha
    frame[y:y1, x:x1] = frame[y:y1, x:x1] * (1 - a) + l[..., :3] * a


def typed(s, t0, t, cps=34):
    n = int(max(0, t - t0) * cps)
    return s[:n], n >= len(s)


def caption(frame, t):
    for (a, b, s, where) in CAPS:
        if not a <= t < b: continue
        shown, done = typed(s, a, t)
        blink = (not done) or (int(t * 2.5) % 2 == 0)
        fade = min(1.0, (b - t) / 0.25)
        sz = 80 if where == 'low' else 84
        lay = text_layer(shown, sz, blink)
        if where == 'low':
            frame *= 1 - BAND * fade
            blit(frame, lay, 80, H - 175, fade)
        else:
            full = font(sz).getlength(s)
            blit(frame, lay, (W - full) / 2 - 20, H / 2 - sz / 2 - 10, fade)


# ---------- footage
def frames_of(sh):
    a, b, name, s0, speed, cy, z0, z1, fx, fy, grade = sh
    n = int(round((b - a) * FPS))
    src_dur = (b - a) * speed + 0.2
    p = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', str(s0), '-t', str(src_dur), '-i', clip(name),
                        '-vf', 'setpts=PTS/%g,fps=%d' % (speed, FPS), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                       capture_output=True, check=True).stdout
    fr = np.frombuffer(p, np.uint8).reshape(-1, 160, 240, 3)
    assert len(fr), name
    return fr, n


def render_shot(fr, i, n, sh):
    a, b, name, s0, speed, cy, z0, z1, fx, fy, grade = sh
    f = fr[min(i, len(fr) - 1)][cy:cy + 135]
    if f.shape[0] < 135: f = np.vstack([f, np.zeros((135 - f.shape[0], 240, 3), np.uint8)])
    big = Image.fromarray(f).resize((W, H), Image.NEAREST)
    u = i / max(1, n - 1); u = u * u * (3 - 2 * u)              # ease
    z = z0 + (z1 - z0) * u
    if z > 1.001:
        cw, ch = W / z, H / z
        x = min(max(fx * W - cw / 2, 0), W - cw); y = min(max(fy * H - ch / 2, 0), H - ch)
        big = big.resize((W, H), Image.BICUBIC, box=(x, y, x + cw, y + ch))
    out = np.asarray(big, np.float32)
    sat, br, con = grade
    g = out.mean(2, keepdims=True); out = g + (out - g) * sat
    out = ((out / 255 - 0.5) * con + 0.5) * 255 * br
    return out


# ---------- the terminal
def terminal(t):
    fr = np.zeros((H, W, 3), np.float32); fr[:] = (4, 10, 6)
    # faint raster + slow roll bar
    roll = (t * 140) % H
    yy = np.arange(H)[:, None]
    fr += (np.exp(-((yy - roll) / 60.0) ** 2) * 10)[..., None] * np.array([0.4, 1.0, 0.6])
    sz = 82; x0, y0, lh = 170, 170, 112
    for k, (ts, s) in enumerate(TERM):
        if t < ts: break
        y = y0 + k * lh
        last = (k == len(TERM) - 1) or t < TERM[k + 1][0]
        if s == '#BAR':
            p = min(1.0, max(0.0, (t - ts) / 2.1)); nb = 28
            fill = int(p * nb)
            bar = '[' + '#' * fill + '.' * (nb - fill) + '] %3d%%' % int(p * 100)
            blit(fr, text_layer(bar, sz, False), x0, y)
            continue
        cps = 22 if s == 'COMING SOON' else 40
        shown, done = typed(s, ts, t, cps)
        cur = last and ((not done) or int(t * 2.2) % 2 == 0)
        size = 150 if s == 'COMING SOON' else sz
        yo = y + (12 if s == 'COMING SOON' else 0)
        blit(fr, text_layer(shown, size, cur), x0, yo)
    fr *= 0.97 + 0.03 * math.sin(t * 50)                       # phosphor flicker
    return fr


def crt_off(fr, u):
    """u 0..1: the picture collapses to a line, then to a dot."""
    out = np.zeros_like(fr)
    if u < 0.6:
        hh = max(2, int(H * (1 - u / 0.6) ** 2))
        img = Image.fromarray(np.clip(fr, 0, 255).astype(np.uint8)).resize((W, hh), Image.BILINEAR)
        a = np.asarray(img, np.float32) * (1 + u * 2)
        out[(H - hh) // 2:(H - hh) // 2 + hh] = a
    else:
        v = 1 - (u - 0.6) / 0.4; ww = max(2, int(W * v * v))
        out[H // 2 - 2:H // 2 + 2, (W - ww) // 2:(W + ww) // 2] = 255 * v
    return out


# ---------- global look
yy, xx = np.mgrid[0:H, 0:W]
VIG = (1 - 0.42 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)).clip(0.45, 1)[..., None].astype(np.float32)
SCAN = np.ones((H, 1, 1), np.float32); SCAN[1::3] = 0.86
BAND = (np.clip((yy[:, :1] - H * 0.68) / (H * 0.32), 0, 1) ** 1.3 * 0.72)[..., None].astype(np.float32)   # dark floor behind low captions


def make_frame(t, fi, get):
    frame = np.zeros((H, W, 3), np.float32)
    sh = next((s for s in SHOTS if s[0] <= t < s[1]), None)
    if sh:
        fr, n = get(sh); i = int(round((t - sh[0]) * FPS))
        frame = render_shot(fr, i, n, sh)
        fin = min(1.0, (t - sh[0]) / 0.5) if sh[0] < 19 or sh[2] == 'cellinc' else 1.0
        fout = min(1.0, (sh[1] - t) / 0.5) if sh[1] < 19.7 or sh[2] == 'cellinc' else 1.0
        frame *= min(fin, fout)
        if sh[2] == 'cellinc' and rng.random() < 0.08:          # signal tearing in the tease
            r0 = rng.randrange(0, H - 120); hgt = rng.randrange(20, 120); dx = rng.randrange(-60, 60)
            frame[r0:r0 + hgt] = np.roll(frame[r0:r0 + hgt], dx, axis=1)
            frame[r0:r0 + hgt, :, 0] = np.roll(frame[r0:r0 + hgt, :, 0], 8, axis=1)
    for a, b in DIP:
        if a <= t < b: frame *= abs((t - (a + b) / 2) / ((b - a) / 2))
    if TERM_START <= t:
        tf = terminal(t)
        if t < TERM_START + 0.35: tf *= (t - TERM_START) / 0.35 * (1 + 0.6 * rng.random())
        if t >= OFF: tf = crt_off(tf, min(1.0, (t - OFF) / 0.55))
        frame = tf
    caption(frame, t)
    for ft in FLASH:
        if ft <= t < ft + 0.2: frame = frame + (255 - frame) * (1 - (t - ft) / 0.2) * 0.85
    frame = frame * VIG * SCAN
    frame += np.random.default_rng(fi).normal(0, 2.0, (H // 4, W // 4, 1)).repeat(4, 0).repeat(4, 1)   # light grain
    return frame


def main(mp3, out):
    total = int(END * FPS)
    loaded = {}
    def get(sh):
        k = id(sh)
        if k not in loaded: loaded.clear(); loaded[k] = frames_of(sh)
        return loaded[k]
    enc = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
                            '-r', str(FPS), '-i', '-', '-ss', '0', '-t', str(END), '-i', mp3,
                            '-filter_complex', '[1:a]afade=t=in:d=1.0,afade=t=out:st=%g:d=%g[a]' % (OFF - 3.2, END - OFF + 3.2),
                            '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19',
                            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-shortest', out], stdin=subprocess.PIPE)
    for fi in range(total):
        t = fi / FPS
        frame = make_frame(t, fi, get)
        enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
        if fi % 300 == 0: print('%.1fs' % t, flush=True)
    enc.stdin.close(); enc.wait()


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
