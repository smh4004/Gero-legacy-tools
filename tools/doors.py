"""Animated doors for LoG2-style door regions (see RE_NOTES "Map door regions").

A LoG2 lab door is a map "region": a 32x64 OBJ overlay that Buu's Fury draws above every character and never animates,
so it hid the player walking in. For every warp door whose rect overlaps a region of its (LoG2-imported) map:
  - the region is dropped from the map record;
  - its art becomes door-panel actors (NPC template 152; one actor frame may hold at most 1024 px, so a 32x40 door is two
    panels) with three states shown by facing: dir 0 closed, dir 2 half slid up into the frame, dir 1 open (empty, no
    collision box). Actors are depth-sorted with the player, so he is never drawn behind a door;
  - a trigger in front of the door (UP held, so arriving from the other room never fires it) runs: face panels half,
    wait, face panels open, then walks the player into the open doorway, where the warp takes him through.
It also makes the doorway floor above the walk-in target solid (map collision mask), so the warp fires as soon as the
player stands in the doorway. build.py calls plan() before the actors are built (actor_cfg) and areas.apply() places panels and triggers (spawns_for,
trigger_code) and drops the regions (drop_regions).
"""
import os, struct
import numpy as np

L2B, BFB = 0x08800000, 0x08000000
UP_HELD = 0x080071A7          # exit getter: UP held inside the rect
WAIT = 5                      # frames the half-open state is shown


def _wfz(l2, off):
    from wfz import decompress_stream
    t, size = struct.unpack_from('<II', l2, off)
    return l2[off + 8:off + 8 + size] if t == 0 else bytes(decompress_stream(l2, off + 8, size)[0])


_REMAP = None


def regions(l2, map_off):
    """[(rect, attr, attr2word, pixels)] of a LoG2 map record. pixels = h x w OBJ indices (tiles 1D, 8bpp); they are
    recoloured to BF's OBJ palette (mapimport.obj_remap; raw LoG2 indices showed teal doors orange)."""
    u = lambda o: struct.unpack_from('<I', l2, o)[0]
    n, recs, mask = u(map_off + 0x28), u(map_off + 0x2C), u(map_off + 0x30)
    if not n: return []
    data = _wfz(l2, mask - L2B)
    global _REMAP
    if _REMAP is None:
        import mapimport
        _REMAP = mapimport.obj_remap(l2, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bf.gba'), 'rb').read())
    data = _REMAP[np.frombuffer(data, np.uint8)].tobytes()
    out, pos = [], 0
    for i in range(n):
        x0, y0, x1, y1, attr, a2 = struct.unpack_from('<6I', l2, recs - L2B + 24 * i)
        w, h = x1 - x0, y1 - y0
        img = np.zeros((h, w), np.uint8)
        if (attr & 0x2000) and pos + w * h <= len(data):          # 8bpp graphic, tiles in 1D order
            t = np.frombuffer(data[pos:pos + w * h], np.uint8).reshape(-1, 8, 8); tw = w // 8
            for k, tile in enumerate(t): img[(k // tw) * 8:(k // tw) * 8 + 8, (k % tw) * 8:(k % tw) * 8 + 8] = tile
            pos += w * h
        out.append(((x0, y0, x1, y1), attr, a2, img))
    return out


def _overlap(a, b): return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _map_of(cfg_area, by_area):
    if 'map_log2' in cfg_area: return int(cfg_area['map_log2'], 16)
    if 'map_from' in cfg_area:                     # a BF area not in areas.json has a BF map: no LoG2 door regions
        src = by_area.get(tuple(cfg_area['map_from']))
        return _map_of(src, by_area) if src else None
    return None


def plan(cfg, l2):
    """-> {'actors': {name: actor cfg}, 'areas': {(w, a): [door]}, 'maps': {map_off: set(region index)}}.
    door = {'panels': [(name, spawn x, spawn y)], 'trigger': rect, 'dest': (x, y) to walk into, 'region': i}."""
    res = {'actors': {}, 'areas': {}, 'maps': {}}
    if l2 is None: return res
    allareas = cfg.get('areas', []) + cfg.get('new_areas', [])
    by_area = {(a['world'], a['area']): a for a in allareas}
    for a in allareas:
        mo = _map_of(a, by_area)
        if mo is None: continue
        regs = regions(l2, mo)
        for d in a.get('doors', []):
            if 'warp' not in d: continue
            for i, (rect, attr, a2, img) in enumerate(regs):
                if not _overlap(rect, d['rect']): continue
                # two warps on one doorway with complementary 'when' conditions share one set of panels and one trigger
                if any(x['region'] == i for x in res['areas'].get((a['world'], a['area']), [])): continue
                assert d.get('dir', 'down') == 'up', 'animated doors are done for UP doors only (need a key getter)'
                res['maps'].setdefault(mo, set()).add(i)
                names = _panels(res['actors'], mo, i, rect, img, a.get('palette_act'))
                x0, y0, x1, y1 = rect; dx0, dy0, dx1, dy1 = d['rect']
                # walk-in target: centred, as deep as a 32 px tall character can stand with his head still below the
                # top of the door opening (feet 42 px under the door art's top row: 34 + the ~8 px he still walks
                # before the solid floor stops him), and at least at the door's bottom edge
                art_top = y0 + int(np.where(img.any(1))[0].min()) if img.any() else y0
                dest = ((x0 + x1) // 2 - 7, min(art_top + 42, y1) - 8)
                # a warp fires when the player, inside its rect and holding the key, is stopped by a wall. The doorway
                # floor stays walkable well up into the door, so he would walk on under the wall above the opening
                # (tools/clipcheck.py fails that): the floor above the walk-in target is made solid instead.
                feet_row = (dest[1] + 8) // 8
                res['maps'].setdefault(('block', mo), set()).update(
                    (ty, tx) for ty in range(y0 // 8, feet_row) for tx in range(x0 // 8, (x1 + 7) // 8))
                res['areas'].setdefault((a['world'], a['area']), []).append(dict(
                    region=i, panels=names,
                    # zone just below the warp rect: the player walks up through it before reaching the warp
                    trigger=(dx0, dy1, dx1, dy1 + 16),
                    dest=dest))
    return res


def _panels(actors, mo, i, rect, img, act):
    """Cut the door art (rows with pixels) into stacked panels of <= 1024 px and make their 3-state frames."""
    x0, y0, x1, y1 = rect; w = x1 - x0
    rows = np.where(img.any(1))[0]
    top = int(rows.min()) if len(rows) else 0
    art = img[top:]; H = art.shape[0]
    states = []
    for s in (0, H // 2, H):                      # closed, half slid up, open (clipped to the door box)
        st = np.zeros_like(art); st[:H - s] = art[s:]; states.append(st)
    ph = 1024 // w
    cuts = list(range(H, 0, -ph))[::-1]           # panel bottoms, bottom panel ph tall, the rest on top
    bounds = [(max(0, b - ph), b) for b in cuts]
    # every panel's origin (= its feet, where the engine draws an NPC shadow it can't be told to skip) sits inside the
    # dark doorway, 45% down the door, so the shadows vanish against it; the art hangs below the origin (origin_dy)
    # Upper panels sit 2 px higher each, so they sort behind the panel below and their shadows hide under its art.
    base = y0 + top + int(H * 0.45)
    names = []
    for k, (a, b) in enumerate(bounds):
        feet = base - 2 * (len(bounds) - 1 - k)
        name = 'door_%x_%d_%d' % (mo, i, k)
        cl, half, op = (st[a:b] for st in states)
        actors[name] = {'template': 152, 'act': act, 'raw_frames': {
            # two identical frames per state: the engine only re-reads an NPC's frame when its animation advances, so
            # a one-frame animation would never show a new facing
            '0': [[cl, cl], [op, op], [half, half]], '1': [[cl, cl], [op, op], [half, half]]},
            'boxes': {'1': [0, 0, 0, 0]}, 'origin_dy': y0 + top + b - feet,
            '_note': 'door panel (auto, tools/doors.py): dir0 closed, dir2 half open, dir1 open'}
        # cell left = x0 -> spawn x = left + 9 for a 32-wide frame; spawn y = feet - 8
        names.append((name, x0 + w // 2 - 7, feet - 8))
    return names


def trigger_code(panels, dest):
    """Bytecode for the door event. panels = [(actor idx, spawn x, spawn y)]. Facing alone doesn't redraw an NPC during
    an event, but moving does (an actor turns to its direction of travel), so each panel is nudged 1 px sideways (its
    side frames = half open), then 1 px up (up frames = open, no collision box); then the current player walks into the
    doorway, out of the trigger, where the warp takes him through."""
    def moves(dx, dy):
        out = b'\x02\x38'                                         # begin_moves
        for idx, x, y in panels:
            out += b'\x1d\x03' + _v(idx) + _v(x + dx) + _v(y + dy) + b'\x02\x60'
        return out + b'\x02\x3a'                                  # wait_moves
    x, y = dest
    return (moves(-1, 0) + b'\x00' + bytes([WAIT]) + b'\x02\x88' + moves(-1, -1) +
            b'\x02\x38' +                                          # begin_moves
            b'\x02\x15\x02\x9c' +                                  # push current character; push its actor idx
            b'\x1d\x02' + _v(x) + _v(y) + b'\x02\x60' +            # move(idx, x, y)
            b'\x02\x3a\x11')                                       # wait_moves; end


def _v(v):
    import scenes
    return scenes.enc_varint(v)
