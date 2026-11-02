"""Work out which OBJ palette slots are free globally and per act (Buu's Fury base).

Protected everywhere: colours of kept portraits, HUD/dialogue-box OBJs (tools/bf_ui_obj_colors.json, from emulator dumps)
and effect actors (classes other than 0x02 NPC / 0x04 character / 0x10 boss). Global free = slots nothing uses.
Act free = slots not used by the protected set, by that act's kept actors, or by the global free list.
Writes log4/art/palette_plan.json. Needs the BF portraits (read from the clean ROM).
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))


def plan(clean_rom, acts_path, out_path):
    import portrait_backdrops as P
    u = {int(k): v for k, v in json.load(open(os.path.join(HERE, 'bf_actor_colors.json'))).items()}
    ui = set(json.load(open(os.path.join(HERE, 'bf_ui_obj_colors.json'))))
    cfg = json.load(open(acts_path)); cut = set(cfg['cut_actors'])
    ports = P.load_all(clean_rom)
    all_used = set().union(*[set(a['used']) for a in u.values()]) | set(np.unique(ports).tolist()) | ui
    global_free = [i for i in range(1, 256) if i not in all_used]
    eff = set().union(*[set(a['used']) for a in u.values() if a['cls'] not in (2, 4, 0x10)])
    base = set(np.unique(ports[cfg['keep_portraits']]).tolist()) | ui | eff | {0}
    out = {'global_free': global_free, 'base': sorted(base), 'acts': {}}
    for name, a in cfg['acts'].items():
        k = a['keep_actors']
        if isinstance(k, str):            # shorthand: "class2+[ids]" or "class2,4,16"
            classes = [int(c) for c in k.split('+')[0].replace('class', '').split(',')]
            extra = json.loads(k.split('+')[1]) if '+' in k else []
            k = [i for i, v in u.items() if v['cls'] in classes and i not in cut] + extra
        used = base | set().union(*[set(u[i]['used']) for i in k if i in u])
        free = [i for i in range(1, 256) if i not in used and i not in global_free]
        out['acts'][name] = {'free': free, 'keep_colors': sorted(used - {0}), 'worlds': a['worlds'], 'art': a['art']}
    json.dump(out, open(out_path, 'w'), indent=1)
    return out


if __name__ == '__main__':
    o = plan(open(sys.argv[1], 'rb').read(), sys.argv[2], sys.argv[3])
    print('global free', len(o['global_free']), {k: len(v['free']) for k, v in o['acts'].items()})
