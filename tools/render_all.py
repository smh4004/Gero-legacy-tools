import sys, os, json, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maprender import Game, GAMES
from PIL import Image
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
index = []
for g, linkfile in (('bf', 'run3/area_links_bf.json'), ('log2', 'run3/area_links_l2.json')):
    cfg = GAMES[g]; G = Game(os.path.join(root, cfg['rom']), cfg['base'], cfg['pal'])
    links = json.load(open(os.path.join(root, linkfile)))
    seen = {}
    for L in links:
        seen.setdefault(L['map'], []).append(L)
    mapsall = json.load(open(os.path.join(root, 'run3/maps_%s.json' % ('bf' if g == 'bf' else 'l2'))))
    for m in mapsall:
        Ls = seen.get(m, [])
        name = Ls[0]['name'] if Ls else '(unlinked)'
        try:
            im, info = G.render(m)
        except Exception as e:
            print('fail', g, hex(m), e); continue
        import numpy as _np
        a = _np.array(im.convert('RGB')); nz = _np.nonzero(a.sum(2))
        if len(nz[0]):
            im = im.crop((int(nz[1].min()), int(nz[0].min()), int(nz[1].max()) + 1, int(nz[0].max()) + 1))
        fn = '%s/%06X.png' % (g, m)
        im.save(os.path.join(root, 'maps_out', fn))
        index.append(dict(game=g, map='%06X' % m, name=name, areas=[(l['world'], l['area']) for l in Ls],
                          w=im.width, h=im.height, layers=info, file=fn))
    print(g, 'done', len([i for i in index if i['game'] == g]))
json.dump(index, open(os.path.join(root, 'maps_out/index.json'), 'w'), indent=0)
