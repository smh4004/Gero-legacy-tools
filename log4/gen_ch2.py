"""Chapter 2 'An Enemy Bullet': the drone's search for Squad Seven in the Northern Wastelands. Writes areas 1:68, 1:95,
1:96, 1:97, 1:100-102 into areas.json. Scenes: log4/scenes/act1_ch2.scene. usage: python3 log4/gen_ch2.py"""
import os
import areagen as G
from areagen import hexcond

SRC = {68: ('l2', '0x67542c'), 95: ('new', 68), 96: ('bf', [20, 3]), 97: ('l2', '0x66dff8'),
       100: ('l2', '0x66684c'), 101: ('l2', '0x665ed4'), 102: ('l2', '0x66c68c')}
SIZE = {68: (512, 512), 95: (512, 512), 96: (640, 256), 97: (472, 512), 100: (296, 264), 101: (304, 424), 102: (274, 230)}
NAMES = {68: 'Ambush Ridge', 95: 'Ambush Ridge (Gevo)', 96: 'Scorched Canyon', 97: 'Dry Basin', 100: 'Fuel Dump',
         101: 'Supply Yard', 102: 'Raider Cave'}
g = G.Gen(SRC, SIZE)
def l2_mask(off):                                          # collision of a LoG2 map not yet in the built ROM
    import struct, numpy as np, mapimport
    l2 = open(os.path.join(G.HERE, '..', 'log12.gba'), 'rb').read()[0x800000:]
    mp = struct.unpack_from('<I', l2, off + 0x38)[0] - 0x08800000
    return np.unpackbits(np.frombuffer(bytes(mapimport.wfz_data(l2, mp)), np.uint8), bitorder='little').reshape(-1, 256)
g._m[97] = l2_mask(0x66dff8)
FOUND = ('set', 378)
# Ambush Ridge <-> Scorched Canyon: the ridge's north road (see below) and the canyon's east edge. (The ridge's west
# exit was a corner behind rocks nobody could see - user, 2026-11-02: no hidden exits - so it is gone.)
canyon_arr = g.arrival(96, 'right', 128, 160)
east = {'rect': g.rect(96, 'right', 128, 160), 'warp': [1, 68, 106, 92], 'dir': 'right', 'face': 'up',
        'when': hexcond(('clear', 378)), '_note': 'Scorched Canyon east edge -> Ambush Ridge'}
# the canyon's east exit leads to the Ridge with Gevo once all three survivors are found (exits are read at area load)
g.doors[96] += [east, dict(east, warp=[1, 95, 106, 92], when=hexcond(FOUND), _note='Scorched Canyon -> Ambush Ridge (Gevo)')]
g.link(96, ('left', 216, 240), 97, ('right', 264, 328), NAMES)    # the canyon trail west -> the gulch's east road
g.link(96, ('up', 416, 448), 101, ('left', 264, 368), NAMES)
g.link(96, ('down', 48, 256), 100, ('down', 112, 176), NAMES)
# Dry Basin is LoG2's 3:7 gulch now (BF 20:10 was a walled basin whose exits went through the rim). Its top-right cave
# mouth is the Raider Cave; the cave's mouth (bottom) and its east ramp both lead back out to it.
gulch_arr = g.snap(97, 330, 182, 14, 'down')
cave_arr = g.arrival(102, 'down', 96, 136)
g.doors[97].append({'rect': [316, 120, 356, 160], 'warp': [1, 102] + cave_arr, 'dir': 'up', 'face': 'up',
                    'cover_ok': True, '_note': 'Dry Basin cave mouth -> Raider Cave (he walks into the dark mouth)'})
g.doors[102].append({'rect': g.rect(102, 'down', 96, 136), 'warp': [1, 97] + gulch_arr, 'dir': 'down', 'face': 'down',
                     '_note': 'Raider Cave mouth -> Dry Basin'})
g.doors[102].append({'rect': [246, 104, 274, 150], 'warp': [1, 97] + gulch_arr, 'dir': 'right', 'face': 'down',
                     '_note': 'Raider Cave east ramp -> Dry Basin'})
for d in g.doors[96]:                                      # the north trail bends east as it climbs: a wider, shorter rect
    if d['warp'][1] == 101: d['rect'] = [416, 0, 480, 60]
# The ridge's north road (user report 2026-11-02: "north blocked by electric fence, no other paths"; the west exit is a
# corner behind rocks nobody finds). LoG2's fence (layer 1 tiles 12-28 x 4-8, post feet on layer 2) is erased and its
# row opened either side of the rock pillar; the north edge is the way to the canyon.
NORTH = ('up', 104, 208)
north_arr = {a: [106, 92] for a in (68, 95)}            # left of the pillar (feet reach x+24)
for a in (68, 95):
    g.doors[a].append({'rect': [104, 0, 208, 48], 'warp': [1, 96] + canyon_arr, 'dir': 'up', 'face': 'left',
                       'cover_ok': True, '_note': 'Ambush Ridge north road -> Scorched Canyon (the west cliff overhangs it)'})
FENCE = {'erase_tiles': [{'layer': 1, 'tiles': [12, 4, 28, 8]}, {'layer': 2, 'tiles': [13, 5, 13, 7]},
                         {'layer': 2, 'tiles': [27, 5, 27, 7]}],
         'walkable': [[104, 40, 135, 63], [168, 40, 207, 63]]}

# story triggers and examine spots
g.ev(68, (128, 392, 192, 448), 'ch2_field', walk=True, when=hexcond(('clear', 313)), note='drone arrival (160,420): radio + journal')
g.ev(95, (104, 96, 248, 150), 'ch2_gevo', walk=True, when=hexcond(('clear', 311)), note='reaching Gevo (flag 311 clear)')
ya = g.arrival(101, 'left', 264, 368)
g.ev(101, (ya[0] - 8, ya[1] - 40, ya[0] + 40, ya[1] + 24), 'ch2_yard', walk=True, when=hexcond(('clear', 314)), note='raider chief taunt (flag 314)')
g.ev(100, (56, 100, 128, 132), 'cache_dump', examine='up', note='crates by the fuel tanks (items, flag 379)')
g.ev(101, (92, 196, 136, 262), 'cache_yard', examine='up', note='a Red Ribbon supply crate (items, flag 328)')

S = lambda a, x, y, r=12: g.snap(a, x, y, r)
spawns = {
    95: [dict(actor='gevo', x=168, y=104, face='down', talk='gevo_field_talk')],
    100: [dict(zip(('x', 'y'), S(100, 200, 140)), actor_id=25, face='left', talk='surv_a', _note='Pvt. Kurz (wounded)')],
    102: [dict(zip(('x', 'y'), S(102, 176, 150)), actor_id=25, face='down', talk='surv_b', _note='Cpl. Mori, the radioman')],
    101: [dict(zip(('x', 'y'), S(101, 230, 120)), actor_id=25, face='down', talk='surv_c', _note='Sgt. Halden, tied up by the raiders')],
}
E = lambda a, t, x, y, **k: dict(type=t, x=S(a, x, y, 14)[0], y=S(a, x, y, 14)[1], **k)
GUN, MERC, SNIPER, CRIM, THUG = 44, 75, 108, 15, 128
enemies = {
    68: [E(68, SNIPER, 240, 370), E(68, GUN, 120, 330), E(68, CRIM, 140, 220)],
    96: [E(96, CRIM, 300, 140), E(96, CRIM, 180, 150), E(96, GUN, 120, 100), E(96, MERC, 470, 130), E(96, SNIPER, 360, 70)],
    97: [E(97, MERC, 300, 230), E(97, CRIM, 350, 280)],
    100: [E(100, SNIPER, 100, 180), E(100, GUN, 170, 140)],
    102: [E(102, CRIM, 200, 140)],
    101: [E(101, GUN, 120, 300), E(101, MERC, 200, 330),
          dict(E(101, THUG, 160, 200), condition=0x20000 + 377, _note='raider chief (row 128): until defeated (377)')],
}
ents = []
for a in SRC:
    k, s = SRC[a]
    e = {'world': 1, 'area': a, 'template': [15, 10], 'name': 573, 'palette_act': 'act1',
         '_note': 'Chapter 2: %s (generated by log4/gen_ch2.py)' % NAMES[a], 'doors': g.doors[a]}
    if k == 'bf': e['map_from'] = s
    elif k == 'new': e['map_from'] = [1, s]
    else: e['map_log2'] = s
    if spawns.get(a): e['spawns'] = spawns[a]
    if enemies.get(a): e['enemies'] = enemies[a]
    sol = g.solid_for_top_exits(a)
    if sol and k != 'new': e['solid'] = sol
    if a == 68: e.update(FENCE)                            # 1:95 shares 1:68's (edited) map
    ents.append(e)
# 1:95 must come after 1:68 (map_from another new area)
ents.sort(key=lambda e: e['area'] == 95)
G.write(ents, set(SRC))
for a in SRC: print(a, NAMES[a], [(d.get('warp'), d['rect']) for d in g.doors[a] if 'warp' in d])
