"""Build Legacy of Goku 4 from a clean Buu's Fury (USA) ROM.

usage: python3 build.py <clean Buu's Fury .gba> [--log2 <LoG I&II cart .gba>] [--proto <BF Prototype D .gba>] [--skip-art] [--shoot] [--debug]
outputs out/LoG4.gba and out/LoG4.bps (apply the .bps to a clean ROM with Flips, Floating IPS, etc.)

Every build ends with tools/clipcheck.py: each NPC spawn and door arrival in the edited areas is played in the emulator
and checked for clipping (characters inside props/walls or hidden by the map) and every door is walked through.
If anything fails, no patch is written (out/clipcheck/ has the report and annotated frames). There is no switch to skip it.
"""
import hashlib, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import glob, json, outfit, text_tool, bps, artclean, portraits, worldpal, sprites, areas, scenes, stats, logo, scouter, title, doors

CLEAN_SHA1 = 'f1c4b07554d2a3b1ad2f325307051e775ce68087'
COMBO_SHA1 = 'f02d179accbeb9b68bcaef8720eb0ae426dde6ee'
PROTO_SHA1 = '4594e2d524e2d77cdf0e58ae7512e1052cc5bc02'   # Buu's Fury Prototype D (DBZ3_cart27.GBA): Super Android 13   # Legacy of Goku I & II (USA) combo cart; LoG2 = second 8 MB


def main(clean_path):
    clean = open(clean_path, 'rb').read()
    if hashlib.sha1(clean).hexdigest() != CLEAN_SHA1:
        sys.exit("That isn't the expected clean Buu's Fury (USA) ROM (SHA-1 mismatch).")
    art = os.path.join(HERE, 'art')
    if os.path.exists(os.path.join(art, 'specs.json')) and '--skip-art' not in sys.argv:
        import palette_plan
        plan = palette_plan.plan(clean, os.path.join(HERE, 'acts.json'), os.path.join(art, 'palette_plan.json'))
        print('-- palette plan: %d global free slots; per act %s' % (len(plan['global_free']), {k: len(v['free']) for k, v in plan['acts'].items()}))
        for f in os.listdir(os.path.join(art, 'clean')):                 # re-plan colours from the whole art set
            if f.startswith('palette_alloc'): os.remove(os.path.join(art, 'clean', f))
        print('-- art: cleanup + quantize')
        reps = artclean.main(os.path.join(art, 'specs.json'), os.path.join(art, 'raw'), os.path.join(art, 'clean'))
        done = [r for r in reps if 'colors' in r]
        print('-- art: %d of %d assets processed (ROM insertion of sprites comes with the animation-table work)' % (len(done), len(reps)))
    shoot = '--shoot' in sys.argv        # footage ROM for trailers: adds log4/shoot/*.scene (party/warp lists), no checks
    debug = '--debug' in sys.argv        # debug ROM: New Game opens the debug room (log4/gen_debug.py), no checks
    scene_list = [scenes.parse(f) for f in sorted(glob.glob(os.path.join(HERE, 'scenes', '*.scene'))
                                                 + (glob.glob(os.path.join(HERE, 'shoot', '*.scene')) if shoot else [])
                                                 + (glob.glob(os.path.join(HERE, 'debug', '*.scene')) if debug else []))]
    if debug:                            # the opening: after its setup step, go to the debug room unless flag 429 is set
        import tempfile
        op = next(sc for sc in scene_list if sc['replace'] == 0x780550)
        assert op['steps'][0] == ('keep', 1)
        with tempfile.NamedTemporaryFile('w', suffix='.scene', delete=False) as t:
            t.write('\n'.join(json.load(open(os.path.join(HERE, 'debug', 'boot.json')))) + '\n')
        boot = scenes.parse(t.name)['steps']; os.remove(t.name)
        op['name'] = 'act1_opening'
        op['steps'] = op['steps'][:1] + [('ifflag', 429, 'dbg_skip', True)] + boot + [('goto', '__end__'), ('label', 'dbg_skip')] + op['steps'][1:]
        # debug options (gen_debug.py APPLY): appended to each chapter's start list, before a trailing stop
        def parse_lines(lines):
            with tempfile.NamedTemporaryFile('w', suffix='.scene', delete=False) as t:
                t.write('\n'.join(lines) + '\n')
            st = scenes.parse(t.name)['steps']; os.remove(t.name); return st
        for lname, lines in json.load(open(os.path.join(HERE, 'debug', 'apply.json'))).items():
            add = parse_lines(lines)
            if lname == 'act1_opening':
                op['steps'] += add; continue
            sc = next(sc for sc in scene_list if any(n == lname for n, _ in sc.get('lists') or []))
            cuts = sc['lists'] + [(None, len(sc['steps']))]
            k = next(i for i, (n, _) in enumerate(cuts) if n == lname)
            end = cuts[k + 1][1]
            at = end - 1 if sc['steps'][end - 1] == ('goto', '__end__') else end
            sc['steps'][at:at] = add
            sc['lists'] = [(n, i + len(add) if i > at or (i == at and j > k) else i) for j, (n, i) in enumerate(sc['lists'])]
    import goals
    goals.write_ui(os.path.join(HERE, 'goals.json'), os.path.join(HERE, 'text'))   # journal goal strings (UI 1600+)
    out = bytearray(text_tool.build(clean_path, os.path.join(HERE, 'text'), extra=scenes.texts(scene_list)))
    n = portraits.apply_palette(out, os.path.join(art, 'clean', 'palette_alloc.json'))
    log2 = None
    if '--log2' in sys.argv:
        combo = open(sys.argv[sys.argv.index('--log2') + 1], 'rb').read()
        if hashlib.sha1(combo).hexdigest() != COMBO_SHA1:
            sys.exit("That isn't the expected Legacy of Goku I & II (USA) cart (SHA-1 mismatch).")
        log2 = combo[0x800000:]
    else:
        print('-- note: no --log2 <LoG I&II cart> given, so LoG2 assets (portraits) are skipped')
    proto = None
    if '--proto' in sys.argv:
        proto = open(sys.argv[sys.argv.index('--proto') + 1], 'rb').read()
        if hashlib.sha1(proto).hexdigest() != PROTO_SHA1:
            sys.exit("That isn't the expected Buu's Fury Prototype D (SHA-1 mismatch).")
    else:
        print('-- note: no --proto <Prototype D> given, so Super Android 13 is skipped')
    sp, used = portraits.insert(out, os.path.join(art, 'specs.json'), os.path.join(art, 'clean'),
                                os.path.join(art, 'speakers.json'), clean, log2,
                                os.path.join(art, 'portrait_imports.json'), os.path.join(art, 'clean', 'palette_alloc.json'), proto)
    print('-- palette: %d new OBJ colours; portraits: %d new speakers (ids %d-%d), %d bytes'
          % (n, len(sp), min(sp.values()) if sp else 0, max(sp.values()) if sp else 0, used))
    regs = artclean.registries(os.path.join(art, 'clean'))
    colour_ctx = lambda act: (regs.get(act, regs[None]).usable(), artclean.palette_rgb(regs.get(act, regs[None])))
    areas_cfg = json.load(open(os.path.join(HERE, 'areas.json')))
    if debug: areas_cfg['new_areas'] += json.load(open(os.path.join(HERE, 'debug', 'areas_debug.json')))['new_areas']
    door_plan = doors.plan(areas_cfg, log2)                   # animated doors: panel actors + triggers (tools/doors.py)
    actors_cfg = json.load(open(os.path.join(HERE, 'actors.json'))); actors_cfg.update(door_plan['actors'])
    ids, end = sprites.build_actors(out, actors_cfg, os.path.join(art, 'clean'), 0xC00000, log2, colour_ctx, proto)
    json.dump(ids, open(os.path.join(art, 'actor_ids.json'), 'w'), indent=1)
    assert end <= areas.SPILL[0] if hasattr(areas, 'SPILL') else True, 'actors ran into the map spill region (tools/areas.py SPILL)'
    print('-- actors: table moved to 0xC00000, %d new actors %s, %d bytes' % (len(ids), ids, end - 0xC00000))
    end3 = scenes.compile_all(out, scene_list, text_tool.EXTRA_REFS, scenes.aliases(os.path.join(art, 'speakers.json')), 0xF00000, ids)
    if not shoot: json.dump({k: v for k, v in scenes.NAMED.items()}, open(os.path.join(HERE, 'out', 'named_lists_debug.json' if debug else 'named_lists.json'), 'w'), indent=1)
    print('-- scenes: %d compiled (%d bytes), named lists %s' % (len(scene_list), end3 - 0xF00000, sorted(scenes.NAMED)))
    # areas (imported maps + area structs) at 0x880000-0xA00000 (text 0x800000+, portraits 0xA00000+); 0xE00000 was
    # outgrown in chapter 5 (2026-11-02)
    assert all(b in (0, 0xFF) for b in out[0x87F000:0x880000]), 'text ran into the area region'
    done, area_worlds, end2 = areas.apply(out, areas_cfg, log2, ids, 0x880000, talk=scenes.NAMED, doors=door_plan)
    assert end2 < 0xA00000, 'areas overflow into the portraits'
    print('-- doors: %d animated door(s) in %s' % (sum(len(v) for v in door_plan['areas'].values()),
                                                   sorted('%d:%d' % k for k in door_plan['areas'])))
    print('-- areas: %s edited, %d bytes of imported maps (+%d in the spill region)' % (done, end2 - 0x880000, areas.SPILL[0] - 0xDF8000))
    plan_path = os.path.join(art, 'palette_plan.json')
    if area_worlds and os.path.exists(plan_path):                 # areas.json can assign worlds to an act's palette
        plan = json.load(open(plan_path))
        for act, ws in area_worlds.items():
            plan['acts'][act]['worlds'] = sorted(set(plan['acts'][act]['worlds']) | ws)
        json.dump(plan, open(plan_path, 'w'), indent=1)
    pals = portraits.act_palettes(os.path.join(art, 'clean'), plan_path, os.path.join(HERE, 'palettes.json'))
    for w, mos in areas.NIGHT.items():                            # areas.json new areas with "night": true
        for mo in mos: pals.setdefault(str(w), {}).setdefault('bg', {}).update(worldpal.night_bg(out, mo))
    assert end3 < 0xF40000
    end4 = logo.apply(out, "GERO'S LEGACY", "GERO'S", 0xF40000)
    print('-- title logo: subtitle rebuilt (%d bytes)' % (end4 - 0xF40000))
    assert end4 < 0xF50000
    end5 = scouter.apply(out, 0xF50000)
    print('-- scouter map: Gero\'s Lab schematic (%d bytes)' % (end5 - 0xF50000))
    assert end5 < 0xF60000
    end6, ncol = title.apply(out, os.path.join(art, 'raw', 'U1_title.png'), 0xF60000)
    print('-- title screen: U1_title inserted (%d new colours, %d bytes)' % (ncol, end6 - 0xF60000))
    end6 = title.legal_apply(out, end6)
    print('-- legal screen: first line reads "%s"' % title.LEGAL_TITLE)
    assert end6 < 0xF7E000
    st = json.load(open(os.path.join(HERE, 'stats.json')))
    print('-- stats: %s' % stats.apply(out, {k: v for k, v in st.items() if k != 'enemies'}))
    print('-- enemy rows: %s' % stats.apply_enemies(out, st.get('enemies', {}), 0xF7F000))
    import levelup                                                # BF's move-upgrade checks on level-up (crash fix)
    print('-- level-up: %d attack-level checks neutralised' % levelup.apply(out))
    import saga                                                   # save-slot chapter name from LoG4's chapter flags
    print('-- save-slot chapter names: script at 0xAFFF00 (%d bytes)' % (saga.apply(out, 0xAFFF00) - 0xAFFF00))
    import tabname                                                # party tabs read 17 / 18 after the conversion
    end_t = tabname.apply(out, os.path.join(HERE, 'asm', 'tabname.s'), 0xAFFF80)
    assert end_t <= 0xB00000
    print('-- party tab names: hook (%d bytes)' % (end_t - 0xAFFF80))
    import worldmap                                               # Act 3 world map landing spots (log4/worldmap.json)
    end_w, nloc = worldmap.apply(out, os.path.join(HERE, 'worldmap.json'), 0xAF0000)
    assert end_w <= 0xAFFF00
    print('-- world map: %d places (%d bytes)' % (nloc, end_w - 0xAF0000))
    end7 = outfit.apply(out, os.path.join(HERE, 'asm', 'outfit.s'), 0xF7E000, json.load(open(os.path.join(HERE, 'forms.json'))), ids)
    print('-- outfit swap: skill 18 hooks + forms (%d bytes)' % (end7 - 0xF7E000))
    # journal goals table: moved 2026-11-03 from 0xF7EA00 (1.5 KB, outgrown at 65 goals) to 0xF3C000, after the ki effects
    end_g = goals.apply(out, os.path.join(HERE, 'goals.json'), 0xF3C000)
    print('-- journal goals: %d (%d bytes)' % (len(json.load(open(os.path.join(HERE, 'goals.json')))['goals']), end_g - 0xF3C000))
    assert end_g <= 0xF40000
    import kifx                                                   # 17 blue / 18 pink ki blasts, Final Flash wave, Power Blitz
    assert end3 < 0xF38000, 'scenes ran into the ki effect copy at 0xF38000'
    end8 = kifx.apply(out, 0xF38000)
    assert end8 <= 0xF3C000, 'ki effects ran into the journal goals at 0xF3C000'
    print('-- ki effects: 17 blue / 18 pink blast copies + hook, Final Flash coloured energy wave, Power Blitz / Infinity Bullet (%d bytes)' % (end8 - 0xF38000))
    import framegrd, frameaudit                                   # sprite frame guard + audit (2026-11-03: garbled
    endf, _ = framegrd.apply(out, 0xF3B800, int(os.environ['LOG4_GUARD_COUNTER'], 16) if shoot and os.environ.get('LOG4_GUARD_COUNTER') else None)                       # shadows when an enemy played a slot its sprite lacks)
    assert end8 <= 0xF3B800 and endf <= 0xF3C000
    na, nf, fprob = frameaudit.audit(out)
    assert not fprob, 'sprite frames that do not fit their actor: %s (tools/frameaudit.py)' % fprob[:5]
    print('-- sprite frame guard at 0x0800F38C (%d bytes); audit: %d actors, %d frames fit their OBJ VRAM' % (endf - 0xF3B800, na, nf))
    import kiregen                                                # ki recharge: drone and converted androids
    end7 = kiregen.apply(out, os.path.join(HERE, 'asm', 'kiregen.s'), 0xF7E800)
    print('-- ki recharge hook (%d bytes)' % (end7 - 0xF7E800))
    assert end7 <= 0xF7F000
    if log2 is not None:                                          # startup music: LoG2's "Era of Darkness" (song 7)
        import music
        end8 = music.port(out, log2, 7, 0xF80000)
        assert end8 <= 0x1000000
        print('-- startup music: LoG2 "Era of Darkness" in BF song slot 45 (%d bytes)' % (end8 - 0xF80000))
        # the music plan (log4/music.json): more LoG2 songs sharing those samples, at 0xB00000 (free: 0xA32000-0xC00000)
        end9, nmus = music.apply_plan(out, log2, json.load(open(os.path.join(HERE, 'music.json'))), 0xB00000, areas.entry_any)
        assert end9 < 0xC00000
        print('-- music plan: %d areas set, LoG2 songs %d bytes' % (nmus, end9 - 0xB00000))
    assert end7 < 0xF7F000
    nw = worldpal.apply(out, os.path.join(HERE, 'asm', 'fadepal.bin'), pals)
    print('-- per-world palettes: hook installed, %d world(s) with their own palette' % nw)
    out = bytes(out)
    # future stages (stats, maps, sprites, scripts) plug in here
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    rom_path = os.path.join(HERE, 'out', 'LoG4.gba')
    if shoot:                            # never a release: no clip check, no patch
        open(os.path.join(HERE, 'out', 'LoG4_shoot.gba'), 'wb').write(out)
        json.dump({k: v for k, v in scenes.NAMED.items()}, open(os.path.join(HERE, 'out', 'named_lists_shoot.json'), 'w'), indent=1)
        print('shoot ROM written (not a release build)'); return
    if debug:                            # never a release: no clip check (its boot expects the real opening)
        dbg = os.path.join(HERE, 'out', 'LoG4_debug.gba'); open(dbg, 'wb').write(out)
        patch = bps.make(clean, out, meta=b'Legacy of Goku 4 DEBUG ROM (personal ROM hack of DBZ: Buu\'s Fury USA)')
        assert bps.apply(clean, patch) == out, 'patch round-trip failed'
        open(os.path.join(HERE, 'out', 'LoG4_debug.bps'), 'wb').write(patch)
        print('DEBUG ROM %s  sha1 %s, patch %d bytes (verified)' % (dbg, hashlib.sha1(out).hexdigest(), len(patch))); return
    open(rom_path, 'wb').write(out)
    stale = os.path.join(HERE, 'out', 'LoG4.bps')
    if os.path.exists(stale): os.remove(stale)
    tools = os.path.join(HERE, '..', 'tools')
    harness = os.path.join(tools, 'harness')
    if not os.path.exists(harness):
        import subprocess
        subprocess.run(['gcc', '-O2', os.path.join(tools, 'harness.c'), '-o', harness, '-lmgba', '-lpng'], check=True)
    import subprocess
    print('-- clipcheck: playing every placement and door in the emulator ...')
    rc = subprocess.run([sys.executable, os.path.join(tools, 'clipcheck.py'), rom_path, '--areas',
                         os.path.join(HERE, 'areas.json'), '--out', os.path.join(HERE, 'out', 'clipcheck'),
                         '--harness', harness]).returncode
    if rc != 0:
        sys.exit('BUILD FAILED: clipping/door check failed - no patch written. See log4/out/clipcheck/report.txt '
                 'and the FAIL_*.png frames.')
    patch = bps.make(clean, out, meta=b'Legacy of Goku 4 (personal ROM hack of DBZ: Buu\'s Fury USA)')
    assert bps.apply(clean, patch) == out, 'patch round-trip failed'
    open(os.path.join(HERE, 'out', 'LoG4.bps'), 'wb').write(patch)
    # the walkthrough (GUIDE.md) is generated from this build: regenerate it and report anything it no longer covers
    g = subprocess.run([sys.executable, os.path.join(tools, 'guide.py')], capture_output=True, text=True)
    print(g.stdout.strip() or g.stderr.strip())
    if g.returncode: print('WARNING: GUIDE.md is out of date with the game - update log4/guide/walkthrough.md')
    print('ROM   %s  sha1 %s' % (rom_path, hashlib.sha1(out).hexdigest()))
    print('patch %d bytes (verified)' % len(patch))


if __name__ == '__main__':
    main(sys.argv[1])
