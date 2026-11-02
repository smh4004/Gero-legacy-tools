"""Area edits for LoG4: attach imported LoG2 maps to BF areas, swap spawn records to new actors, add doors, and add
brand-new areas.

AreaEntry table ROM 0x8E2E0 (452 x 56 bytes). Looked up by 0x080089FC: linear search over the count returned by
0x080125E0 (movs r0,#0xff; adds r0,#imm -> max 510) for byte0 = world, byte1 = area; the table address is the literal at
0x8A58 (its only reference). Word 0 = world | area<<8 | 1<<16 | exit count<<24. +4 = object count, +0xC = name (UI index),
+0x10 -> exits [{u32 condition param, u32 exit object}] x exit count, +0x14 -> object list (pointers to NPC objects),
+0x24 = music, +0x2C -> area struct (word 0 = map pointer M+4, then inline spawn records).

Spawn record (9 words): [0x0800A223][0x00030032] [0x08017DA3][0x00020002][y<<16|x][talk step list][actor id + 9][1]
[ptr to record start]. The object list points at the 0x08017DA3 word (record + 8).
Doors (exit objects, rect u16 x0,y0,x1,y1):
  warp   [0x08007675][0x0800776D][rect][dest][arrival y<<16 | x] - the engine's own doors (decoded from 0x08007674 /
         0x080075AC): dest byte 0 low nibble = the key the player must hold inside the rect (0 DOWN, 1 UP, 2 LEFT,
         3 RIGHT, via the table at 0x080707D8); byte 0 high nibble = arrival facing + 1 (0 = face the key direction);
         the player arrives walking ~14 px that way. Byte 1 = world, byte 2 = area, byte 3 = room in that area (1 = the
         first; 0 = the area's default). The map record's pre-struct is the same object. Every door is played by
         tools/clipcheck.py (walk in, expect the destination).
  script [0x08007387][0x080071A7][rect][ptr to bytecode]. Native 114/115 (world, area, room, cam x, cam y) loads an area
         but x/y only set the camera and the player keeps its position, so script doors suit cutscenes, not walking."""
import struct
import mapimport

AREAS, COUNT = 0x8E2E0, 452
NIGHT = {}                     # world id -> [map record offsets], for new areas with "night": true (filled by apply)
TABLE_LIT, COUNT_INSN = 0x8A58, 0x125E0
BASE = 0x08000000


def area_count(rom):
    """The area count returned by the count function at COUNT_INSN: BF's 'movs r0,#0xff; adds r0,#k' (max 510) or
    LoG4's 'movs r0,#a; lsls r0,r0,#1; adds r0,#b; bx lr' (2a + b, max 765; the 2 bytes after BF's bx lr are padding)."""
    h = struct.unpack_from('<4H', rom, COUNT_INSN)
    if h[0] == 0x20FF and h[1] >> 8 == 0x30: return 0xFF + (h[1] & 0xFF)
    if h[0] >> 8 == 0x20 and h[1] == 0x0040 and h[2] >> 8 == 0x30: return 2 * (h[0] & 0xFF) + (h[2] & 0xFF)
    return COUNT


def entry(rom, world, area, table=AREAS, count=COUNT):
    for k in range(count):
        e = table + 56 * k
        if rom[e] == world and rom[e + 1] == area: return e
    raise KeyError((world, area))


def entry_any(rom, world, area):
    """AreaEntry offset in the table the game uses (relocated by apply, with LoG4's new areas)."""
    tab = struct.unpack_from('<I', rom, TABLE_LIT)[0] - BASE
    return entry(rom, world, area, tab, area_count(rom))


class _W:
    def __init__(self, rom, at): self.rom, self.cur = rom, at
    def put(self, data):
        a = self.cur; self.rom[a:a + len(data)] = data; self.cur = (a + len(data) + 3) & ~3
        return BASE + a


EXAMINE = {'down': 0x03001944, 'up': 0x0300193C, 'left': 0x0300194C, 'right': 0x03001954}   # A + facing conditions
_getters = {}


def _getter(W, facing):
    """Exit condition getter for "press A while facing <facing> inside the rect" (BF's own up-getter is 0x0800774F;
    the other three condition objects exist in RAM without getters, so a 8-byte stub is written: ldr r0,[pc]; bx lr)."""
    if facing == 'up': return 0x0800774F
    if facing not in _getters:
        while W.cur & 3: W.cur += 1
        _getters[facing] = W.put(struct.pack('<HHI', 0x4800, 0x4770, EXAMINE[facing])) | 1
    return _getters[facing]


def _doors(W, doors, actor_ids, talk=None):
    import scenes
    exits = []
    def code_of(act):
        code = (bytes.fromhex(act[4:]) if act.startswith('hex ') else scenes.assemble(act, actor_ids))
        return code if code.endswith(b'\x11') else code + b'\x11'
    for d in doors:
        x0, y0, x1, y1 = d['rect']
        if 'warp' in d:     # engine door, see the module notes: [fns][rect][dest][arrival y<<16 | x]
            w, a, x, y = d['warp']
            D = {'down': 0, 'up': 1, 'left': 2, 'right': 3}
            key = D[d.get('dir', 'down')]                     # direction the player walks into it
            face = D[d['face']] + 1 if 'face' in d else 0    # facing / walking direction on arrival (default = key)
            dest = key | (face << 4) | (w << 8) | (a << 16) | (d.get('room', 1) << 24)
            obj = W.put(struct.pack('<IIHHHHII', 0x08007675, 0x0800776D, x0, y0, x1, y1, dest, (y << 16) | x))
        else:               # script door: rect object running inline bytecode, or a step list ("event")
            if 'examine' in d: fn2 = _getter(W, d['examine'])  # press A facing that way inside the rect
            else: fn2 = int(str(d.get('fn2', '0x080071A7')), 0)   # 0x080071A7 = hold UP inside the rect
            if 'event' in d:    # class 0x0800742D runs a step list (dialogue + code), named in log4/scenes/*.scene
                obj = W.put(struct.pack('<IIHHHHI', 0x0800742D, fn2, x0, y0, x1, y1, talk[d['event']]))
            else:               # "hex 02 15 ..." = raw bytecode (branches), else assembler text
                obj = W.put(struct.pack('<IIHHHHI', 0x08007387, fn2, x0, y0, x1, y1, W.put(code_of(door_action(d)['action']))))
        # exit param = condition: 0 = always, else a pointer to bytecode that must leave true ("when"; BF uses flag
        # tests such as 'push 176; call 28', see RE_NOTES)
        param = W.put(code_of(d['when'])) if 'when' in d else d.get('param', 0)
        exits.append((param, obj))
    return exits


def _set_exits(rom, W, e, exits):
    rom[e + 3] = len(exits)
    struct.pack_into('<I', rom, e + 0x10, W.put(b''.join(struct.pack('<II', *x) for x in exits)) if exits else 0)


def door_action(d):
    """'to': [world, area, x, y] -> load_area bytecode text. Entrance 1 = arrive at (x, y), as BF's own scripts do
    (e.g. 18,4,1,68,160); entrance 0 = the area's default spawn (new areas have none), used when x = y = 0."""
    if 'action' in d: return d
    w, a, x, y = d['to']
    return dict(d, action='call 114 %d %d %d %d %d' % (w, a, 1 if (x or y) else 0, x, y))


def apply(rom, cfg, l2, actor_ids, at, talk=None, doors=None):
    """talk: {name: step list bus address} for NPC talk scripts compiled elsewhere.
    doors: tools/doors.plan() result (animated door panels + triggers, regions to drop)."""
    import doors as doors_mod
    W = _W(rom, at); done = []; worlds = {}; NIGHT.clear()
    talk = talk or {}
    doors = doors or {'areas': {}, 'maps': {}}
    _getters.clear()
    empty_talk = W.put(b'\0' * 4)                         # talk list for door panels (pressing A does nothing)

    def kill_pre_door(M_bus):
        """Empty the rect of a map's built-in door (the map record's pre-struct, a warp object). Found 2026-11-02: BF
        and LoG2 maps carry their own doors to BF areas (West City's Z-Mart door -> BF 0:92, the LoG2 lab's south door
        -> BF 8:48, BF 1:16's cave door -> 1:17 with a BF story scene...). LoG4 areas list every exit themselves."""
        pre = struct.unpack_from('<I', rom, M_bus - BASE)[0] - BASE
        if 0 <= pre < len(rom) - 0x18 and struct.unpack_from('<I', rom, pre)[0] == 0x08007675:
            struct.pack_into('<4H', rom, pre + 8, 0, 0, 0, 0)

    def drop_regions(newM, mo):
        block = doors['maps'].get(('block', mo))
        if block:                                           # make the doorway floor above the walk-in target solid
            import numpy as np
            M = newM - BASE; mp = struct.unpack_from('<I', rom, M + 0x38)[0] - BASE
            bits = np.unpackbits(np.frombuffer(bytes(mapimport.wfz_data(bytes(rom[mp:mp + 0x10000]), 0)), np.uint8),
                                 bitorder='little').reshape(-1, 256)
            for ty, tx in block: bits[ty, tx] = 0
            new = np.packbits(bits.reshape(-1), bitorder='little').tobytes()
            struct.pack_into('<I', rom, M + 0x38, W.put(struct.pack('<II', 0, len(new)) + new))   # stored (type 0)
        used = doors['maps'].get(mo)
        if not used: return
        M = newM - BASE; n = struct.unpack_from('<I', rom, M + 0x28)[0]
        keep = [i for i in range(n) if i not in used]
        assert keep == list(range(len(keep))), 'door regions must come after the regions that are kept'
        struct.pack_into('<I', rom, M + 0x28, len(keep))

    def door_extras(w, a):
        ds = doors['areas'].get((w, a), [])
        spawns = [{'actor': nm, 'x': x, 'y': y, 'talk_ptr': hex(empty_talk)} for d in ds for (nm, x, y) in d['panels']]
        exits = []
        for d in ds:
            code = doors_mod.trigger_code([(actor_ids[nm] + 9, x, y) for nm, x, y in d['panels']], d['dest'])
            lst = W.put(struct.pack('<II', W.put(struct.pack('<HB', 1, 0) + code), 0))
            x0, y0, x1, y1 = d['trigger']
            exits.append((0, W.put(struct.pack('<IIHHHHI', 0x0800742D, doors_mod.UP_HELD, x0, y0, x1, y1, lst))))
        return spawns, exits

    def enemy_records(enemies):
        """BF field enemies (decomp tools/assets/actors.py): 8-word records [0x0800FD55 spawn fn][condition][type = row
        of the enemy stats table][y<<16|x][character = sprite, actor id + 9][0x080555A0 behaviour][1][0x080716EC ai];
        the object list points at the record. Condition: 0 always, 0x1NNNN flag set, 0x2NNNN flag clear, or a script
        pointer (spawn if it returns non-zero). Default character = the one BF pairs with the type."""
        known = {19: 76, 71: 184, 78: 199, 82: 202, 101: 241, 123: 255, 124: 256, 125: 257, 131: 272, 8: 34, 12: 39, 20: 78, 100: 240, 62: 164, 76: 191, 94: 230, 15: 70, 17: 72, 19: 76, 36: 122, 41: 133, 44: 137, 47: 141, 48: 142, 64: 167, 72: 187, 75: 190, 97: 235, 108: 247, 127: 259, 128: 263, 140: 291}
        out = []
        for en in enemies:
            ch = actor_ids[en['actor']] + 9 if 'actor' in en else en.get('character', en.get('param', known.get(en['type'])))
            assert ch is not None, 'enemy type %d: give its character (decomp assets/tables/spawns.csv)' % en['type']
            cond = en.get('condition', 0)              # 0 always, 0x1NNNN flag set, 0x2NNNN clear, or script text
            if isinstance(cond, str):
                import scenes
                cond = W.put(bytes.fromhex(cond[4:]) if cond.startswith('hex ') else scenes.assemble(cond, {}) + b'\x11')
            out.append(W.put(struct.pack('<8I', 0x0800FD55, cond, en['type'], (en['y'] << 16) | en['x'], ch,
                                         0x080555A0, 1, 0x080716EC)))
        return out

    def spawn_block(spawns):
        """Spawn records (9 words each, last word = the record's own address); returns object-list pointers."""
        recs = bytearray(); offs = []
        for s_ in spawns:
            offs.append(len(recs))
            face = {'down': 0, 'up': 1, 'left': 2, 'right': 3}[s_.get('face', 'down')]
            recs += struct.pack('<9I', 0x0800A223, (face << 16) | 0x32, 0x08017DA3, 0x00020002, (s_['y'] << 16) | s_['x'],
                                talk.get(s_.get('talk'), int(str(s_.get('talk_ptr', '0')), 0)),
                                (actor_ids[s_['actor']] if 'actor' in s_ else s_['actor_id']) + 9, 1, 0)
        blk = W.put(bytes(recs))
        for off in offs: struct.pack_into('<I', rom, blk - BASE + off + 32, blk + off)
        return [blk + off + 8 for off in offs]
    for a in cfg.get('areas', []):
        e = entry(rom, a['world'], a['area'])
        if a.get('pre_door') != 'keep' and ('doors' in a or 'doors_append' in a):
            kill_pre_door(struct.unpack_from('<I', rom, struct.unpack_from('<I', rom, e + 0x2C)[0] - BASE)[0] - 4)
        st = struct.unpack_from('<I', rom, e + 0x2C)[0] - BASE
        if 'map_log2' in a and l2 is not None:
            newM, W.cur = mapimport.import_map(rom, l2, int(a['map_log2'], 16), W.cur)
            struct.pack_into('<I', rom, st, newM + 4)
            drop_regions(newM, int(a['map_log2'], 16))
        if 'keep_objects' in a:                             # drop the rest of the area's object list (leftovers)
            rom[e + 4] = a['keep_objects']
        if 'object_talk' in a or 'drop_objects' in a:      # by index in the area's ORIGINAL object list
            n0 = rom[e + 4]; lp = struct.unpack_from('<I', rom, e + 0x14)[0] - BASE
            objs = [struct.unpack_from('<I', rom, lp + 4 * i)[0] for i in range(n0)]
            for idx, name in a.get('object_talk', {}).items():   # NPC object: talk list at +12 from its behaviour word
                o = objs[int(idx)] - BASE
                assert struct.unpack_from('<I', rom, o)[0] == 0x08017DA3, 'object %s of %d:%d is not an NPC' % (idx, a['world'], a['area'])
                struct.pack_into('<I', rom, o + 12, talk[name])
            drop = set(a.get('drop_objects', []))
            if drop:
                keep = [p_ for i, p_ in enumerate(objs) if i not in drop]
                struct.pack_into('<I', rom, e + 0x14, W.put(struct.pack('<%dI' % len(keep), *keep)) if keep else 0)
                rom[e + 4] = len(keep)
        for word, name in a.get('spawn_ids', {}).items():
            struct.pack_into('<I', rom, st + 4 * int(word), actor_ids[name] + 9)
        for word, name in a.get('spawn_talk', {}).items():     # word = the spawn_ids word; its talk list is 1 before
            struct.pack_into('<I', rom, st + 4 * (int(word) - 1), talk[name])
        for word, (x, y) in a.get('spawn_pos', {}).items():    # word = the spawn_ids word; position word is 2 before
            struct.pack_into('<I', rom, st + 4 * (int(word) - 2), (y << 16) | x)
        if 'name' in a: struct.pack_into('<H', rom, e + 0xC, a['name'])
        dsp, dex = door_extras(a['world'], a['area'])
        dsp = dsp + a.get('spawns_append', [])              # extra NPCs ("actor": name or "actor_id": BF actor id)
        if dsp:                                             # append the door panels / extra NPCs to the object list
            n0 = rom[e + 4]; lp = struct.unpack_from('<I', rom, e + 0x14)[0] - BASE
            ptrs = [struct.unpack_from('<I', rom, lp + 4 * i)[0] for i in range(n0)] + spawn_block(dsp)
            struct.pack_into('<I', rom, e + 0x14, W.put(struct.pack('<%dI' % len(ptrs), *ptrs))); rom[e + 4] = len(ptrs)
        if 'doors' in a:
            _set_exits(rom, W, e, _doors(W, a['doors'], actor_ids, talk) + dex)
        if 'doors_append' in a:                             # keep the area's own exits and add ours after them
            n0 = rom[e + 3]; xp = struct.unpack_from('<I', rom, e + 0x10)[0] - BASE
            old = [struct.unpack_from('<II', rom, xp + 8 * i) for i in range(n0)] if n0 else []
            old = [x for i, x in enumerate(old) if i not in set(a.get('drop_exits', []))]   # e.g. BF story triggers
            _set_exits(rom, W, e, old + _doors(W, a['doors_append'], actor_ids, talk))
        if 'palette_act' in a: worlds.setdefault(a['palette_act'], set()).add(a['world'])
        done.append('%d:%d' % (a['world'], a['area']))

    new = cfg.get('new_areas', [])
    if new and l2 is not None:
        entries = []; new_maps = {}
        for a in new:
            tw, ta = a.get('template', [1, 1])
            ent = bytearray(rom[entry(rom, tw, ta):entry(rom, tw, ta) + 56])
            ent[0], ent[1], ent[2] = a['world'], a['area'], 1
            if 'map_from' in a and tuple(a['map_from']) in new_maps:   # another new area's map (listed earlier)
                newM = new_maps[tuple(a['map_from'])]
            elif 'map_from' in a:                              # reuse another area's (already built) map
                fe = entry(rom, *a['map_from'])
                newM = struct.unpack_from('<I', rom, struct.unpack_from('<I', rom, fe + 0x2C)[0] - BASE)[0] - 4
                if a.get('pre_door') != 'keep': kill_pre_door(newM)
            else:
                newM, W.cur = mapimport.import_map(rom, l2, int(a['map_log2'], 16), W.cur)
                drop_regions(newM, int(a['map_log2'], 16))
                if a.get('pre_door') != 'keep':                # the map's built-in LoG2 door (pre-struct warp with LoG2
                    pre = struct.unpack_from('<I', rom, newM - BASE)[0] - BASE      # world/area numbers, i.e. some BF
                    # area): empty rect. Our 'doors' are the area's exits (found 2026-11-02: 1:85, 1:71, 1:102, 1:109...
                    # had live built-in doors to BF areas where no LoG4 door covers them)
                    struct.pack_into('<4H', rom, pre + 8, 0, 0, 0, 0)
            if 'keep_regions' in a and 'map_from' in a:        # drop map OBJ regions (e.g. BF's level-140 gate graphic)
                rec = bytearray(rom[newM - 4 - BASE:newM - BASE + 0x54])
                self_ = struct.unpack_from('<I', rec, 4 + 0x48)[0]
                nm = W.put(bytes(rec)) + 4
                struct.pack_into('<I', rom, nm - BASE + 0x48, nm + (self_ - newM)); newM = nm
                M = newM - BASE; rp = struct.unpack_from('<I', rom, M + 0x2C)[0] - BASE
                keep = b''.join(bytes(rom[rp + 0x18 * i:rp + 0x18 * i + 0x18]) for i in a['keep_regions'])
                struct.pack_into('<I', rom, M + 0x28, len(a['keep_regions']))
                if keep: struct.pack_into('<I', rom, M + 0x2C, W.put(keep))
            if 'effect' in a and 'map_from' in a:              # map effect id (+0x44) override on a copied record
                rec = bytearray(rom[newM - 4 - BASE:newM - BASE + 0x54])
                self_ = struct.unpack_from('<I', rec, 4 + 0x48)[0]
                nm = W.put(bytes(rec)) + 4
                struct.pack_into('<I', rom, nm - BASE + 0x48, nm + (self_ - newM)); newM = nm
                struct.pack_into('<I', rom, newM - BASE + 0x44, a['effect'])
            if a.get('solid'):                                 # make pixel rects of the floor solid (map edge exits:
                import numpy as np                             # the player stops in view and the warp fires)
                if 'map_from' in a:                            # BF map shared with its own area: copy the record first
                    rec = bytearray(rom[newM - 4 - BASE:newM - BASE + 0x54])      # (+0x48 points at newM - 4)
                    self_ = struct.unpack_from('<I', rec, 4 + 0x48)[0]
                    nm = W.put(bytes(rec)) + 4
                    struct.pack_into('<I', rom, nm - BASE + 0x48, nm + (self_ - newM)); newM = nm
                M = newM - BASE; mp = struct.unpack_from('<I', rom, M + 0x38)[0] - BASE
                bits = np.unpackbits(np.frombuffer(bytes(mapimport.wfz_data(bytes(rom[mp:mp + 0x10000]), 0)), np.uint8),
                                     bitorder='little').reshape(-1, 256).copy()
                for x0, y0, x1, y1 in a['solid']: bits[y0 // 8:(y1 + 7) // 8, x0 // 8:(x1 + 7) // 8] = 0
                newb = np.packbits(bits.reshape(-1), bitorder='little').tobytes()
                struct.pack_into('<I', rom, M + 0x38, W.put(struct.pack('<II', 0, len(newb)) + newb))
            if a.get('erase_tiles') or a.get('walkable'):      # remove map art (e.g. LoG2's electric fence in 1:68)
                import numpy as np                             # and open its collision
                if 'map_from' in a:
                    rec = bytearray(rom[newM - 4 - BASE:newM - BASE + 0x54])
                    self_ = struct.unpack_from('<I', rec, 4 + 0x48)[0]
                    nm = W.put(bytes(rec)) + 4
                    struct.pack_into('<I', rom, nm - BASE + 0x48, nm + (self_ - newM)); newM = nm
                M = newM - BASE
                for ed in a.get('erase_tiles', []):            # {"layer": i, "tiles": [tx0, ty0, tx1, ty1]} (inclusive, 8 px)
                    hp = struct.unpack_from('<I', rom, M + 0x18 + 4 * ed['layer'])[0] - BASE
                    hw = list(struct.unpack_from('<6I', rom, hp)); cw, chh = hw[5] & 0xFF, (hw[5] >> 8) & 0xFF
                    cps = list(struct.unpack_from('<%dI' % (cw * chh), rom, hp + 0x18))
                    tx0, ty0, tx1, ty1 = ed['tiles']
                    for ci in range(cw * chh):
                        cy, cx = (ci // cw) * 32, (ci % cw) * 32
                        if tx1 < cx or tx0 >= cx + 32 or ty1 < cy or ty0 >= cy + 32: continue
                        ch = np.frombuffer(bytes(mapimport.wfz_data(bytes(rom[cps[ci] - BASE:cps[ci] - BASE + 0x10000]), 0))[:2048],
                                           '<u2').reshape(32, 32).copy()
                        ch[max(ty0 - cy, 0):min(ty1 - cy, 31) + 1, max(tx0 - cx, 0):min(tx1 - cx, 31) + 1] = 0
                        d = ch.astype('<u2').tobytes(); cps[ci] = W.put(struct.pack('<II', 0, len(d)) + d)
                    struct.pack_into('<I', rom, M + 0x18 + 4 * ed['layer'],
                                     W.put(struct.pack('<6I', *hw) + struct.pack('<%dI' % len(cps), *cps)))
                if a.get('walkable'):                          # pixel rects of floor made walkable
                    mp = struct.unpack_from('<I', rom, M + 0x38)[0] - BASE
                    bits = np.unpackbits(np.frombuffer(bytes(mapimport.wfz_data(bytes(rom[mp:mp + 0x10000]), 0)), np.uint8),
                                         bitorder='little').reshape(-1, 256).copy()
                    for x0, y0, x1, y1 in a['walkable']: bits[y0 // 8:(y1 + 7) // 8, x0 // 8:(x1 + 7) // 8] = 1
                    newb = np.packbits(bits.reshape(-1), bitorder='little').tobytes()
                    struct.pack_into('<I', rom, M + 0x38, W.put(struct.pack('<II', 0, len(newb)) + newb))
            new_maps[(a['world'], a['area'])] = newM
            dsp, dex = door_extras(a['world'], a['area'])
            # area struct: map pointer, then spawn records
            recs = bytearray(struct.pack('<I', newM + 4)); spawn_offs = []
            for s in a.get('spawns', []) + dsp:
                spawn_offs.append(len(recs))
                face = {'down': 0, 'up': 1, 'left': 2, 'right': 3}[s.get('face', 'down')]
                recs += struct.pack('<9I', 0x0800A223, (face << 16) | 0x32, 0x08017DA3, 0x00020002, (s['y'] << 16) | s['x'],
                                    talk.get(s.get('talk'), int(str(s.get('talk_ptr', '0')), 0)),
                                    (actor_ids[s['actor']] if 'actor' in s else s['actor_id']) + 9, 1, 0)
            st = W.put(bytes(recs))
            for off in spawn_offs:                      # last word = pointer to the record start
                struct.pack_into('<I', rom, st - BASE + off + 32, st + off)
            struct.pack_into('<I', ent, 0x2C, st)
            objs = [st + off + 8 for off in spawn_offs] + enemy_records(a.get('enemies', []))
            struct.pack_into('<I', ent, 4, len(objs))
            struct.pack_into('<I', ent, 0x14, W.put(b''.join(struct.pack('<I', o) for o in objs)) if objs else 0)
            if 'name' in a: struct.pack_into('<I', ent, 0xC, a['name'])
            if 'music' in a: struct.pack_into('<I', ent, 0x24, a['music'])
            if 'flag8' in a: struct.pack_into('<I', ent, 8, a['flag8'])
            copied = []                                     # "exits_from": [[world, area, exit index]] (e.g. a save pad)
            for cw, ca, ci in a.get('exits_from', []):
                ce = entry(rom, cw, ca); copied.append(struct.unpack_from('<II', rom, struct.unpack_from('<I', rom, ce + 0x10)[0] - BASE + 8 * ci))
            exits = copied + _doors(W, a.get('doors', []), actor_ids, talk) + dex
            ent[3] = len(exits)
            struct.pack_into('<I', ent, 0x10, W.put(b''.join(struct.pack('<II', *x) for x in exits)) if exits else 0)
            entries.append(bytes(ent))
            if 'palette_act' in a: worlds.setdefault(a['palette_act'], set()).add(a['world'])
            if a.get('night'): NIGHT.setdefault(a['world'], []).append(newM - BASE)   # build.py: moonlit BG palette
            done.append('new %d:%d' % (a['world'], a['area']))
        n = COUNT + len(entries)
        assert n <= 3 * 0xFF, 'area count over the movs/lsls/adds limit (765)'
        tab = W.put(bytes(rom[AREAS:AREAS + 56 * COUNT]) + b''.join(entries))
        struct.pack_into('<I', rom, TABLE_LIT, tab)
        a_ = min(0xFF, n // 2)                       # movs r0,#a ; lsls r0,r0,#1 ; adds r0,#b ; bx lr  (n = 2a + b)
        struct.pack_into('<4H', rom, COUNT_INSN, 0x2000 | a_, 0x0040, 0x3000 | (n - 2 * a_), 0x4770)
    return done, worlds, W.cur
