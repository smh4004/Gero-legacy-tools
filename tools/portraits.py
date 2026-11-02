"""Portrait + palette build stage for LoG4 (Buu's Fury base).

- Writes the OBJ palette slots claimed by the art pipeline (log4/art/clean/palette_alloc.json) into the master
  palette (ROM 0x701B0, 24-bit, OBJ half = entries 256-511).
- Composes every cleaned portrait frame (56x56) into a 64x64 framed portrait (frame + synthesised backdrop),
  stores it uncompressed (WFZ type 0) in free space, and moves the speaker->portrait table to free space with
  room for new speakers. New speaker ids are written to log4/art/speakers.json (one id per portrait frame), for
  use in dialogue event steps (type 5: [u8 speaker][u32 text ref]).
Verified in the emulator: a stored portrait shows in a real dialogue box with correct colours.
"""
import json, os, struct, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portrait_backdrops as P

PAL, OBJ = 0x701B0, 256
OLD_COUNT = P.FIRST + P.COUNT                 # 163 speaker slots in the original table
FREE = 0xA00000                               # portrait area (text uses 0x800000+)


def act_palettes(clean_dir, plan_path, manual_path):
    """Per-world OBJ overrides: each act's palette_alloc_<act>.json applied to the act's worlds, plus manual entries."""
    out = json.load(open(manual_path)) if os.path.exists(manual_path) else {}
    if os.path.exists(plan_path):
        for name, a in json.load(open(plan_path))['acts'].items():
            ap = os.path.join(clean_dir, 'palette_alloc_%s.json' % name)
            if not os.path.exists(ap): continue
            ov = {k: v['rgb'] for k, v in json.load(open(ap))['assigned'].items()}
            for w in a['worlds']:
                out.setdefault(str(w), {}).setdefault('obj', {}).update(ov)
    return out


OBJ555 = 0x5652C                   # BF's OBJ palette as RGB555 (verified 256/256 = the PAL triples)


def apply_palette(rom, alloc_path):
    reg = json.load(open(alloc_path))['assigned'] if os.path.exists(alloc_path) else {}
    for k, v in reg.items():
        o = PAL + (OBJ + int(k)) * 3; rom[o:o + 3] = bytes(v['rgb'])
        # the menus (status screen, inventory...) reload the OBJ palette from BF's RGB555 copy at OBJ555 (16 code
        # references); without this the new colours fall back to BF's there (green blotches on the status portraits)
        r, g, b = v['rgb']; struct.pack_into('<H', rom, OBJ555 + 2 * int(k), (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10)
    return len(reg)


L2_TABLE, L2_PAL, L2_BASE = 0x3ECB6C, 0x3ECD1C, 0x08800000


def log2_imports(log2_rom, imports_path, reg_path, const, frame):
    """Re-frame LoG2 portraits for BF: window [4:60] mapped to BF OBJ colours (CIE94), BF frame on top."""
    import artclean as A
    from wfz import decompress_stream
    want = {k: v for k, v in json.load(open(imports_path)).items() if not k.startswith('_')}
    pl2 = np.frombuffer(log2_rom[L2_PAL + 768:L2_PAL + 1536], np.uint8).reshape(256, 3).astype(np.int64)
    reg = A.registries(os.path.dirname(reg_path))[None]       # portraits can show in any act: global colours only
    pal = A.palette_rgb(reg); usable = reg.usable()
    ulab = A.srgb_to_lab(pal[usable]); out = []
    for name, k in want.items():
        o = struct.unpack_from('<I', log2_rom, L2_TABLE + 4 * k)[0] - L2_BASE
        t, sz = struct.unpack_from('<II', log2_rom, o)
        d = log2_rom[o + 8:o + 8 + 4096] if t == 0 else bytes(decompress_stream(log2_rom, o + 8, 4096)[0])
        win = np.frombuffer(d, np.uint8).reshape(64, 64)[4:60, 4:60]
        j = A.de94(A.srgb_to_lab(pl2[win.ravel()])[:, None], ulab[None]).argmin(1)
        img = frame.copy(); img[4:60, 4:60] = np.array(usable)[j].reshape(56, 56); img[const] = frame[const]
        out.append((name, img))
    return out


PROTO_TABLE = 0x6E39C4             # Prototype D portrait table (163 entries, same layout as retail 0x6F393C)


def proto_imports(proto_rom, spec_path, reg_path, const, frame, clean_rom):
    """Prototype D portraits (cut characters, e.g. Androids 13/14/15). Same palette as retail; the window is still
    mapped onto this build's global colours (CIE94 nearest, identity for colours no act repaints)."""
    import artclean as A
    from wfz import decompress_stream
    want = {k: v for k, v in json.load(open(spec_path)).items() if not k.startswith('_')}
    src = np.frombuffer(clean_rom[PAL + 768:PAL + 1536], np.uint8).reshape(256, 3).astype(np.int64)
    reg = A.registries(os.path.dirname(reg_path))[None]
    pal = A.palette_rgb(reg); usable = reg.usable(); ulab = A.srgb_to_lab(pal[usable]); out = []
    for name, k in want.items():
        o = struct.unpack_from('<I', proto_rom, PROTO_TABLE + 4 * k)[0] - 0x08000000
        t = struct.unpack_from('<I', proto_rom, o)[0]
        d = proto_rom[o + 8:o + 8 + 4096] if t == 0 else bytes(decompress_stream(proto_rom, o + 8, 4096)[0])
        win = np.frombuffer(d, np.uint8).reshape(64, 64)[4:60, 4:60]
        j = A.de94(A.srgb_to_lab(src[win.ravel()])[:, None], ulab[None]).argmin(1)
        img = frame.copy(); img[4:60, 4:60] = np.array(usable)[j].reshape(56, 56); img[const] = frame[const]
        out.append((name, img))
    return out


def log2_sprite_portraits(log2_rom, spec_path, reg_path, const, bds):
    """Portraits made from a LoG2 sprite frame (for characters with no drawn portrait, e.g. the combat drone):
    the frame's body (rows above `rows`) is cropped, scaled up by the largest whole factor that fits 52x52,
    mapped to BF OBJ colours and centred on a backdrop. spec: {name: {record, anim, dir, frame, rows, backdrop}}."""
    import artclean as A
    from wfz import decompress_stream
    want = {k: v for k, v in json.load(open(spec_path)).items() if not k.startswith('_')}
    pl2 = np.frombuffer(log2_rom[L2_PAL + 768:L2_PAL + 1536], np.uint8).reshape(256, 3).astype(np.int64)
    reg = A.registries(os.path.dirname(reg_path))[None]
    pal = A.palette_rgb(reg); usable = reg.usable(); ulab = A.srgb_to_lab(pal[usable]); out = []
    for name, s in want.items():
        rec = int(s['record'], 16); u = lambda o: struct.unpack_from('<I', log2_rom, o)[0]
        r = u(rec + 0x4C + 16 * s.get('anim', 0) + 4 * s.get('dir', 0)) - L2_BASE + 12 * s.get('frame', 0)
        x, y, w, h = struct.unpack_from('<bbBB', log2_rom, r); tp = u(r + 8) - L2_BASE
        t, sz = struct.unpack_from('<II', log2_rom, tp)
        d = log2_rom[tp + 8:tp + 8 + sz] if t == 0 else bytes(decompress_stream(log2_rom, tp + 8, sz)[0])
        a = np.frombuffer(d[:w * h], np.uint8); img = np.zeros((h, w), np.uint8)
        for ti in range((w // 8) * (h // 8)):
            tx, ty = ti % (w // 8), ti // (w // 8); img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8] = a[ti * 64:ti * 64 + 64].reshape(8, 8)
        img = img[:s.get('rows', h)]
        ys, xs = np.nonzero(img); img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        k = max(1, min(52 // img.shape[0], 52 // img.shape[1]))
        big = np.kron(img, np.ones((k, k), np.uint8))
        m = big != 0; face = np.zeros(big.shape, np.uint8)
        j = A.de94(A.srgb_to_lab(pl2[big[m]])[:, None], ulab[None]).argmin(1)
        face[m] = np.array(usable)[j]
        bd = bds[s.get('backdrop', 'blue')]
        port = bd.copy(); fh, fw = face.shape; y0, x0 = 4 + (56 - fh) // 2, 4 + (56 - fw) // 2
        sub = port[y0:y0 + fh, x0:x0 + fw]; sub[face != 0] = face[face != 0]; port[const] = bd[const]
        out.append((name, port))
    return out


def insert(rom, specs_path, clean_dir, out_json, clean_rom, log2_rom=None, imports_path=None, reg_path=None, proto_rom=None):
    specs = [s for s in json.load(open(specs_path)) if s.get('kind') == 'portrait']
    const, bds = P.frame_and_backdrops(clean_rom)
    imgs = []
    for s in specs:
        n = 0
        while os.path.exists(os.path.join(clean_dir, '%s_%02d.png' % (s['id'], n))):
            f = np.array(Image.open(os.path.join(clean_dir, '%s_%02d.png' % (s['id'], n))))
            imgs.append(('%s_%02d' % (s['id'], n), P.compose(f, bds[s.get('backdrop', 'cyan')], const))); n += 1
    if log2_rom is not None and imports_path and os.path.exists(imports_path):
        imgs += log2_imports(log2_rom, imports_path, reg_path, const, bds['cyan'])
        sprite_spec = os.path.join(os.path.dirname(imports_path), 'portrait_sprites.json')
        if os.path.exists(sprite_spec):
            imgs += log2_sprite_portraits(log2_rom, sprite_spec, reg_path, const, bds)
    proto_spec = os.path.join(os.path.dirname(specs_path), 'proto_portraits.json')
    if proto_rom is not None and os.path.exists(proto_spec):           # appended last: earlier speaker ids keep their numbers
        imgs += proto_imports(proto_rom, proto_spec, reg_path, const, bds['cyan'], clean_rom)
    if len(rom) < 0x1000000: rom.extend(b'\xff' * (0x1000000 - len(rom)))
    total = OLD_COUNT + len(imgs)
    assert total <= 256, 'speaker ids are one byte'
    table = list(struct.unpack_from('<%dI' % OLD_COUNT, rom, P.TABLE))
    cur = FREE + 4 * 256                      # table first (room for all 256 ids), then the portraits
    speakers = {}
    for name, img in imgs:
        rom[cur:cur + 8] = struct.pack('<II', 0, 4096); rom[cur + 8:cur + 8 + 4096] = img.astype(np.uint8).tobytes()
        speakers[name] = len(table); table.append(0x08000000 + cur); cur += 4104
    ov_path = os.path.join(os.path.dirname(out_json), '..', 'portrait_overrides.json')
    if os.path.exists(ov_path):                         # existing speaker slots shown with one of our portraits
        for slot, name in json.load(open(ov_path)).items():
            if not slot.startswith('_') and name in speakers: table[int(slot)] = table[speakers[name]]
    table += [0] * (256 - len(table))
    rom[FREE:FREE + 1024] = struct.pack('<256I', *table)
    struct.pack_into('<I', rom, P.LITERAL, 0x08000000 + FREE)   # code at 0x08012118 reads table[speaker]
    json.dump(speakers, open(out_json, 'w'), indent=1)
    return speakers, cur - FREE
