"""Draft teaser v2 for Gero's Legacy: ominous and vague. Letterboxed, darkened emulator footage that dissolves from shot
to shot, three faint lines from the game's own narration (in its own font) in the lower bar, logo and 17/18 art only at the end.
usage: python3 teaser2.py <music.mp3> <out.mp4>"""
import os, subprocess, sys
import numpy as np
from PIL import Image

SP = '/tmp/claude-0/-home-claude/b76ce272-737f-5f00-95c7-c5425ffc809f/scratchpad'
TZ, V, T2 = SP + '/tz', SP + '/v61', SP + '/t2'
OUT = SP + '/teaser/build2'
os.makedirs(OUT, exist_ok=True)
W, H, FPS = 1920, 1080, 60
S = 7                                   # 240x128 strip (rows 24-151: HUD cropped off) at 7x = 1680x896
GW, GH = 240 * S, 128 * S
GX, GY = (W - GW) // 2, (H - GH) // 2
ART = '/home/claude/rom/log4/art/raw/U1_title.png'
ENC = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-r', str(FPS)]
GRADE = 'eq=saturation=0.72:gamma=0.86:contrast=1.06'


def run(args): subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + args, check=True)


def seg(name, src, start, dur, crop_y=24, grade=GRADE, extra=''):
    """One shot: crop a 240x128 strip, nearest-neighbour 7x, grade, centre on black, vignette."""
    vf = ('fps=%d,crop=240:128:0:%d,scale=%d:%d:flags=neighbor,%s,pad=%d:%d:%d:%d:black,vignette=angle=PI/5'
          % (FPS, crop_y, GW, GH, grade, W, H, GX, GY)) + extra
    run(['-ss', str(start), '-t', str(dur), '-i', src, '-vf', vf, '-an'] + ENC + [OUT + '/%s.mp4' % name])
    got = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                OUT + '/%s.mp4' % name], capture_output=True, text=True).stdout)
    assert got >= dur - 0.05, 'shot %s: source too short (%.2f of %.2f s)' % (name, got, dur)
    return name, dur


# Text uses the game's own dialogue font: glyph runs lifted from two intro narration frames (white pixels of the box),
# mask rows/cols below (fontmask.npy, 0,0 = screen 48,8). Word gap in the font = 5 px.
FONT_MASK = SP + '/teaser/fontmask.npy'
PIECES = {  # name: (row band, col range) -> ascender top is found inside the band
    'a_soldier_that_never_tires': ((3, 17), (7, 134)), 'never_doubts_and_never': ((17, 31), (12, 131)),
    'disobeys...': ((31, 45), (20, 71)), 'built_by_human': ((45, 59), (56, 129)), 'hands.': ((68, 84), (55, 86))}
TEXT = {'t1': ['a_soldier_that_never_tires'], 't2': ['never_doubts_and_never', 'disobeys...'],
        't3': ['built_by_human', 'hands.']}
TS = 4                                   # text scale (game pixels -> video pixels)


def piece(m, name):
    (r0, r1), (c0, c1) = PIECES[name]
    band = m[r0:r1, c0:c1]
    base = np.where(band.sum(1) >= 8)[0].max()     # baseline = bottom row of the lowercase letters
    out = np.zeros((13, c1 - c0), bool)            # 9 rows up to the baseline + 3 for descenders
    for i in range(13):
        r = base - 9 + i
        if 0 <= r < band.shape[0]: out[i] = band[r]
    return out


def text_png(name, key):
    import numpy as np
    m = np.load(FONT_MASK)
    parts = [piece(m, p) for p in TEXT[key]]
    h = max(p.shape[0] for p in parts)
    row = np.zeros((h, sum(p.shape[1] for p in parts) + 5 * (len(parts) - 1)), bool); x = 0
    for p in parts: row[:p.shape[0], x:x + p.shape[1]] = p; x += p.shape[1] + 5
    big = np.kron(row, np.ones((TS, TS), bool))
    img = np.zeros((H, W, 4), np.uint8)
    y = GY + GH + (GY - 9 * TS) // 2; x = (W - big.shape[1]) // 2
    img[y:y + big.shape[0], x:x + big.shape[1]][big] = (212, 206, 200, 215)
    Image.fromarray(img, 'RGBA').save(OUT + '/%s.png' % name)


def art_seg(name, path, dur, zoom=(1.0, 1.07), focus=(0.5, 0.40)):
    """The full-resolution title art (not the 240x160 game screen): widescreen crop above its menu bar, a slow push-in
    rendered with bicubic resampling, then the same grade/letterbox/vignette as the footage, rising out of black."""
    art = Image.open(path).convert('RGB'); aw = art.width; ah = round(aw * GH / GW)       # crop to 1680:896 from the top
    art = art.crop((0, 0, aw, ah))
    n = round(dur * FPS)
    vf = 'eq=saturation=0.85:gamma=0.92,pad=%d:%d:%d:%d:black,vignette=angle=PI/5,fade=t=in:st=0:d=3.2' % (W, H, GX, GY)
    p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (GW, GH),
                          '-r', str(FPS), '-i', '-', '-vf', vf, '-an'] + ENC + [OUT + '/%s.mp4' % name], stdin=subprocess.PIPE)
    for i in range(n):
        t = i / max(1, n - 1); z = zoom[0] + (zoom[1] - zoom[0]) * (t * t * (3 - 2 * t))   # eased
        cw, ch = aw / z, ah / z
        cx = focus[0] * aw; cy = focus[1] * ah
        x0 = min(max(cx - cw / 2, 0), aw - cw); y0 = min(max(cy - ch / 2, 0), ah - ch)
        frame = art.transform((GW, GH), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BICUBIC)
        p.stdin.write(frame.tobytes())
    p.stdin.close(); p.wait()
    return name, dur


def main():
    music, out = sys.argv[1], sys.argv[2]
    # shots (name, dur) and the transition INTO each following shot (kind, length)
    shots = [
        seg('a', T2 + '/r63.mkv', 5.2, 7.0),                     # Gero walks up to the incubator pod (camera rises)
        seg('b', T2 + '/r62.mkv', 0.3, 7.0),                     # the tank room, fading in from the door transition
        seg('c', V + '/drone2.mkv', 0.0, 8.3),                   # a drone drifting through the main lab
        seg('d', V + '/rooms.mkv', 0.0, 4.6),                    # on the swell: Gero walks through the lab door
        seg('e', TZ + '/walk1.mkv', 0.0, 3.0),                   # main lab
        art_seg('f', ART, 5.0),                                  # 17 & 18: full-resolution title art, slow push-in
        seg('g', TZ + '/intro.mkv', 34.45, 4.4, crop_y=16, grade='null'),   # GERO'S LEGACY, after its last flash
    ]
    trans = [('dissolve', 1.2), ('dissolve', 1.2), ('fadeblack', 0.8), ('dissolve', 0.6), ('fadeblack', 1.0),
             ('fadeblack', 1.0)]
    inputs, fc, prev, t = [], [], '0:v', shots[0][1]
    for n, _ in shots: inputs += ['-i', OUT + '/%s.mp4' % n]
    starts = [0.0]
    for i, ((kind, d), (n, dur)) in enumerate(zip(trans, shots[1:]), 1):
        off = t - d; starts.append(off)
        fc.append('[%s][%d:v]xfade=transition=%s:duration=%g:offset=%g[x%d]' % (prev, i, kind, d, off, i))
        prev = 'x%d' % i; t = off + dur
    total = t + 1.2
    fc.append('[%s]fade=t=in:st=0:d=2.2,fade=t=out:st=%g:d=1.0,tpad=stop_mode=add:stop_duration=1.2:color=black[v0]'
              % (prev, t - 1.0))
    # faint narration lines from the game's intro, in the lower bar while the music is still quiet
    lines = [('t1', 't1', 2.2, 5.6), ('t2', 't2', 8.4, 11.8), ('t3', 't3', 14.6, 18.0)]
    k = len(shots); last = 'v0'
    for j, (n, txt, a, b) in enumerate(lines):
        text_png(n, txt); inputs += ['-loop', '1', '-t', str(total), '-i', OUT + '/%s.png' % n]
        fc.append('[%d:v]format=rgba,fade=t=in:st=%g:d=1.0:alpha=1,fade=t=out:st=%g:d=1.0:alpha=1[o%d]' % (k + j, a, b - 1, j))
        fc.append('[%s][o%d]overlay=0:0:shortest=1[v%d]' % (last, j, j + 1)); last = 'v%d' % (j + 1)
    run(inputs + ['-filter_complex', ';'.join(fc), '-map', '[%s]' % last, '-t', str(total), '-an'] + ENC
        + [OUT + '/video.mp4'])
    print('shot starts', ['%.1f' % s for s in starts], 'total %.1f' % total)
    # music from the top of the track: its quiet opening under the first three shots, the swell (20 s) on shot d
    run(['-i', OUT + '/video.mp4', '-i', music, '-filter_complex',
         '[1:a]atrim=0:%g,afade=t=in:st=0:d=1.5,afade=t=out:st=%g:d=3.5[a]' % (total, total - 3.5),
         '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest',
         '-movflags', '+faststart', out])
    print('teaser %.1f s -> %s' % (total, out))


if __name__ == '__main__':
    main()
