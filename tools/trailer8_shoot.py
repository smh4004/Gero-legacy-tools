"""Footage for trailer v8 (2026-11-03, same method as v7; the length passes' new places): every clip from the --shoot ROM, recorded with the harness `rec` command.
Fights are played by tools/fightbot.py (it walks straight at the enemy and only attacks in reach), then its key log is
replayed from the same start state while recording, so nobody swings at the air or walks away from a fight. Other clips
are short scripted walks / camera holds.
usage: python3 tools/trailer7_shoot.py <shoot rom> <named_lists_shoot.json> <outdir> [clip ...]"""
import os, subprocess, sys, struct
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(HERE, 'harness')
ROM, NAMED, OUT = sys.argv[1:4]
ADV = ['4 A', '25 -'] * 6                                   # level-up pages after a t_bal_* list

# name: (list, prep lines, kind, args)
#   fight: (boss hp, stop flag, character, arrival x, y, env)    hold/script: harness key lines (recorded)
CLIPS = {
    'quarters': ('cam_t8_quarters', [], 'hold', ['300 -']),
    'qm':       ('t_bal_qm', ['200 -'], 'fight', (380, 451, 2, 140, 224, {'RANGED': '1', 'ANYMARK': '1'})),
    'p3':       ('t_bal_p3', ['200 -'], 'fight', (800, 456, 2, 150, 200, {'RANGED': '1', 'ANYMARK': '1'})),
    'night':    ('t8_night', ['200 -'], 'script', ['30 -', '100 RIGHT', '30 UP', '100 RIGHT', '40 -']),
    'warden':   ('t_bal_warden', ADV + ['150 -'], 'fight', (1900, 482, 1, 120, 160, {'ANYMARK': '1'})),
    'wave':     ('t8_wave', ['200 -'], 'script', ['30 -', '4 L', '12 -', '8 RIGHT', '6 -'] + ['2 B', '14 -'] * 6 +
                 ['4 L', '12 -', '80 B', '110 -']),
    'store':    ('t8_store', ['200 -'], 'script', ['20 -', '70 LEFT', '150 UP', '60 RIGHT', '40 -']),
    'sentry':   ('t_bal_sentry', ADV + ['150 -'], 'fight', (2400, 537, 1, 108, 76, {'ANYMARK': '1'})),
    'outfit8':  ('t7_outfits', ['60 -'], 'script', ['20 -', '2 L', '10 -', '2 L', '10 -', '2 L', '20 -',
                                                    '2 B', '100 -', '2 B', '100 -', '2 B', '100 -', '2 B', '100 -',
                                                    '2 L', '20 -', '2 B', '320 -']),
    'rcapt':    ('t_bal_rcapt', ADV + ['150 -'], 'fight', (1800, 492, 1, 140, 224, {'ANYMARK': '1'})),
    'archive':  ('t8_archive', ['200 -'], 'script', ['20 -', '120 UP', '20 -']),
    'district': ('t8_district', ['200 -'], 'script', ['20 -', '140 RIGHT', '20 -']),
    'bio':      ('t_bal_warden', ['4 A', '25 -'] * 16 + ['150 -'], 'script', ['20 -', '130 RIGHT', '20 -']),   # (the rooftop walk was blocked)
}


CALM = {'outfit8', 'night', 'store', 'archive', 'district', 'bio'}   # recorded with the area's enemies removed
# (prep waits of 150-200 frames: the area-name banner is gone before recording starts)


def harness(d, lines):
    p = os.path.join(d, '_t8.txt'); open(p, 'w').write('\n'.join(lines) + '\n')
    subprocess.run([H, os.path.join(d, 'lt.gba'), p, d], capture_output=True)


def go(name):
    lst, prep, kind, arg = CLIPS[name]
    d = os.path.join(OUT, name); os.makedirs(d, exist_ok=True)
    env = dict(os.environ, NAMED=NAMED, SHOTS='0', TAIL='20 -', NOENEMIES='1' if name in CALM else '0')
    subprocess.run(['python3', os.path.join(HERE, 'listtest.py'), ROM, d, 's', '1:1:112:200', lst], env=env, capture_output=True)
    if kind != 'fight' or prep is not ADV and not prep[0].startswith('4 A'):
        harness(d, ['1 -', 'load s_end'] + prep + ['save start'])
    if kind == 'fight':
        hp, flag, ch, ax, ay, fenv = arg
        if prep[:2] == ['4 A', '25 -']:             # level-up pages: stop pressing A once the boss is there at full HP
            extra = prep[len(ADV):]
            for n in (2, 3, 4, 6, 8, 10, 12, 16):
                harness(d, ['1 -', 'load s_end'] + ['4 A', '25 -'] * n + ['20 -', 'dump _e 2000000 40000'])
                b = open(os.path.join(d, '_e.bin'), 'rb').read()
                if any(struct.unpack_from('<I', b, i)[0] == hp << 10 for i in range(0, len(b) - 4, 4)):
                    harness(d, ['1 -', 'load s_end'] + ['4 A', '25 -'] * n + ['20 -'] + extra + ['save start']); break
        r = subprocess.run(['python3', os.path.join(HERE, 'fightbot.py'), os.path.join(d, 'lt.gba'), d, 'start', str(hp),
                            str(flag), str(ch), '45', str(ax), str(ay)], env=dict(os.environ, **fenv), capture_output=True, text=True)
        keys = [k for k in open(os.path.join(d, 'keys.txt')).read().split('\n') if k.strip()] if os.path.exists(os.path.join(d, 'keys.txt')) else []
        lines = keys + ['60 -']                         # exactly the bot's inputs from the same state: same fight
        res = (r.stdout + r.stderr).strip().split('\n')[-1]
    else:
        lines = arg; res = 'scripted'
    rec = []
    for l in lines:
        n, k = l.split(); rec.append('rec %s %s %s' % (name, n, k))
    harness(d, ['1 -', 'load start'] + rec)
    ok = os.path.exists(os.path.join(d, name + '.mkv'))
    return name, ok, res


if __name__ == '__main__':
    names = sys.argv[4:] or list(CLIPS)
    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(go, names): print(r, flush=True)
