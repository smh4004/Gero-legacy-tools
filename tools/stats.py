"""Starting stats for playable characters (BF table at ROM 0x6FDA4C, 18-byte records)."""
import struct
TABLE, SIZE = 0x6FDA4C, 18


def apply(rom, cfg):
    done = []
    for k, s in cfg.items():
        if k.startswith('_'): continue
        r = TABLE + SIZE * int(k)
        struct.pack_into('<HHHBBBB', rom, r, s['level'], s['hp'], s['ep'], s['str'], s['pow'], s['end'], s['spd'])
        done.append(s.get('name', k))
    return done


# Enemy stats (decomp: gEnemyStats 0x08711274, 150 x 28 bytes, row = enemy type): +0 exp, +4 hp, +8 id08 (kept),
# +0xC level+50, +0xD str, +0xE pow, +0xF end, +0x10 phys_taken, +0x11 ki_taken (128 = 100%), +0x14 on_defeat handler,
# +0x18 death script (bytecode run on defeat; BF uses it for item drops). Unused rows (no spawns in BF: 13, 14, 30, 31,
# 34) can be repurposed for LoG4 enemies.
ENEMY_TABLE, ENEMY_SIZE = 0x711274, 28
ON_DEFEAT = {'normal': 0x08708920, 'boss': 0x080716F4}


def apply_enemies(rom, cfg, at):
    """cfg: {row: {name, exp, hp, level, str, pow, end, phys_taken, ki_taken, on_defeat, death}}; death = assembler text
    (scenes.assemble). Scripts go at `at`. Returns names."""
    import scenes
    done = []
    for k, e in cfg.items():
        if k.startswith('_'): continue
        r = ENEMY_TABLE + ENEMY_SIZE * int(k)
        struct.pack_into('<II', rom, r, e['exp'], e['hp'])
        struct.pack_into('<BBBBBB', rom, r + 0xC, e['level'], e['str'], e['pow'], e['end'],
                         e.get('phys_taken', 128), e.get('ki_taken', 128))
        struct.pack_into('<I', rom, r + 0x14, ON_DEFEAT[e.get('on_defeat', 'normal')])
        if 'ai' in e: struct.pack_into('<I', rom, r + 8, e['ai'])   # +8 = behaviour class (likely): 0x8A fighter (BF row 21)
        script = 0
        if e.get('death'):
            code = (bytes.fromhex(e['death'][4:]) if e['death'].startswith('hex ') else scenes.assemble(e['death'], {})) + b'\x11'
            assert set(rom[at:at + len(code)]) <= {0, 0xFF}, 'enemy script space not free'
            rom[at:at + len(code)] = code; script = 0x08000000 + at; at = (at + len(code) + 3) & ~3
        if e.get('death') or e.get('drops') is False:     # else keep BF's own death script = its item drops
            struct.pack_into('<I', rom, r + 0x18, script)   # (run_event 497; zeroed for every tuned row before 2026-11-02)
        done.append(e.get('name', k))
    return done
