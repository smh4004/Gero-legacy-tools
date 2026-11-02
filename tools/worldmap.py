"""Act 3 world map (BF's Earth map, area 0:50, flown in Mode 7). log4/worldmap.json lists LoG4's landing spots.

0:50's exits (BF): pairs of 20-byte records sharing a rect -
  name   [0x080076C5][0x0800776D hover][rect x0,y0,x1,y1 u16][u32 UI string]  - shows the place name while overhead
  land   [0x08007387][getter][rect][ptr bytecode]                              - runs when the player lands in the rect
         getter 0x08034355 = landed (hold A to descend), 0x0803436F = ascended into it (Kami's Lookout, up in the sky)
The whole exit list is rewritten: one name record (+ one landing record per land rect) per LoG4 location; BF's places
that LoG4 doesn't use are gone (no name, nowhere to land). The HUD hint record (A: Descend/Land, B: Ascend) is kept.
Landing script: fade out; pick the destination by era (first entry whose "when" holds); load it (native 119, room 1)
facing down; fade in; give control back. Natives: 118(world, area, room, x, y) loads 0:50 at map (x, y) - used by the
take-off exits that areas.json gives every Act 3 destination (tools/areas.py door "action").
Verified 2026-11-02: 118 0 50 0 x y from a list puts 17 over the map at (x, y); holding A over West City lands."""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenes
from areas import entry_any, BASE

NAME_FN, HOVER, LAND_FN, LANDED, ASCENDED = 0x080076C5, 0x0800776D, 0x08007387, 0x08034355, 0x0803436F
HINT_UI = 597                                    # "A Button: Descend/Land  B Button: Ascend"


def cond_code(spec):
    """'set:N & clear:M' -> bytecode leaving 1/0 (no end)."""
    out = b''
    for i, t in enumerate(spec.split('&')):
        k, f = t.strip().split(':')
        out += scenes.assemble('call %d %d' % (27 if k == 'set' else 28, int(f)), {})
        if i: out += b'\x04'
    return out


def landing_code(dests):
    """dests: [{"to": [w, a, x, y], "when": "set:380"}...]; the last one without "when" is the default."""
    body = b''
    tail = scenes.assemble('call 121 30; call 47; call 51 0', {}) + b'\x11'
    for d in dests:
        w, a, x, y = d['to']
        load = scenes.assemble('call 119 %d %d 1 %d %d' % (w, a, x, y), {}) + tail
        if 'when' in d:
            body += cond_code(d['when']) + b'\x13' + struct.pack('>h', 2 + len(load)) + load
        else:
            body += load; break
    return scenes.assemble('call 120 30', {}) + body


# BF's own record indices in 0:50's exit list (landing records, name record) per place. Rewriting the list from scratch
# made landing stop working (names showed, holding A never landed), so the list is copied and edited in place: same
# order and count, new UI names and landing scripts; places LoG4 doesn't use get an empty rect.
BF_PLACES = {'east_district': ([0], 1), 'west_city': ([2, 3], 4), 'hercule_city': ([5, 6], 7), 'roshi': ([8], 9),
             'lookout': ([10, 30], 11), 'papaya': ([12], 13), 'sw_forest': ([14], 15), 'pilaf': ([16], 17),
             'fukurou': ([18], 19), 'nataday': ([20], 21), 'thieves': ([22], 23), 'diablo': ([24], 25),
             'kyodai': ([26], 27), 'airship': ([28], 29), 'barren': ([], 33)}


def apply(rom, cfg_path, at):
    cfg = json.load(open(cfg_path))
    e = entry_any(rom, 0, 50)
    cur = [at]
    def put(data):
        a = cur[0]; rom[a:a + len(data)] = data; cur[0] = (a + len(data) + 3) & ~3
        assert cur[0] <= 0xAFFF00, 'worldmap data too big'
        return BASE + a
    n = rom[e + 3]; xp = struct.unpack_from('<I', rom, e + 0x10)[0] - BASE
    assert n == 35, 'world map exit list changed (%d)' % n
    old = [list(struct.unpack_from('<II', rom, xp + 8 * i)) for i in range(n)]
    recs = [bytearray(rom[o - BASE:o - BASE + 20]) for _, o in old]
    assert struct.unpack_from('<I', recs[34], 16)[0] == HINT_UI
    used = {}
    for loc in cfg['locations']:
        lands, name = BF_PLACES[loc['bf']]
        used[loc['bf']] = loc
        struct.pack_into('<I', recs[name], 16, loc['ui'])
        code = put(landing_code(loc['dests']) + b'\x11')
        for i in lands: struct.pack_into('<I', recs[i], 16, code)
    for k, (lands, name) in BF_PLACES.items():
        if k in used: continue
        for i in lands + [name]: struct.pack_into('<4H', recs[i], 8, 0, 0, 0, 0)     # nowhere: no name, no landing
    for i in (31, 32): struct.pack_into('<4H', recs[i], 8, 0, 0, 0, 0)                # BF story step lists
    ptrs = [put(bytes(r)) for r in recs]
    for i in range(n): old[i][1] = ptrs[i]
    for i in (10, 30): old[i][0] = 0                         # the Lookout: always (BF needed story flags)
    struct.pack_into('<I', rom, e + 0x10, put(b''.join(struct.pack('<II', *x) for x in old)))
    return cur[0], len(cfg['locations'])


def takeoff_action(loc):
    """areas.json door action: fly up to the map over this location."""
    x0, y0, x1, y1 = loc['rect']
    return 'call 120 20; call 118 0 50 0 %d %d; call 121 20' % ((x0 + x1) // 2, (y0 + y1) // 2)
