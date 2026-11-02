"""Teaser v3 for Gero's Legacy (~50 s): ominous and vague, Act 1 lab -> Act 2 West City -> night -> the lab -> 17 & 18
art -> logo. Letterboxed, darkened emulator footage (240x128 strip, HUD cropped, 7x nearest), dissolves / dips to
black, no title cards; five faint lines in the lower bar, rendered in the game's own dialogue font (tools/gamefont.py,
atlas tools/gamefont_atlas.npz lifted from footage). Music: LoG2 "Era of Darkness" from the top (its swell at 20 s
lands on the man in the long coat).
Footage: scratchpad recordings made with tools/harness `rec` from a test ROM (see HANDOFF "Teaser").
usage: python3 tools/teaser.py <music.mp3> <out.mp4> <footage dir> [intro clip dir]"""
import os, subprocess, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gamefont

FOOT = sys.argv[3] if len(sys.argv) > 3 else '.'
TZ = sys.argv[4] if len(sys.argv) > 4 else FOOT
OUT = os.path.join(FOOT, 'build3')
os.makedirs(OUT, exist_ok=True)
W, H, FPS = 1920, 1080, 60
S = 7                                   # 240x128 strip (rows 24-151: HUD cropped off) at 7x = 1680x896
GW, GH = 240 * S, 128 * S
GX, GY = (W - GW) // 2, (H - GH) // 2
HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, '..', 'log4', 'art', 'raw', 'U1_title.png')
ENC = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-r', str(FPS)]
GRADE = 'eq=saturation=0.72:gamma=0.86:contrast=1.06'
TS = 4                                  # text scale (game pixels -> video pixels)


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


def text_png(name, line):
    chars = gamefont.load(os.path.join(HERE, 'gamefont_atlas.npz'))
    big = np.kron(gamefont.render(chars, line), np.ones((TS, TS), bool))
    img = np.zeros((H, W, 4), np.uint8)
    y = GY + GH + (GY - 11 * TS) // 2; x = (W - big.shape[1]) // 2
    img[y:y + big.shape[0], x:x + big.shape[1]][big] = (212, 206, 200, 215)
    Image.fromarray(img, 'RGBA').save(OUT + '/%s.png' % name)


def main():
    music, out = sys.argv[1], sys.argv[2]
    F = lambda n: os.path.join(FOOT, n)
    shots = [
        seg('a', F('main.mkv'), 0.4, 4.6),            # Act 1: Gero crosses the main lab, past Gevo and a hovering drone
        seg('b', F('lab.mkv'), 0.2, 3.0),             # the lab door slides open and he steps through
        seg('c', F('lab.mkv'), 3.4, 7.4),             # the tank room, Gero crosses to the pod
        seg('d', F('s1.mkv'), 27.5, 7.5),             # years later: West City by day, the twins walk the street
        seg('e', F('watch.mkv'), 2.2, 6.7),           # the park after the chase: the man in the long coat stands watching
        seg('f', F('s5.mkv'), 0.1, 10.0),             # night: moonlit streets, drones hanging over the road
        seg('g', F('s5.mkv'), 11.9, 3.5),             # the drones close in
        seg('h', F('lab2.mkv'), 4.3, 3.5),            # the lab afterwards: the twins, Gero, the pod
        art_seg('i', ART, 6.0),                       # 17 & 18: full-resolution title art, slow push-in
        seg('j', os.path.join(TZ, 'intro.mkv'), 34.45, 4.4, crop_y=16, grade='null'),   # GERO'S LEGACY
    ]
    trans = [('dissolve', 0.8), ('dissolve', 0.8), ('fadeblack', 1.2), ('dissolve', 1.0), ('fadeblack', 1.0),
             ('dissolve', 0.6), ('fadeblack', 0.8), ('fadeblack', 1.0), ('fadeblack', 1.0)]
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
    # five faint lines in the lower bar, each inside its shot
    sh = dict(zip('abcdefghij', starts))
    lines = [('A soldier that never tires...', sh['a'] + 0.8, sh['c'] + 3.0),
             ('Years later.', sh['d'] + 1.0, sh['d'] + 5.2),
             ('Somebody else was watching.', sh['e'] + 2.2, sh['e'] + 6.4),
             ('Subjects located.', sh['g'] + 0.2, sh['h'] + 0.4),
             ('Your old names end tonight.', sh['h'] + 0.6, sh['i'] + 2.2)]
    k = len(shots); last = 'v0'
    for j, (txt, a, b) in enumerate(lines):
        n = 't%d' % j; text_png(n, txt); inputs += ['-loop', '1', '-t', str(total), '-i', OUT + '/%s.png' % n]
        fc.append('[%d:v]format=rgba,fade=t=in:st=%g:d=0.9:alpha=1,fade=t=out:st=%g:d=0.9:alpha=1[o%d]' % (k + j, a, b - 0.9, j))
        fc.append('[%s][o%d]overlay=0:0:shortest=1[v%d]' % (last, j, j + 1)); last = 'v%d' % (j + 1)
    run(inputs + ['-filter_complex', ';'.join(fc), '-map', '[%s]' % last, '-t', str(total), '-an'] + ENC
        + [OUT + '/video.mp4'])
    print('shot starts', ['%.1f' % s for s in starts], 'total %.1f' % total)
    run(['-i', OUT + '/video.mp4', '-i', music, '-filter_complex',
         '[1:a]atrim=0:%g,afade=t=in:st=0:d=1.5,afade=t=out:st=%g:d=3.5[a]' % (total, total - 3.5),
         '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest',
         '-movflags', '+faststart', out])
    print('teaser %.1f s -> %s' % (total, out))


if __name__ == '__main__':
    main()
