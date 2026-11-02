"""Chapter 5 'Siblings' (Act 2, West City, world 4 = act2 palette): the twins' West City grows a district.
West City (4:1, BF) hub exits:
  west road     -> 4:40 Circus Lot (BF Musuka Circus 3:14): a fairground street the Red Fangs gang has taken over
  south road    -> 4:41 Riverside (BF 2:9, arriving over its bridge) -> 4:42 Docks (BF 2:8, island with a barn and a
                   dome house) -> barn door -> 4:43 Old Warehouse (LoG2 2:50): the twins' hideout, now the Red Fangs'
                   den; boss Big Ox (enemy row 12, BF Bruiser sprite)
  Z-Mart door   -> 4:44 Z-Mart (LoG2 Big Mouth deli 4:42): the clerk's stolen delivery (side job)
  city hall door-> 4:45 West City Museum (LoG2 West City Antiquities 4:43): the curator's stolen medal (side job), the
                   Red Ribbon exhibit
Flags: 293 vendor told them about the Red Fangs, 294 Big Ox beaten, 295 stash recovered (needed for ch5_end), 296 medal
returned, 297 riverside cache, 298 delivery returned, 299 docks cache, 387 curator asked, 388 clerk asked, 389 den intro.
usage: python3 log4/gen_ch5.py (needs a built log4/out/LoG4.gba that already has 4:43-4:45 for their floor masks)"""
import json, os
import areagen as G
from areagen import hexcond

W4 = 4
SRC = {1: ('bf', [4, 1]), 40: ('bf', [3, 14]), 41: ('bf', [2, 9]), 42: ('bf', [2, 8]),
       43: ('l2', '0x677374'), 44: ('l2', '0x63ed74'), 45: ('l2', '0x63d5b0')}
SIZE = {1: (1072, 912), 40: (480, 240), 41: (480, 320), 42: (480, 480), 43: (368, 301), 44: (472, 320), 45: (696, 288)}
NAMES = {1: 'West City', 40: 'Circus Lot', 41: 'Riverside', 42: 'Docks', 43: 'Old Warehouse', 44: 'Z-Mart',
         45: 'West City Museum'}
UI_NAME = {40: 1701, 41: 1702, 42: 1703, 43: 1704, 44: 1705, 45: 1706}    # log4/text/ui.txt
g = G.Gen(SRC, SIZE, world=W4)
arr = g.link(1, ('left', 312, 424), 40, ('right', 112, 184), NAMES)
for d in g.doors[40]:
    if d['warp'][1] == 1: d['warp'][2:] = [48, 320]      # clear of the park's tree tops
g.link(1, ('down', 368, 472), 41, ('up', 224, 288), NAMES)
g.link(41, ('right', 176, 272), 42, ('down', 232, 280), NAMES)   # the docks' pier (was the west edge behind the trees)
S = lambda a, x, y, r=12, f=None: g.snap(a, x, y, r, f)


def door(a, rect, dirn, b, at, face, note):
    g.doors[a].append({'rect': rect, 'warp': [W4, b] + at, 'dir': dirn, 'face': face, '_note': note})


# building doors (BF West City's own doors are graphics only; the LoG2 interiors' built-in doors are emptied by
# tools/areas.py and replaced by these)
door(1, [260, 268, 292, 312], 'up', 44, S(44, 192, 272, 14, 'up'), 'up', 'West City -> Z-Mart')
door(44, [176, 300, 224, 320], 'down', 1, S(1, 268, 316, 14, 'down'), 'down', 'Z-Mart -> West City')
door(1, [400, 112, 448, 140], 'up', 45, S(45, 400, 232, 14, 'up'), 'up', 'West City -> museum (city hall doors)')
g.doors[1][-1]['cover_ok'] = True         # the city hall's door is drawn in its wall: walking in, the wall covers the feet
door(45, [392, 272, 440, 288], 'down', 1, S(1, 416, 140, 14, 'down'), 'down', 'museum -> West City')
door(42, [120, 186, 168, 208], 'up', 43, S(43, 140, 104, 14, 'down'), 'down', 'Docks -> Old Warehouse (barn door)')
door(43, [120, 64, 192, 92], 'up', 42, S(42, 136, 214, 14, 'down'), 'down', 'Old Warehouse -> Docks')
g.doors[43][-1]['cover_ok'] = True        # the doorway is cut into the top wall: the wall covers the player going in

# events
den = S(43, 140, 104)
g.ev(43, (den[0] - 24, den[1] + 8, den[0] + 56, den[1] + 40), 'ch5_den', walk=True,
     when=hexcond(('clear', 389)), note='first steps into the den: Big Ox (389)')
g.ev(42, (256, 186, 288, 208), 'docks_dome', note='dome house door: locked; the lookout cache (299)')
g.ev(41, (40, 120, 72, 152), 'cache_river', examine='left', note='a boat under the trees (297)')
g.ev(45, (448, 112, 512, 140), 'museum_exhibit', examine='up', note='the Red Ribbon exhibit case')

spawns = {
    40: [dict(zip(('x', 'y'), S(40, 360, 40)), actor_id=172, face='down', talk='ch5_vendor', _note='street vendor')],
    44: [dict(zip(('x', 'y'), S(44, 300, 120)), actor_id=171, face='down', talk='zmart_clerk', _note='Z-Mart clerk')],
    45: [dict(zip(('x', 'y'), S(45, 300, 220)), actor_id=195, face='down', talk='museum_curator', _note='curator')],
}
# the stash is an examine spot on the crates in the den's south-east corner, not an NPC
g.ev(43, (304, 224, 360, 252), 'ch5_stash', examine='down', note='the twins\' stash behind the crates (295)')

E = lambda a, t, x, y, **k: dict(type=t, x=S(a, x, y, 14)[0], y=S(a, x, y, 14)[1], **k)
PUNK, BRUTE, OX = 97, 36, 12      # rows: Criminal (char 235), Goon (char 122), Bruiser (char 39)
enemies = {
    40: [E(40, PUNK, 120, 40), E(40, PUNK, 250, 140), E(40, BRUTE, 420, 60)],
    41: [E(41, PUNK, 200, 160), E(41, PUNK, 320, 220), E(41, BRUTE, 120, 220)],
    42: [E(42, PUNK, 100, 320), E(42, PUNK, 300, 260), E(42, BRUTE, 360, 360), E(42, PUNK, 220, 120)],
    43: [E(43, PUNK, 60, 200), E(43, BRUTE, 230, 170),
         dict(E(43, OX, 180, 250), character=39, condition=0x20000 + 294, _note='Big Ox (row 12): until beaten (294)')],
}
ents = []
for a in SRC:
    if a == 1: continue
    k, s = SRC[a]
    e = {'world': W4, 'area': a, 'template': [15, 10], 'name': UI_NAME[a], 'palette_act': 'act2',
         '_note': 'Chapter 5: %s (generated by log4/gen_ch5.py)' % NAMES[a], 'doors': g.doors[a]}
    if k == 'bf': e['map_from'] = s
    else: e['map_log2'] = s
    if spawns.get(a): e['spawns'] = spawns[a]
    if enemies.get(a): e['enemies'] = enemies[a]
    sol = g.solid_for_top_exits(a)
    if sol and k == 'bf': e['solid'] = sol
    if a == 45: e['shade_ok'] = [[360, 200, 460, 280]]   # LoG2's opaque window-shadow layer over the museum floor
    ents.append(e)
G.write(ents, set(SRC) - {1}, world=W4)
# West City's new exits go on its in-place entry (doors_append), replacing earlier generated ones
p = os.path.join(G.HERE, 'areas.json'); cfg = json.load(open(p))
for v in cfg['areas']:
    if (v['world'], v['area']) == (4, 1):
        v['doors_append'] = [d for d in v['doors_append'] if not d.get('_gen5')] + [dict(d, _gen5=1) for d in g.doors[1]]
json.dump(cfg, open(p, 'w'), indent=1)
for a in SRC: print(a, NAMES[a], [(d.get('warp'), d['rect']) for d in g.doors[a] if 'warp' in d], spawns.get(a))
