"""Footage for trailer v7 (2026-11-03): every clip from the --shoot ROM, recorded with the harness `rec` command.
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
    'a16':    ('cam_a16', [], 'hold', ['260 -']),
    'g66':    ('cam_g66', [], 'hold', ['260 -']),
    'g80':    ('cam_g80', [], 'hold', ['260 -']),
    'drone':  ('sh_drone_110', ['60 -'], 'fight', (450, 290, 2, 112, 230, {'RANGED': '1', 'ANYMARK': '1'})),
    'yard':   ('sh_drone_yard', ['60 -'], 'fight', (480, 377, 2, 160, 300, {'RANGED': '1'})),
    'docks':  ('t_s_lapis', ['60 -'], 'fight', (120, 500, 1, 248, 64, {'ANYMARK': '1'})),
    'pic':    ('t_bal_pic', ADV, 'fight', (1350, 348, 1, 424, 440, {'ANYMARK': '1'})),
    'kri':    ('t_bal_kri', ADV, 'fight', (700, 347, 3, 424, 440, {'ANYMARK': '1'})),
    'fly':    ('t_worldmap', ['60 -'], 'script', ['90 UP', '24 RIGHT', '50 UP', '24 LEFT', '70 UP']),
    'ninja':  ('sh_w_pilaf', ['60 -'], 'fight', (450, 500, 1, 150, 210, {'ANYMARK': '1'})),
    'sent':   ('t_bal_sent', ADV, 'fight', (2600, 401, 1, 88, 166, {'ANYMARK': '1'})),
    'outfit': ('t7_outfits', ['60 -'], 'script', ['20 -', '2 L', '10 -', '2 L', '10 -', '2 L', '20 -',
                                                  '2 B', '100 -', '2 B', '100 -', '2 B', '100 -', '2 B', '100 -',
                                                  '2 L', '20 -', '2 B', '260 -',
                                                  '2 L', '10 -', '2 L', '10 -', '2 L', '10 -', '2 L', '20 -', '2 B', '120 -']),
    'a13':    ('t_bal_13', ADV, 'fight', (700, 438, 1, 208, 312, {'ANYMARK': '1'})),
    'kame':   ('t7_kame', ['60 -'], 'script', ['180 -', '90 LEFT', '20 -']),
    'paozu':  ('t7_paozu', ['60 -'], 'script', ['180 -', '90 DOWN', '20 -']),
    'hub':    ('t7_hub', ['60 -'], 'script', ['180 -', '90 DOWN', '20 -']),
    'ruins':  ('t7_ruins', ['60 -'], 'script', ['180 -', '90 UP', '20 -']),
    'fs26':   ('cam_t7_fs26', [], 'hold', ['300 -']),
    'fs25':   ('cam_t7_fs25', [], 'hold', ['330 -']),
}


CALM = {'outfit'}                                  # recorded with the area's enemies removed


def harness(d, lines):
    p = os.path.join(d, '_t7.txt'); open(p, 'w').write('\n'.join(lines) + '\n')
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
