"""Batch art intake: python3 intake.py <file-or-zip> [...]

Copies images (and images inside zips) into log4/art/raw/, matches each to a prompt ID from its file name
(P1..P12, R1..R6, E1..E7, U1..U14 prefixes, e.g. "P1_android17_dash.png" or "p1 dash v2.webp"), creates or updates
its spec with defaults for that prompt, runs the cleanup step on just those assets, and writes one review sheet
(log4/art/clean/review_<time>.png) showing raw input next to the cleaned frames.
Unmatched files are listed so they can be named.
"""
import json, os, re, sys, time, zipfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artclean
from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'log4', 'art')
RAW, CLEAN, SPECS = os.path.join(ROOT, 'raw'), os.path.join(ROOT, 'clean'), os.path.join(ROOT, 'specs.json')
IMG = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif')

# defaults per prompt (from the art doc + measured in-game heights)
SPRITE = dict(kind='sprite', cell=[32, 32], max_colors=16)   # characters: every frame must fit ONE 32x32 OBJ (engine limit)
DEFAULTS = {
    'P1': dict(SPRITE, target_height=31, allow_new_colors=1), 'P2': dict(SPRITE, target_height=31, allow_new_colors=1),
    'P3': dict(SPRITE, target_height=31, allow_new_colors=2), 'P4': dict(SPRITE, target_height=31, allow_new_colors=2),
    'P5': dict(SPRITE, target_height=32, allow_new_colors=1), 'P6': dict(SPRITE, cell=[32, 32], target_height=32, allow_new_colors=1),  # 1 KB OBJ VRAM per character frame
    'P7': dict(SPRITE, target_height=31), 'P8': dict(SPRITE, target_height=30), 'P9': dict(SPRITE, target_height=31),
    'P10': dict(SPRITE, cell=[64, 64], target_height=53), 'P11': dict(SPRITE, cell=[16, 16], target_height=12),
    'P12': dict(SPRITE, target_height=32),
    'P13': dict(SPRITE, target_height=27, allow_new_colors=1),   # kid Goku (Goten-sized); pole_extend needs a wide cell (set per file)
    'E1': dict(SPRITE, cell=[64, 64]), 'E2': dict(SPRITE, cell=[64, 32]), 'E3': dict(SPRITE, cell=[64, 64]),
    'E4': dict(SPRITE, cell=[32, 16]), 'E5': dict(SPRITE, cell=[64, 32]), 'E6': dict(SPRITE, cell=[32, 32]),
    'E7': dict(SPRITE, cell=[64, 64]),
    'E8': dict(SPRITE, cell=[16, 16]), 'E9': dict(SPRITE, cell=[32, 16]),
}
PORTRAIT = dict(kind='portrait', cell=[56, 56], target_height=56, max_colors=32, allow_new_colors=1)  # BF window 56x56 inside the 64x64 frame
UI = dict(kind='ui', size=[240, 160], max_colors=240)


def prompt_id(name):
    m = re.match(r'\s*([PpRrEeUu])\s*[-_ ]?(\d{1,2})(?!\d)', name)
    return (m.group(1).upper() + str(int(m.group(2)))) if m else None


def defaults_for(pid):
    if pid in DEFAULTS: return dict(DEFAULTS[pid])
    if pid.startswith('R'): return dict(PORTRAIT)
    if pid.startswith('U'): return dict(UI)
    return None


def gather(paths):
    out = []
    for p in paths:
        if p.lower().endswith('.zip'):
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if n.lower().endswith(IMG) and not n.startswith('__MACOSX'):
                        dst = os.path.join(RAW, os.path.basename(n))
                        with z.open(n) as src, open(dst, 'wb') as f: shutil.copyfileobj(src, f)
                        out.append(dst)
        elif p.lower().endswith(IMG):
            dst = os.path.join(RAW, os.path.basename(p))
            if os.path.abspath(p) != os.path.abspath(dst): shutil.copy(p, dst)
            out.append(dst)
    return out


def main(paths):
    os.makedirs(RAW, exist_ok=True); os.makedirs(CLEAN, exist_ok=True)
    specs = json.load(open(SPECS)) if os.path.exists(SPECS) else []
    by_file = {s['file']: s for s in specs}
    files = gather(paths)
    todo, unmatched = [], []
    for f in files:
        fn = os.path.basename(f)
        if fn.lower().endswith(('.jpg', '.jpeg', '.webp', '.bmp', '.gif')):        # normalise to PNG
            png = os.path.splitext(f)[0] + '.png'
            Image.open(f).convert('RGBA').save(png); os.remove(f); fn = os.path.basename(png)
        if fn in by_file:
            todo.append(by_file[fn]); continue
        pid = prompt_id(fn)
        d = defaults_for(pid) if pid else None
        if not d:
            unmatched.append(fn); continue
        sid = re.sub(r'[^A-Za-z0-9_]+', '_', os.path.splitext(fn)[0]).strip('_')
        spec = dict(d, id=sid, file=fn)
        specs.append(spec); by_file[fn] = spec; todo.append(spec)
    json.dump(specs, open(SPECS, 'w'), indent=1)
    tmp = os.path.join(CLEAN, '_batch_specs.json'); json.dump(todo, open(tmp, 'w'), indent=1)
    reps = artclean.main(tmp, RAW, CLEAN) if todo else []
    os.remove(tmp)
    # merge into the cumulative report
    allp = os.path.join(CLEAN, 'report_all.json')
    allr = {r['id']: r for r in (json.load(open(allp)) if os.path.exists(allp) else [])}
    for r in reps: allr[r['id']] = r
    json.dump(list(allr.values()), open(allp, 'w'), indent=1)
    sheet = review_sheet(todo, reps) if todo else None
    print('\nprocessed %d, unmatched %d' % (len(todo), len(unmatched)))
    for u in unmatched: print('  needs a prompt ID in its name:', u)
    if sheet: print('review sheet:', sheet)
    return reps, unmatched, sheet


def review_sheet(todo, reps):
    rows = []
    for s, r in zip(todo, reps):
        prev = os.path.join(CLEAN, s['id'] + '_preview.png')
        raw = os.path.join(RAW, s['file'])
        if not os.path.exists(prev): continue
        a = Image.open(raw).convert('RGB'); a.thumbnail((360, 160))
        b = Image.open(prev).convert('RGB')
        if b.height > 160: b.thumbnail((900, 160))
        rows.append((s['id'], r, a, b))
    if not rows: return None
    W = max(370 + b.width for _, _, a, b in rows) + 10
    H = sum(max(a.height, b.height) + 30 for _, _, a, b in rows)
    img = Image.new('RGB', (min(W, 1600), H), (28, 30, 36)); d = ImageDraw.Draw(img); y = 0
    for sid, r, a, b in rows:
        w = r.get('warnings') or []
        d.text((6, y + 4), '%s   mode: %s   colours: %s   %s' % (sid, r.get('mode', '-'), r.get('colors', '-'),
               ('WARN: ' + '; '.join(w))[:150] if w else 'ok'), fill=(255, 200, 120) if w else (170, 230, 170))
        img.paste(a, (6, y + 22)); img.paste(b, (376, y + 22)); y += max(a.height, b.height) + 30
    path = os.path.join(CLEAN, 'review_%s.png' % time.strftime('%Y%m%d_%H%M%S'))
    img.save(path); return path


if __name__ == '__main__':
    main(sys.argv[1:])
