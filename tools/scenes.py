"""LoG4 scene compiler (v1): write a cutscene / event as text, get a Buu's Fury step list.

Events are lists of u32 pointers to steps (0-terminated). A step is [u16 id][u8 type][payload]:
  type 0 = script bytecode up to END (0x11)      type 5 = dialogue [u8 speaker][u32 text ref]
  type 7 = run another list [pad][u32 ptr]     type 4 = (unknown payload, kept as raw bytes)
Step ids are numbered 1.. in list order (the original lists do the same).

Scene file (log4/scenes/*.scene):
    replace 0x780550            step list to replace (every pointer to it is repointed to the new list)
    keep 1                      copy an original step of that list by id (renumbered)
    keep 5-7                    a range
    say gevo.0 Text...          dialogue; speaker = alias, hex (B7) or #decimal
    narrate Text...             speaker 00
    journal Text...             "Journal Entry: Text"
    code 02 15 00 02 02 53      raw bytecode step (END added)
Speaker aliases come from log4/art/speakers.json (gevo.0..3, young_gero.0..3, android17, cell_perfect, ...),
plus goku/party = 02, narrator = 00, and any BF speaker by hex.
"""
import os, re, struct

BASE = 0x08000000


def aliases(speakers_json):
    import json
    al = {'narrator': 0, 'goku': 2, 'party': 2}
    if os.path.exists(speakers_json):
        for k, v in json.load(open(speakers_json)).items():
            if k.startswith('L2_'): al[k[3:]] = v
            else:
                m = re.match(r'R\d+b?_(.+?)_portrait_(\d+)$', k)
                if m: al['%s.%d' % (m.group(1), int(m.group(2)))] = v
    return al


def parse(path):
    sc = {'file': path, 'steps': [], 'replace': None, 'name': None}
    for ln in open(path, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if not ln.strip() or ln.lstrip().startswith('#'): continue
        cmd, _, rest = ln.strip().partition(' ')
        if cmd == 'replace': sc['replace'] = int(rest, 0)
        elif cmd == 'name': sc['name'] = rest.strip()          # a new list (e.g. an NPC talk script), no replace
        elif cmd == 'list':                                   # several named lists in one file: "list <name>" starts one
            sc.setdefault('lists', []).append((rest.strip(), len(sc['steps'])))
        elif cmd == 'keep':
            a, _, b = rest.partition('-'); a = int(a); b = int(b) if b else a
            sc['steps'] += [('keep', i) for i in range(a, b + 1)]
        elif cmd == 'say':
            who, _, txt = rest.partition(' '); sc['steps'].append(('say', who, txt))
        elif cmd == 'narrate': sc['steps'].append(('say', 'narrator', rest))
        elif cmd == 'journal': sc['steps'].append(('say', 'narrator', 'Journal Entry: ' + rest))
        elif cmd == 'code': sc['steps'].append(('code', bytes(int(x, 16) for x in rest.split())))
        elif cmd == 'do': sc['steps'].append(('do', rest))
        # flow control: a code step that leaves a value runs the step with that id next (BF's own talk scripts do
        # 'push flag; call 27; jz +4; push 3; end'); an id past the last step ends the list
        elif cmd == 'label': sc['steps'].append(('label', rest.strip()))
        elif cmd == 'goto': sc['steps'].append(('goto', rest.strip()))
        elif cmd == 'stop': sc['steps'].append(('goto', '__end__'))
        elif cmd in ('if_flag', 'unless_flag'):
            f, lab = rest.split(); sc['steps'].append(('ifflag', int(f, 0), lab, cmd == 'if_flag'))
        elif cmd == 'set_flag': sc['steps'].append(('do', 'call 29 %d' % int(rest, 0)))
        elif cmd == 'run': sc['steps'].append(('run', rest.strip()))          # type 7: run another named list
        else: raise ValueError('%s: unknown command %r' % (path, cmd))
    return sc


def texts(scenes):
    return [s[2] for sc in scenes for s in sc['steps'] if s[0] == 'say']


def original_steps(rom, lst):
    """{id: bytes} for the step list at ROM offset lst. Step length = distance to the next step in memory."""
    ptrs = []
    while True:
        p = struct.unpack_from('<I', rom, lst + 4 * len(ptrs))[0]
        if not p: break
        ptrs.append(p - BASE)
    order = sorted(set(ptrs)); out = {}
    for p in ptrs:
        nxt = [q for q in order if q > p]
        end = nxt[0] if nxt else lst
        sid = struct.unpack_from('<H', rom, p)[0]
        out[sid] = bytes(rom[p:min(end, p + 0x400)])
    return out


def speaker(al, who):
    if who in al: return al[who]
    if who.startswith('#'): return int(who[1:])
    return int(who, 16)


NAMED = {}      # name -> bus address of a compiled named list (NPC talk scripts etc.), filled by compile_all


def compile_all(rom, scenes, refs, al, at, actors=None):
    """rom: bytearray (text already built); refs: {text: packed ref}. Writes steps + lists at `at`. Returns end.
    Named lists ('name X', or 'list X' sections) are recorded in NAMED."""
    NAMED.clear()
    actors = actors or {}
    cur = at
    def put(data):
        nonlocal cur
        a = cur; rom[a:a + len(data)] = data; cur = (a + len(data) + 3) & ~3
        return BASE + a
    expanded = []
    for sc in scenes:                                          # split "list" sections into separate named scenes
        if sc.get('lists'):
            cuts = sc['lists'] + [(None, len(sc['steps']))]
            for (nm, a), (_, b) in zip(cuts, cuts[1:]):
                expanded.append(dict(sc, steps=sc['steps'][a:b], name=nm, replace=None, lists=None))
        else: expanded.append(sc)
    fixups = []                                                # (rom offset, list name) for 'run' steps
    def push(v): return bytes([0x00, v]) if 0 <= v < 256 else b'\x01' + enc_varint(v)
    for sc in expanded:
        orig = original_steps(rom, sc['replace']) if sc['replace'] else {}
        ptrs = []
        labels, steps, k = {}, [], 0
        # A code step that leaves a value v jumps: the engine moves to step v and then advances one, so the value for
        # a label is the id of the step BEFORE it (verified 2026-11-01: if_flag to the 11th step needs 10). Stop =
        # jump to the last step. A label on the first step can't be reached (0 = no jump).
        for st in sc['steps']:
            if st[0] == 'label':
                assert k > 0, 'label %s on the first step of a list' % st[1]; labels[st[1]] = k
            else: steps.append(st); k += 1
        labels['__end__'] = len(steps)
        for n, st in enumerate(steps, 1):
            if st[0] == 'goto':
                b = struct.pack('<HB', n, 0) + push(labels[st[1]]) + b'\x11'
            elif st[0] == 'ifflag':
                tgt = push(labels[st[2]])
                b = struct.pack('<HB', n, 0) + push(st[1]) + bytes([0x02, 27 if st[3] else 28, 0x13]) + \
                    struct.pack('>H', 2 + len(tgt)) + tgt + b'\x11'
            elif st[0] == 'run':
                b = struct.pack('<HBxI', n, 7, 0)                  # the list pointer is word-aligned at +4
                ptrs.append(put(bytes(b))); fixups.append((ptrs[-1] - BASE + 4, st[1])); continue
            elif st[0] == 'keep':
                b = bytearray(orig[st[1]]); struct.pack_into('<H', b, 0, n)
            elif st[0] == 'say':
                b = struct.pack('<HBB', n, 5, speaker(al, st[1])) + struct.pack('<I', refs[st[2]])
            else:
                code = st[1] if st[0] == 'code' else assemble(st[1], actors)
                code = code if code.endswith(b'\x11') else code + b'\x11'
                b = struct.pack('<HB', n, 0) + code
            ptrs.append(put(bytes(b)))
        lst = put(struct.pack('<%dI' % (len(ptrs) + 1), *(ptrs + [0])))
        if sc.get('name'): NAMED[sc['name']] = lst
        if sc['replace']:
            old = struct.pack('<I', BASE + sc['replace']); i = -1
            while True:
                i = rom.find(old, i + 1)
                if i < 0: break
                if i % 4 == 0 and i < 0x800000: struct.pack_into('<I', rom, i, lst)
    for off, name in fixups: struct.pack_into('<I', rom, off, NAMED[name])
    return cur


# ---------- bytecode assembler (for "do" steps) ----------
# Natives named from the opening scene (Snake Way); arguments are pushed left to right.
NATIVES = {'begin_moves': (56, 0), 'move': (96, 3), 'wait_moves': (58, 0), 'face': (90, 2), 'journal_flag': (31, 1),
           'music': (35, 1)}


def enc_varint(v):
    u = (abs(v) << 1) | (1 if v < 0 else 0)
    groups = []
    while True:
        groups.append(u & 0x7F); u >>= 7
        if not u: break
    groups.reverse()
    return bytes([g | 0x80 for g in groups[:-1]] + [groups[-1]])


def assemble(text, actors):
    """'move gevo 88 160; wait_moves' -> bytecode. Actor names map to actor id + 9 (the game's actor index);
    'call N a b c' calls any native by number."""
    out = bytearray()
    for part in [p_.strip() for p_ in text.split(';') if p_.strip()]:
        tok = part.split(); name = tok[0]
        if name == 'heal':                         # current player: hp = max_hp; ki = max_ki (vars 0x0C-0x0F)
            out += bytes([0x02, 0x0D, 0x03, 0x0C, 0x02, 0x0F, 0x03, 0x0E]); continue   # as the Senzu Bean
        args = [actors[a] + 9 if a in actors else int(a, 0) for a in tok[1:]]
        if name == 'call': num, args = args[0], args[1:]
        else: num = NATIVES[name][0]
        if len(args) == 1 and 0 <= args[0] < 256: out += bytes([0x00, args[0]])
        elif args: out += bytes([0x1D, len(args)]) + b''.join(enc_varint(a) for a in args)
        out += bytes([0x02, num])
    return bytes(out)


# ---------- bytecode disassembler ----------
OPS = {0x00: ('push', 'u8'), 0x01: ('push', 'var'), 0x02: ('call', 'u8'), 0x03: ('set', 'u8'), 0x04: ('and', ''),
       0x05: ('or', ''), 0x06: ('neg', ''), 0x07: ('add', ''), 0x08: ('sub', ''), 0x09: ('mul', ''), 0x0A: ('div', ''),
       0x1E: ('mod', ''), 0x0B: ('eq', ''), 0x0C: ('ne', ''), 0x0D: ('gt', ''), 0x0E: ('ge', ''), 0x0F: ('lt', ''),
       0x10: ('le', ''), 0x11: ('end', ''), 0x12: ('jmp', 's16be'), 0x13: ('jz', 's16be'), 0x14: ('pop', ''),
       0x15: ('inc', 'u8'), 0x16: ('dec', 'u8'), 0x17: ('op17', 'u8'), 0x18: ('op18', 'u8'), 0x19: ('op19', 'u8'),
       0x1A: ('op1a', 'u8'), 0x1B: ('loopctr', ''), 0x1C: ('loop', 'u16'), 0x1D: ('pushn', 'n')}


def varint(b, i):
    """7-bit groups, MSB first, continuation in bit 7; low bit of the result = sign."""
    v = 0
    while True:
        c = b[i]; i += 1; v = (v << 7) | (c & 0x7F)
        if not c & 0x80: break
    return (-(v >> 1) if v & 1 else v >> 1), i


def disasm(b, i=0, names=None):
    out = []
    while i < len(b):
        op = b[i]; i += 1
        if op not in OPS: out.append('?%02x' % op); break
        name, kind = OPS[op]
        if kind == 'u8': arg = b[i]; i += 1
        elif kind == 'var': arg, i = varint(b, i)
        elif kind == 's16be': arg = struct.unpack('>h', b[i:i + 2])[0]; i += 2
        elif kind == 'u16': arg = struct.unpack('<H', b[i:i + 2])[0]; i += 2
        elif kind == 'n':
            n = b[i]; i += 1; arg = []
            for _ in range(n):
                v, i = varint(b, i); arg.append(v)
        else: arg = None
        if name == 'call' and names: out.append('call %s' % names.get(arg, '0x%02x' % arg))
        else: out.append(name if arg is None else '%s %s' % (name, arg))
        if op == 0x11: break
    return out, i
