"""Enemy sprite / behaviour check (2026-11-03). An enemy row's behaviour (its own, or stats.json 'ai' = another row's
id08) was written for the sprites BF pairs with that row. If LoG4 gives it a different sprite, the behaviour can ask
for animation slots the sprite leaves empty (pointer 0: the engine reads garbage), slots past the end of its slot
list, or more frames than the sprite's animation has. tools/framegrd.py keeps all of that from corrupting VRAM, but the
sprite then freezes; fix the actor instead (actors.json: copy_slots / slot_count / frames).
For every (row, sprite) the game spawns whose sprite isn't one BF uses with that behaviour, prints the slots the native
sprites fill that ours lacks, and the slots where ours has fewer frames.
usage: python3 tools/enemyslots.py <built rom> <decomp assets/tables dir> [build log with the "new actors" line]"""
import csv, json, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
KNOWN = {19: 76, 71: 184, 78: 199, 82: 202, 101: 241, 123: 255, 124: 256, 125: 257, 131: 272, 8: 34, 12: 39, 20: 78,
         100: 240, 62: 164, 76: 191, 94: 230, 15: 70, 17: 72, 36: 122, 41: 133, 44: 137, 47: 141, 48: 142, 64: 167,
         72: 187, 75: 190, 97: 235, 108: 247, 127: 259, 128: 263, 140: 291}          # = tools/areas.py's defaults


def main(rom_path, tables, log=None):
    rom = open(rom_path, 'rb').read(); B = 0x08000000
    u = lambda a: struct.unpack_from('<I', rom, a)[0]
    rows = lambda f: csv.DictReader(l for l in open(os.path.join(tables, f)) if not l.startswith('#'))
    native = {}
    for x in rows('spawns.csv'): native.setdefault(int(x['enemy']), set()).add(int(x['character']))
    by_id08 = {int(x['id08']): int(x['index']) for x in rows('enemies.csv')}
    ids = eval(re.search(r"new actors (\{.*?\})", open(log).read()).group(1)) if log else {}
    cfg = json.load(open(os.path.join(ROOT, 'log4', 'areas.json')))
    st = json.load(open(os.path.join(ROOT, 'log4', 'stats.json')))['enemies']

    def frames(ch):
        r = u(0xC00000 + 4 * (ch - 9)) - B; n = rom[r]
        return {s: u(u(r + 0x54 + 4 * s) - B) for s in range(n) if u(r + 0x54 + 4 * s)}, n
    pairs = {}
    for v in cfg['new_areas'] + cfg['areas']:
        for e in v.get('enemies', []):
            if 'actor' in e and e['actor'] not in ids: continue
            ch = ids[e['actor']] + 9 if 'actor' in e else e.get('character', KNOWN.get(e['type']))
            pairs[(e['type'], ch)] = (v['world'], v['area'])
    bad = 0
    for (row, ch), (w, a) in sorted(pairs.items()):
        ai = st.get(str(row), {}).get('ai'); src = by_id08.get(ai, row) if ai else row
        nat = native.get(src, set())
        if ch in nat: continue
        if not nat:                                   # (2026-11-04) a row BF never places: its behaviour was never
            bad += 1                                  # made for any sprite (Prototype 12 = row 30 with the Death
            print('CHECK row %3d sprite %3d (%d:%d): row %d is never placed in BF, so its behaviour has no native '
                  'sprite; give it the ai of a row that natively uses sprite %d' % (row, ch, w, a, src, ch))   # Machine:
            continue                                  # vanished for most of the fight, 178 guard rejects)
        mine, n = frames(ch); miss, short = set(), {}
        for nc in nat:
            f, _ = frames(nc)
            miss |= set(f) - set(mine)
            short.update({s: (mine[s], f[s]) for s in f if s in mine and mine[s] < f[s]})
        flag = 'OK' if not miss and not short else 'CHECK'
        bad += flag != 'OK'
        print('%-5s row %3d sprite %3d (%d:%d) behaviour of row %d: missing slots %s, fewer frames %s' %
              (flag, row, ch, w, a, src, sorted(miss), short))
    return bad


if __name__ == '__main__':
    sys.exit(1 if main(*sys.argv[1:4]) else 0)
