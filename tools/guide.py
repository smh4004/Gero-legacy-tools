"""Walkthrough + 100% guide generator (user 2026-11-02: "a comprehensive walkthrough guide and 100% guide ... always
update along with any new additions or removals so it fully reflects all of the game to 100% accuracy").

Facts come from the BUILT ROM (log4/out/LoG4.gba + named_lists.json) and the sources, never from memory:
  - every area's name, exits (and where they lead), examine spots, walk-in events, NPCs and enemies are read from the
    ROM's own area tables, so the atlas is exactly what the game contains;
  - items, flags and objectives come from the compiled scene lists (log4/scenes/*.scene);
  - boss stats come from the enemy table in the ROM.
The hand-written walkthrough (log4/guide/walkthrough.md) uses tags that are filled in from that data:
  {{A:w:a}} area name   {{I:n}} item name   {{B:row}} enemy name + stats   {{L:list}} where a list is triggered
  {{C:list}} a cache/collectible: where + what it gives   {{J:list}} the objective text a list writes to the journal
  {{X:list}} mark a list as covered without printing anything
Lint (exit code 1 = the guide is out of date): a tag naming something that no longer exists, or game content the
walkthrough doesn't cover: every list that gives items, every list in MUST_COVER, every enemy row with 1000+ HP.
usage: python3 tools/guide.py [--check]      writes GUIDE.md (repo root)"""
import json, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..'); L4 = os.path.join(ROOT, 'log4')
sys.path.insert(0, HERE)
import clipcheck as C, scenes, text_tool
from areas import EXAMINE

BASE = 0x08000000
u32 = lambda b, o: struct.unpack_from('<I', b, o)[0]
FACE = {v: k for k, v in EXAMINE.items()}
# content a 100% player must be told about (missables, side jobs, optional fights, the secret chapter's conditions)
MUST_COVER = ['ch8_stall', 'ch8_hideout', 'ch8_civilians', 'ch9_paozu', 'ch9_kame', 'wc_cop_chase', 'park_hide',
              'wc_man_green', 'wc_hercule', 'osc_hercule', 'papaya_announcer', 'diablo_ball', 'pilaf_safe', 'nat_elder',
              'paozu_ball', 'kame_ball', 'lookout_door']


def load():
    rom = open(os.path.join(L4, 'out', 'LoG4.gba'), 'rb').read()
    named = json.load(open(os.path.join(L4, 'out', 'named_lists.json')))
    ui = text_tool.parse(os.path.join(L4, 'text', 'ui.txt'))
    ui.update(text_tool.parse(os.path.join(L4, 'text', 'ui_goals.txt')) if os.path.exists(os.path.join(L4, 'text', 'ui_goals.txt')) else {})
    cfg = json.load(open(os.path.join(L4, 'areas.json')))
    return rom, named, ui, cfg


def clean(s):
    return re.sub(r'\{c0\d\}', '', s).replace('{p}', ' ').replace('{n}', ' ')


def scene_lists():
    """name -> {'items': [(item, n)], 'journal': [text], 'sets': {flags}, 'runs': [names], 'warps': [(w, a)], 'lines': n}"""
    out = {}
    for f in sorted(os.listdir(os.path.join(L4, 'scenes'))):
        if not f.endswith('.scene'): continue
        cur = None
        for ln in open(os.path.join(L4, 'scenes', f), encoding='utf-8'):
            t = ln.strip()
            if t.startswith('list '):
                cur = out.setdefault(t[5:].strip(), dict(items=[], journal=[], sets=set(), runs=[], warps=[], file=f))
                continue
            if cur is None: continue
            for m in re.finditer(r'call 129 (\d+) (\d+)', t): cur['items'].append((int(m.group(1)), int(m.group(2))))
            for m in re.finditer(r'call 119 (\d+) (\d+)', t): cur['warps'].append((int(m.group(1)), int(m.group(2))))
            if t.startswith('journal '): cur['journal'].append(clean(t[8:]))
            if t.startswith('set_flag '): cur['sets'].add(int(t.split()[1]))
            if t.startswith('run '): cur['runs'].append(t[4:].strip())
    return out


def cond_text(rom, prm):
    """Exit condition -> 'flag N set' / 'flag N clear' text (simple push/call 27-28/and chains only)."""
    if prm == 0: return ''
    if not (BASE <= prm < BASE + len(rom)): return 'conditional'
    b = rom[prm - BASE:prm - BASE + 64]; i = 0; parts = []
    try:
        while b[i] != 0x11:
            if b[i] == 0x00: v = b[i + 1]; i += 2
            elif b[i] == 0x01: v, i = scenes.varint(b, i + 1)
            else: return 'conditional'
            if b[i] != 0x02 or b[i + 1] not in (27, 28): return 'conditional'
            parts.append('flag %d %s' % (v, 'set' if b[i + 1] == 27 else 'clear')); i += 2
            if b[i] == 0x04: i += 1
    except IndexError: return 'conditional'
    return ' and '.join(parts)


def scan(rom, cfg, named, ui):
    """Every area LoG4 defines: name, exits, NPCs, enemies - read from the ROM."""
    R = C.Rom(rom); byptr = {v: k for k, v in named.items()}
    NAMES = json.load(open(os.path.join(L4, 'guide', 'area_names.json')))
    stubs = {}
    def getter_kind(g):
        if g == 0x0800774F: return 'examine (face up)'
        if g == 0x080077DF: return 'walk in'
        if g == 0x080071A7: return 'hold Up'
        if g == 0x0800770D: return 'press A'
        o = g - 1 - BASE
        if 0 <= o < len(rom) - 8 and u32(rom, o) == 0x47704800:
            return 'examine (face %s)' % FACE.get(u32(rom, o + 4), '?')
        return 'event'
    areas = {}
    keys = sorted({(a['world'], a['area']) for a in cfg['new_areas'] + cfg.get('areas', [])})
    for (w, a) in keys:
        e = R.entry(w, a)
        nm = clean(ui.get('ui:%d' % struct.unpack_from('<H', rom, e + 0xC)[0], '?'))
        key = '%d:%d' % (w, a); sub = NAMES.get(key)
        if sub is None:
            note = next((x.get('_note') or '' for x in cfg['new_areas'] + cfg.get('areas', []) if (x['world'], x['area']) == (w, a)), '')
            m = re.match(r'.*?: (.+?) \(generated', note); sub = m.group(1) if m else None
        if sub and sub != nm: nm = sub if sub.startswith(nm) else '%s: %s' % (nm, sub)
        A = dict(name=nm, exits=[], events=[], npcs=[], enemies=[])
        ne, xp = rom[e + 3], u32(rom, e + 0x10)
        for i in range(ne if xp else 0):
            prm, obj = struct.unpack_from('<II', rom, xp - BASE + 8 * i)
            o = obj - BASE; fn = u32(rom, o); rect = struct.unpack_from('<4H', rom, o + 8)
            if fn == 0x08007675:
                dest = u32(rom, o + 16)
                if rect[2] > rect[0]:
                    A['exits'].append(dict(to=((dest >> 8) & 0xFF, (dest >> 16) & 0xFF), dir='down up left right'.split()[dest & 3],
                                           rect=rect, when=cond_text(rom, prm)))
            elif fn == 0x0800742D and u32(rom, o + 16) in byptr:
                A['events'].append(dict(list=byptr[u32(rom, o + 16)], kind=getter_kind(u32(rom, o + 4)), rect=rect,
                                        when=cond_text(rom, prm)))
        n, lp = rom[e + 4], u32(rom, e + 0x14)
        for k in range(n if lp else 0):
            o = u32(rom, lp - BASE + 4 * k) - BASE
            fn = u32(rom, o)
            if fn == 0x08017DA3 and u32(rom, o + 12) in byptr:
                pos = u32(rom, o + 8); A['npcs'].append(dict(list=byptr[u32(rom, o + 12)], pos=(pos & 0xFFFF, pos >> 16)))
            elif fn == 0x0800FD55:
                typ = u32(rom, o + 8); pos = u32(rom, o + 12)
                A['enemies'].append(dict(row=typ, pos=(pos & 0xFFFF, pos >> 16), when=cond_text(rom, u32(rom, o + 4))))
        areas[(w, a)] = A
    return areas


def enemy(rom, row, stats):
    o = 0x711274 + 28 * row
    exp, hp = struct.unpack_from('<ii', rom, o); lv, st, pw, en = rom[o + 12:o + 16]
    nm = stats.get(str(row), {}).get('name', 'enemy row %d' % row)
    nm = re.split(r' \(', nm)[0]
    return dict(name=nm, hp=hp, lv=lv, str=st, pow=pw, end=en, exp=exp)


def main():
    rom, named, ui, cfg = load()
    stats = json.load(open(os.path.join(L4, 'stats.json')))['enemies']
    lists = scene_lists(); areas = scan(rom, cfg, named, ui)
    item = lambda n: clean(ui.get('ui:%d' % (694 + 4 * n), 'item %d' % n))
    where = {}                                         # list -> [(area key, how)]
    for k, A in areas.items():
        for ev in A['events']: where.setdefault(ev['list'], []).append((k, ev['kind'], ev['when']))
        for np_ in A['npcs']: where.setdefault(np_['list'], []).append((k, 'talk', ''))
    aname = lambda k: areas[k]['name'] if k in areas else '%d:%d' % k
    covered, errors = set(), []
    def loc(name):
        ws = where.get(name)
        if not ws: return None
        short = lambda k: aname(k).split(': ', 1)[-1]               # the room's own name (the atlas has the full one)
        return ', '.join(sorted({'**%s**' % short(k) + ('' if how == 'talk' else ' (%s)' % how.split(' (')[0]) for k, how, _ in ws}))
    def gives(name):
        its = lists.get(name, {}).get('items', [])
        return ', '.join('%s x%d' % (item(i), n) for i, n in its)
    def tag(m):
        kind, arg = m.group(1), m.group(2)
        if kind == 'A':
            w, a = map(int, arg.split(':'))
            if (w, a) not in areas: errors.append('unknown area %s' % arg); return arg
            return '**%s**' % aname((w, a))
        if kind == 'I': return item(int(arg))
        if kind == 'B':
            e = enemy(rom, int(arg), stats); return '%s (HP %d, level %d)' % (e['name'], e['hp'], e['lv'])
        if arg not in lists: errors.append('unknown list %s' % arg); return arg
        covered.add(arg)
        if kind == 'X': return ''
        if kind == 'J': return '"%s"' % '; '.join(lists[arg]['journal'])
        l = loc(arg)
        if l is None and kind in ('L', 'C'): errors.append('list %s is not triggered anywhere in the game' % arg); return arg
        if kind == 'L': return l
        if kind == 'C': return '%s: %s' % (l, gives(arg) or 'nothing')
    src = open(os.path.join(L4, 'guide', 'walkthrough.md'), encoding='utf-8').read()
    body = re.sub(r'\{\{([ALCJIBX]):([^}]+)\}\}', tag, src)
    body = re.sub(r' ?\(\)', '', body).replace(' :', ':')       # what an X tag (prints nothing) leaves behind

    # ---------- generated sections
    out = [body.rstrip(), '', '---', '', '# 100% checklist (generated from the game data)', '']
    out += ['Every container, gift and reward that gives items. Each one works once.', '',
            '| Where | How | Gives |', '|---|---|---|']
    giving = sorted(n for n in lists if lists[n]['items'] and n in where)
    for n in giving:
        for k, how, when in where[n]:
            out.append('| %s | %s | %s |' % (aname(k), how, gives(n)))
    # the secret chapter's conditions, read from the epilogue list itself (unless_flag lines before 'run fs_start')
    fin = open(os.path.join(L4, 'scenes', lists['ch10_finale']['file']), encoding='utf-8').read() if 'ch10_finale' in lists else ''
    need = [int(f) for f in re.findall(r'unless_flag (\d+) epi_end', fin)]
    if need:
        out += ['', '## Secret chapter conditions (read from the epilogue script)', '', '| Flag | Set by | Where |', '|---|---|---|']
        for f in need:
            setters = [n for n in lists if f in lists[n]['sets']]
            for n in setters: out.append('| %d | `%s` | %s |' % (f, n, loc(n) or 'story'))
            if not setters: errors.append('secret-chapter flag %d is never set' % f)
    out += ['', '# Bosses and strong enemies (generated)', '',
            '| Enemy | Where | HP | Level | STR | POW | END | EXP |', '|---|---|---|---|---|---|---|---|']
    seen = set()
    for k, A in sorted(areas.items()):
        for en in A['enemies']:
            e = enemy(rom, en['row'], stats)
            if e['hp'] < 400 or (e['name'], k) in seen: continue
            seen.add((e['name'], k))
            out.append('| %s | %s | %d | %d | %d | %d | %d | %d |' % (e['name'], aname(k), e['hp'], e['lv'], e['str'],
                                                                     e['pow'], e['end'], e['exp']))
            if e['hp'] >= 1000 and not any(en['row'] == int(b) for b in re.findall(r'\{\{B:(\d+)\}\}', src)):
                errors.append('boss row %d (%s) is not in the walkthrough' % (en['row'], e['name']))
    out += ['', '# Area atlas (generated from the ROM)', '',
            'Every area of Gero\'s Legacy: its exits, things to examine, people and enemies. "examine" = press A while facing '
            'that way inside the spot; "walk in" = triggers when you step there.', '']
    def exit_line(x):
        return '%s exit -> %s%s' % (x['dir'].capitalize() if x['dir'] in ('up', 'down') else x['dir'].capitalize(),
                                   aname(x['to']), (' (only when %s)' % x['when']) if x['when'] else '')
    for k, A in sorted(areas.items()):
        if not (A['exits'] or A['events'] or A['npcs'] or A['enemies']): continue
        out.append('### %s  `%d:%d`' % (A['name'], k[0], k[1]))
        for x in A['exits']: out.append('- ' + exit_line(x))
        for ev in A['events']:
            out.append('- %s: `%s`%s%s' % (ev['kind'], ev['list'], (' - gives ' + gives(ev['list'])) if gives(ev['list']) else '',
                                           (' (when %s)' % ev['when']) if ev['when'] else ''))
        for np_ in A['npcs']: out.append('- person: `%s`%s' % (np_['list'], (' - gives ' + gives(np_['list'])) if gives(np_['list']) else ''))
        if A['enemies']:
            cnt = {}
            for en in A['enemies']:
                nm = enemy(rom, en['row'], stats)['name']; cnt[nm] = cnt.get(nm, 0) + 1
            out.append('- enemies: ' + ', '.join('%s x%d' % kv if kv[1] > 1 else kv[0] for kv in cnt.items()))
        out.append('')
    out += ['# Items (generated)', '', '| Item | Effect (in-game description) |', '|---|---|']
    used = sorted({i for n in lists for i, _ in lists[n]['items']})
    for i in used:
        out.append('| %s | %s |' % (item(i), clean(ui.get('ui:%d' % (694 + 4 * i + 3), ''))))
    # ---------- lint
    for n in giving + [m for m in MUST_COVER if m in lists]:
        if n not in covered: errors.append('walkthrough does not cover %s (%s)' % (n, loc(n) or 'not placed'))
    for m in MUST_COVER:
        if m not in lists: errors.append('MUST_COVER list %s no longer exists' % m)
    text = '\n'.join(out) + '\n'
    if '--check' not in sys.argv: open(os.path.join(ROOT, 'GUIDE.md'), 'w', encoding='utf-8').write(text)
    for e_ in sorted(set(errors)): print('GUIDE:', e_)
    print('GUIDE.md: %d lines, %d areas, %d item sources; %s' % (text.count('\n'), len(areas), len(giving),
                                                                  'UP TO DATE' if not errors else '%d problem(s)' % len(set(errors))))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
