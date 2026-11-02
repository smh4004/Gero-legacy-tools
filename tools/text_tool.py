"""LoG4 text tool for Buu's Fury.

  export: python3 text_tool.py export <clean.gba> <outdir>
          writes dialogue.txt (story/event lines) and ui.txt (menus, items, names)
  build:  python3 text_tool.py build <clean.gba> <textdir> <out.gba>
          re-inserts every changed line; returns the patched ROM image

Escapes inside text: {c07} = color code 0x08 0x07, {p} = page break (0x0B),
{n} = newline, {xNN} = any other control character.
Edited dialogue goes into new uncompressed text banks in expanded ROM space and
every reference site of that line is repointed; untouched lines stay as they are.
"""
import glob, json, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import unpack

BANK_TABLE = 0x7B5B64          # 7 pointers to WFZ text banks
BANK_TABLE_LITERAL = 0x123CC   # literal pool word used by both string loaders
UI_PTRS, UI_COUNT = 0x6BCE8, 1534
REFS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'refs_ok.json')
EXPAND_TO = 0x1000000
FREE_START = 0x800000


def esc(s):
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '\x08' and i + 1 < len(s):
            out.append('{c%02X}' % ord(s[i + 1])); i += 2; continue
        if ch == '\x0b': out.append('{p}')
        elif ch == '\n': out.append('{n}')
        elif ch in '{}': out.append('{x%02X}' % ord(ch))
        elif ord(ch) < 0x20: out.append('{x%02X}' % ord(ch))
        else: out.append(ch)
        i += 1
    return ''.join(out)


def unesc(s):
    def rep(m):
        t = m.group(1)
        if t == 'p': return '\x0b'
        if t == 'n': return '\n'
        if t[0] == 'c': return '\x08' + chr(int(t[1:], 16))
        if t[0] == 'x': return chr(int(t[1:], 16))
        raise ValueError('bad escape {%s}' % t)
    return re.sub(r'\{(p|n|c[0-9A-Fa-f]{2}|x[0-9A-Fa-f]{2})\}', rep, s)


def load_banks(rom):
    out = []
    for i in range(7):
        p = struct.unpack_from('<I', rom, BANK_TABLE + 4 * i)[0] - 0x08000000
        data, _ = unpack(rom, p)
        out.append(data.decode('utf-16-le'))
    return out


def u16str(rom, a):
    o = []
    while True:
        c = struct.unpack_from('<H', rom, a)[0]
        if c == 0: return ''.join(o)
        o.append(chr(c)); a += 2


def export(rom_path, outdir):
    rom = open(rom_path, 'rb').read()
    banks = load_banks(rom)
    refs = json.load(open(REFS))
    by_key = {}
    for site, sid, spk, b, o, l in refs:
        by_key.setdefault((b, o, l), []).append((site, sid, spk))
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, 'dialogue.txt'), 'w', encoding='utf-8') as f:
        f.write('# Buu\'s Fury dialogue. Edit only the text after "= ". Keep the [bank:offset:length] lines.\n')
        f.write('# Escapes: {c07} highlight color, {c02} normal color, {p} new page, {n} newline.\n\n')
        for key in sorted(by_key, key=lambda k: min(s[0] for s in by_key[k])):
            sites = by_key[key]
            b, o, l = key
            f.write('[%d:%d:%d] speaker=%02X step=%d site=%s\n' % (b, o, l, sites[0][2], sites[0][1],
                    ','.join('%X' % s[0] for s in sites)))
            f.write('= ' + esc(banks[b][o:o + l]) + '\n\n')
    with open(os.path.join(outdir, 'ui.txt'), 'w', encoding='utf-8') as f:
        f.write('# Menu, item, area and character strings. Edit only the text after "= ".\n\n')
        for i in range(UI_COUNT):
            p = struct.unpack_from('<I', rom, UI_PTRS + 4 * i)[0] - 0x08000000
            f.write('[ui:%d]\n= %s\n\n' % (i, esc(u16str(rom, p))))
    print('exported %d dialogue lines, %d UI strings' % (len(by_key), UI_COUNT))


def parse(path, speakers=None):
    """Returns {key: text}. If `speakers` is a dict, it is filled with {key: speaker id} from the header lines
    ("speaker=XX" may be edited to change who says a line; the value is hex, or decimal with a leading #)."""
    entries, key = {}, None
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if line.startswith('['):
            key = line[1:line.index(']')]
            if speakers is not None and 'speaker=' in line:
                v = line.split('speaker=')[1].split()[0]
                speakers[key] = int(v[1:]) if v.startswith('#') else int(v, 16)
        elif line.startswith('= ') and key is not None:
            entries[key] = line[2:]; key = None
        elif line == '=' and key is not None:
            entries[key] = ''; key = None
    return entries


class Builder:
    def __init__(self, rom):
        self.rom = bytearray(rom) + b'\xff' * (EXPAND_TO - len(rom))
        self.free = FREE_START

    def alloc(self, data, align=4):
        self.free = (self.free + align - 1) & ~(align - 1)
        a = self.free
        if a + len(data) > len(self.rom): raise RuntimeError('out of ROM space')
        self.rom[a:a + len(data)] = data
        self.free += len(data)
        return a

    def w32(self, a, v): struct.pack_into('<I', self.rom, a, v)


EXTRA_REFS = {}


def build(rom_path, textdir, out_path=None, extra=None):
    """extra: list of new strings (text escapes allowed) to add; their packed refs end up in EXTRA_REFS[string]."""
    clean = open(rom_path, 'rb').read()
    banks = load_banks(clean)
    refs = json.load(open(REFS))
    sites = {}
    for site, sid, spk, b, o, l in refs:
        sites.setdefault((b, o, l), []).append(site)
    B = Builder(clean)
    changed = 0
    # dialogue
    dpath = os.path.join(textdir, 'dialogue.txt')
    new_bank_texts, cur = [], []
    cur_len = 0
    repoint = []   # (sites, bank_index_in_new, offset, length)
    spk = {}
    if os.path.exists(dpath):
        entries = parse(dpath, spk)
        for key, v in spk.items():                         # speaker edits: the u8 after the step type in each event step
            b, o, l = map(int, key.split(':'))
            for s_ in sites.get((b, o, l), []):
                if clean[s_ + 2] == 5 and clean[s_ + 3] != v:
                    B.rom[s_ + 3] = v; changed += 1
        for key, txt in entries.items():
            b, o, l = map(int, key.split(':'))
            new = unesc(txt)
            if new == banks[b][o:o + l]:
                continue
            if len(new) > 2047: raise ValueError('line %s is longer than 2047 characters' % key)
            if cur_len + len(new) > 32767:
                new_bank_texts.append(''.join(cur)); cur, cur_len = [], 0
            repoint.append((sites[(b, o, l)], len(new_bank_texts), cur_len, len(new)))
            cur.append(new); cur_len += len(new); changed += 1
    extra_pos = []
    for t in (extra or []):
        new = unesc(t)
        if len(new) > 2047: raise ValueError('scene line longer than 2047 characters: %r' % t[:40])
        if cur_len + len(new) > 32767:
            new_bank_texts.append(''.join(cur)); cur, cur_len = [], 0
        extra_pos.append((t, len(new_bank_texts), cur_len, len(new)))
        cur.append(new); cur_len += len(new)
    if cur: new_bank_texts.append(''.join(cur))
    EXTRA_REFS.clear()
    for t, nb, off, ln in extra_pos:
        EXTRA_REFS[t] = (7 + nb) | (off << 6) | (ln << 21)
    if new_bank_texts:
        old_ptrs = [struct.unpack_from('<I', clean, BANK_TABLE + 4 * i)[0] for i in range(7)]
        new_ptrs = []
        for t in new_bank_texts:
            data = t.encode('utf-16-le')
            new_ptrs.append(0x08000000 + B.alloc(struct.pack('<II', 0, len(data)) + data))
        if 7 + len(new_ptrs) > 63: raise RuntimeError('too many text banks')
        table = B.alloc(b''.join(struct.pack('<I', p) for p in old_ptrs + new_ptrs + [0]))
        B.w32(BANK_TABLE_LITERAL, 0x08000000 + table)
        for ss, nb, off, ln in repoint:
            v = (7 + nb) | (off << 6) | (ln << 21)
            for s in ss:
                B.w32(s + 4, v)
    # UI strings
    upath = os.path.join(textdir, 'ui.txt')
    if os.path.exists(upath):
        ui = parse(upath)
        for extra_ui in sorted(glob.glob(os.path.join(textdir, 'ui_*.txt'))):   # e.g. ui_goals.txt (tools/goals.py)
            ui.update(parse(extra_ui))
        new_ui = {}
        for key, txt in ui.items():
            i = int(key.split(':')[1])
            if i >= UI_COUNT:                                  # beyond BF's table: added below
                new_ui[i] = unesc(txt); continue
            p = struct.unpack_from('<I', clean, UI_PTRS + 4 * i)[0] - 0x08000000
            new = unesc(txt)
            if new == u16str(clean, p):
                continue
            a = B.alloc(new.encode('utf-16-le') + b'\0\0', 2)
            B.w32(UI_PTRS + 4 * i, 0x08000000 + a)
            changed += 1
    if new_ui:
        # strings past BF's 1534: copy the pointer table (with this build's edits) and extend it, then repoint every
        # code literal that holds the table address (51 sites in BF, all exact)
        n = max(new_ui) + 1
        tab = bytearray(B.rom[UI_PTRS:UI_PTRS + 4 * UI_COUNT])
        empty = 0x08000000 + B.alloc(b'\0\0', 2)
        tab += struct.pack('<I', empty) * (n - UI_COUNT)
        for i, t in new_ui.items():
            struct.pack_into('<I', tab, 4 * i, 0x08000000 + B.alloc(t.encode('utf-16-le') + b'\0\0', 2))
        at = B.alloc(bytes(tab))
        sites = [o for o in range(0, 0x80000, 4) if struct.unpack_from('<I', clean, o)[0] == 0x08000000 + UI_PTRS]
        assert len(sites) == 51, 'UI table literal count changed: %d' % len(sites)
        for o in sites: B.w32(o, 0x08000000 + at)
        changed += len(new_ui)
    used = B.free - FREE_START
    out = bytes(B.rom)
    if out_path:
        open(out_path, 'wb').write(out)
    print('%d strings changed, %d bytes of new space used' % (changed, used))
    return out


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'export': export(sys.argv[2], sys.argv[3])
    elif cmd == 'build': build(sys.argv[2], sys.argv[3], sys.argv[4])
