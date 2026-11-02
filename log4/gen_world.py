"""Act 3 open world (user, 2026-11-02: "add the world map and flight system ... side content and Easter eggs").
Buu's Fury's Earth map (0:50) opens in Act 3 only: chapter 9's Capsule Corporation years (Age 772, flag 368 on, the
hub's airship) and chapter 10 (Age 780). Writes log4/worldmap.json (landing spots, tools/worldmap.py) and the new
destination areas 17:42-17:47 into areas.json; edits 17:18-17:20 and 17:40 (take-off partner, stone Dragon Balls).
Leaving any destination: talk to Eighteen (she stands by the landing spot) - she says "let's go" and they fly up.

Destinations (era picked when landing: Age 780 once flag 380 is set):
  West City        772: Capsule Corporation hub 17:18      780: Circus Lot ruins 17:40
  Mount Paozu      Goku's house 17:19 (Chi-Chi)           Kame House      Roshi's island 17:20
  Orange Star City 17:42 (BF 3:4, Orange Star High)       Kami's Lookout  17:43 (BF 6:1; fly up into it: hold B)
  Papaya Island    17:44 (BF 7:1, the tournament gate)    Diablo Desert   17:45 (BF 14:1, Prototype 11)
  Pilaf's Castle   17:46 (BF 13:1, the ninja garrison)    Nataday Village 17:47 (BF 15:1, the raiders)
Seven stone Dragon Balls (Kami died in Age 767, so the balls are stone - Future timeline lore): flags 411 Hercule,
415 announcer, 418 desert, 421 Pilaf's safe, 426 village elder, 427 Goku's house (the four-star ball), 428 Kame House.
All seven -> Kami's Lookout's palace door (413). Other flags: 409 first take-off, 410 OSC, 412 Lookout, 414 Papaya,
416 desert, 417 Prototype 11 destroyed, 419 castle, 420 ninja captain, 422 village, 423 raider boss.
(BF's world map itself uses flags 398-408; LoG4's world-map content starts at 409.)
usage: python3 log4/gen_world.py"""
import json, os
import areagen as G
from areagen import hexcond

W17 = 17
SRC = {42: ('bf', [3, 4]), 43: ('bf', [6, 1]), 44: ('bf', [7, 1]), 45: ('bf', [14, 1]), 46: ('bf', [13, 1]),
       47: ('bf', [15, 1])}
SIZE = {42: (320, 400), 43: (768, 768), 44: (480, 480), 45: (320, 320), 46: (320, 320), 47: (1024, 1024)}
UI = {42: 1709, 43: 1710, 44: 1711, 45: 1712, 46: 1713, 47: 1714}
NAMES = {42: 'Orange Star City', 43: "Kami's Lookout", 44: 'Papaya Island', 45: 'Diablo Desert', 46: "Pilaf's Castle",
         47: 'Nataday Village'}
g = G.Gen(SRC, SIZE, world=W17)
S = lambda a, x, y, r=12, f=None: g.snap(a, x, y, r, f)
E = lambda a, t, x, y, **k: dict(type=t, x=S(a, x, y, 14)[0], y=S(a, x, y, 14)[1], **k)

# ---------- landing spots on the map (rects from BF's own 0:50 records: name rect, landing rects)
LAND = {42: (96, 300), 43: (320, 420), 44: (300, 330), 45: (130, 236), 46: (150, 210), 47: (400, 560)}
land = {a: S(a, *LAND[a], 14, 'down') for a in LAND}
locs = [
    dict(key='west_city', bf='west_city', ui=595, rect=[1193, 1137, 1312, 1296], land=[[1137, 1137, 1208, 1256], [1193, 1113, 1312, 1296]],
         dests=[{'when': 'set:380', 'to': [W17, 40, 240, 140]}, {'to': [W17, 18, 240, 150]}]),
    dict(key='paozu', bf='east_district', ui=1715, rect=[2632, 1465, 2712, 1536], dests=[{'to': [W17, 19, 112, 120]}]),
    dict(key='kame', bf='roshi', ui=1716, rect=[2833, 1633, 2944, 1744], land=[[2873, 1673, 2904, 1696]], dests=[{'to': [W17, 20, 380, 300]}]),
    dict(key='osc', bf='hercule_city', ui=1709, rect=[2441, 1020, 2616, 1200], land=[[2441, 1065, 2568, 1200], [2553, 1097, 2616, 1160]],
         dests=[{'to': [W17, 42] + land[42]}]),
    dict(key='lookout', bf='lookout', ui=1710, rect=[593, 1025, 704, 1128], land=[[593, 1025, 704, 1128]], ascend=True,
         dests=[{'to': [W17, 43] + land[43]}]),
    dict(key='papaya', bf='papaya', ui=1711, rect=[1953, 2041, 2096, 2200], dests=[{'to': [W17, 44] + land[44]}]),
    dict(key='diablo', bf='diablo', ui=1712, rect=[1505, 985, 1648, 1144], dests=[{'to': [W17, 45] + land[45]}]),
    dict(key='pilaf', bf='pilaf', ui=1713, rect=[2249, 1521, 2360, 1624], land=[[2289, 1561, 2320, 1584]], dests=[{'to': [W17, 46] + land[46]}]),
    dict(key='nataday', bf='nataday', ui=1714, rect=[2161, 857, 2232, 928], dests=[{'to': [W17, 47] + land[47]}]),
]
json.dump({'_note': 'Act 3 world map landing spots (written by log4/gen_world.py; tools/worldmap.py)', 'locations': locs},
          open(os.path.join(G.HERE, 'worldmap.json'), 'w'), indent=1)
CENTER = {l['key']: ((l['rect'][0] + l['rect'][2]) // 2, (l['rect'][1] + l['rect'][3]) // 2) for l in locs}

# ---------- the take-off partner: Eighteen next to the landing spot (talk -> fly_<key>)
def partner(a, x, y, key): return dict(zip(('x', 'y'), S(a, x, y)), actor='player_18', face='left', talk='fly_' + key,
                                      _note='Eighteen: talk to fly (take-off to the world map)')
spawns = {
    42: [partner(42, land[42][0] + 36, land[42][1], 'osc'),
         dict(zip(('x', 'y'), S(42, 224, 296)), actor_id=129, face='left', talk='osc_hercule', _note='Hercule (BF actor 129)'),
         dict(zip(('x', 'y'), S(42, 196, 248)), actor_id=60, face='down', talk='osc_police', _note='a police officer'),
         dict(zip(('x', 'y'), S(42, 40, 300)), actor_id=92, face='right', talk='osc_girl', _note='a schoolgirl (likely BF townsgirl)')],
    43: [partner(43, land[43][0] + 40, land[43][1] + 8, 'lookout')],
    44: [partner(44, land[44][0] + 36, land[44][1] + 8, 'papaya'),
         dict(zip(('x', 'y'), S(44, 304, 108)), actor_id=9, face='left', talk='papaya_announcer',
              _note='the tournament announcer (likely BF actor 9: blond, sunglasses, suit)')],
    45: [partner(45, land[45][0] + 36, land[45][1] + 8, 'diablo')],
    46: [partner(46, land[46][0] + 36, land[46][1] + 8, 'pilaf')],
    47: [partner(47, land[47][0] + 36, land[47][1] + 8, 'nataday'),
         dict(zip(('x', 'y'), S(47, 360, 440)), actor_id=183, face='down', talk='nat_elder', _note='the village elder (BF old woman)'),
         dict(zip(('x', 'y'), S(47, 520, 470)), actor_id=151, face='left', talk='nat_farmer', _note='a farmer')],
}
# ---------- examine spots and arrival scenes
g.ev(42, (land[42][0] - 16, land[42][1] - 24, land[42][0] + 40, land[42][1] + 24), 'osc_arrive', walk=True,
     when=hexcond(('clear', 410)), note='first landing (410)')
g.ev(42, (140, 116, 188, 148), 'osc_school', examine='up', note='Orange Star High: chained doors')
g.ev(43, (land[43][0] - 16, land[43][1] - 24, land[43][0] + 40, land[43][1] + 24), 'lookout_arrive', walk=True,
     when=hexcond(('clear', 412)), note='first landing (412)')
g.ev(43, (280, 252, 360, 308), 'lookout_door', examine='up', note="the palace door: Kami's altar (all seven balls: 413)")
g.ev(44, (land[44][0] - 16, land[44][1] - 24, land[44][0] + 40, land[44][1] + 24), 'papaya_arrive', walk=True,
     when=hexcond(('clear', 414)), note='first landing (414)')
g.ev(44, (176, 40, 264, 104), 'papaya_gate', examine='up', note='the tournament gate')
g.ev(45, (land[45][0] - 16, land[45][1] - 24, land[45][0] + 40, land[45][1] + 24), 'diablo_arrive', walk=True,
     when=hexcond(('clear', 416)), note='first landing (416)')
g.ev(45, (176, 84, 232, 120), 'diablo_ball', examine='up', note="Prototype 11's post: the stone ball (418, after 417)")
g.ev(46, (land[46][0] - 16, land[46][1] - 24, land[46][0] + 40, land[46][1] + 24), 'pilaf_arrive', walk=True,
     when=hexcond(('clear', 419)), note='first landing (419)')
g.ev(46, (128, 48, 176, 104), 'pilaf_safe', examine='up', note="the rubble of Pilaf's castle: his old safe (421)")
g.ev(47, (land[47][0] - 16, land[47][1] - 24, land[47][0] + 40, land[47][1] + 24), 'nat_arrive', walk=True,
     when=hexcond(('clear', 422)), note='first landing (422)')

# walking off the edge of an open area (a path that runs off the map) also takes off - every such path, so none of
# them looks like an exit that goes nowhere (user rule 2026-11-02)
EDGES = {42: [[0, 240, 16, 384]], 44: [[140, 0, 300, 16], [416, 464, 448, 480]], 45: [[208, 0, 272, 16]],
         46: [[80, 0, 160, 16], [104, 304, 208, 320]], 47: [[248, 0, 304, 16], [288, 696, 512, 712]]}
KEY = {42: 'osc', 43: 'lookout', 44: 'papaya', 45: 'diablo', 46: 'pilaf', 47: 'nataday'}
for a, rects in EDGES.items():
    for r in rects: g.ev(a, r, 'fly_' + KEY[a], walk=True, note='map edge: take off')
PROTO11, RAIDER, RAID_BOSS, NINJA, NINJA2, CAPTAIN, MONK1, MONK2, MONK3 = 19, 71, 131, 78, 101, 82, 123, 124, 125
enemies = {
    44: [E(44, MONK1, 120, 200), E(44, MONK2, 380, 200), E(44, MONK3, 250, 380)],
    45: [dict(E(45, PROTO11, 228, 104), character=76, condition=0x20000 + 417,
              _note='Prototype 11 (row 19, BF Death Machine, char 76): until destroyed (417)'),
         E(45, RAIDER, 80, 120), E(45, RAIDER, 260, 250)],
    46: [E(46, NINJA, 100, 150), E(46, NINJA2, 230, 140), E(46, NINJA, 160, 260),
         dict(E(46, CAPTAIN, 150, 100), character=202, condition=0x20000 + 420,
              _note='the ninja captain (row 82, char 202): until defeated (420)')],
    47: [E(47, RAIDER, 300, 380), E(47, RAIDER, 600, 420), E(47, RAIDER, 480, 300),
         dict(E(47, RAID_BOSS, 520, 360), character=272, condition=0x20000 + 423,
              _note='Butcher, the raider boss (row 131, char 272): until defeated (423)')],
}
ents = []
for a in sorted(SRC):
    e = {'world': W17, 'area': a, 'template': [15, 10], 'name': UI[a], 'palette_act': 'act3', 'map_from': SRC[a][1],
         '_note': 'Act 3 world-map destination: %s (generated by log4/gen_world.py)' % NAMES[a], 'doors': g.doors[a]}
    if spawns.get(a): e['spawns'] = spawns[a]
    if enemies.get(a): e['enemies'] = enemies[a]
    ents.append(e)
G.write(ents, set(SRC), world=W17)

# ---------- existing Act 3 areas: take-off partner and the stone balls
p = os.path.join(G.HERE, 'areas.json'); cfg = json.load(open(p))
EXTRA = {   # area: (spawns to add, doors to add) - tagged _world so reruns replace them
    19: ([dict(x=208, y=104, actor='player_18', face='left', talk='fly_paozu', _world=1)],
         [{'rect': [32, 88, 72, 120], 'event': 'paozu_ball', 'examine': 'up', '_world': 1,
           '_note': "the little shrine by the window: Grandpa Gohan's four-star ball (427)"},
          {'rect': [96, 140, 128, 160], 'event': 'fly_paozu', 'fn2': '0x080077DF', '_world': 1,
           '_note': 'the front door: out and up (take-off; the doorway is the only way out)'}]),
    20: ([dict(x=420, y=300, actor='player_18', face='left', talk='fly_kame', _world=1)],
         [{'rect': [300, 180, 356, 212], 'event': 'kame_ball', 'examine': 'up', '_world': 1,
           '_note': 'the wreck of Kame House (428)'}]),
    40: ([dict(x=272, y=140, actor='player_18', face='left', talk='fly_west', _world=1)],
         [{'rect': r, 'event': 'fly_west', 'fn2': '0x080077DF', '_world': 1, '_note': 'map edge: take off'}
          for r in ([16, 0, 128, 16], [352, 0, 464, 16])]),
    18: ([], [{'rect': [0, 368, 16, 432], 'event': 'fly_hub', 'fn2': '0x080077DF', '_world': 1,
               '_note': 'the street off the west edge: take off'}]),
}
for v in cfg['new_areas']:
    if v['world'] == W17 and v['area'] in EXTRA:
        sp, dr = EXTRA[v['area']]
        v['spawns'] = [s for s in v.get('spawns', []) if not s.get('_world')] + sp
        if not v['spawns']: del v['spawns']
        v['doors'] = [d for d in v.get('doors', []) if not d.get('_world')] + dr
    if (v['world'], v['area']) == (W17, 18):            # the hub: airship and hangar now take off for the world map
        for d in v['doors']:
            if d.get('event') in ('ch9_fly_paozu', 'fly_hub'): d['event'] = 'fly_hub'; d['_note'] = "Bulma's airship -> world map"
            if d.get('event') in ('ch9_fly_kame', 'fly_hub_jet'): d['event'] = 'fly_hub_jet'; d['_note'] = 'the hangar jets -> world map'
json.dump(cfg, open(p, 'w'), indent=1)
# ---------- take-off lists (talk to Eighteen; the hub's airship and jets): fly up over this place
FLY = {'osc': 'osc', 'lookout': 'lookout', 'papaya': 'papaya', 'diablo': 'diablo', 'pilaf': 'pilaf', 'nataday': 'nataday',
       'paozu': 'paozu', 'kame': 'kame', 'west': 'west_city', 'hub': 'west_city', 'hub_jet': 'west_city'}
LINE = {'hub': ("narrate Bulma's old airship. Seventeen doesn't bother with it: they fly faster on their own.",),
        'hub_jet': ('narrate The hangar is full of jets nobody will ever fly again. Seventeen walks past them.',)}
out = ['# GENERATED by log4/gen_world.py - take-off to the world map. First take-off (flag 409) explains the map.']
for k, loc in FLY.items():
    x, y = CENTER[loc]
    out += ['list fly_' + k] + list(LINE.get(k, ())) + [
        'if_flag 409 fly_%s_go' % k, 'set_flag 409',
        'say android18 Let\'s go. Somewhere that isn\'t here.',
        'narrate (World map: steer with the + pad. Hold A to drop down and land on a place. Hold B to climb - Kami\'s Lookout floats high above the wasteland.)',
        'narrate (Wherever you land, talk to Eighteen, or walk off the edge of the area, to fly on.)',
        'label fly_%s_go' % k,
        'do call 120 20; call 118 0 50 0 %d %d; call 121 20' % (x, y), 'stop']
open(os.path.join(G.HERE, 'scenes', 'act3_world_fly.scene'), 'w').write('\n'.join(out) + '\n')
for a in SRC: print(a, NAMES[a], 'land', land[a], [s.get('actor', s.get('actor_id')) for s in spawns.get(a, [])])
print('map centres', CENTER)
