import sys, struct, json, os, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import decompress_stream
import numpy as np
from PIL import Image, ImageDraw
SZ = {0: [(8,8),(16,16),(32,32),(64,64)], 1: [(16,8),(32,8),(32,16),(64,32)], 2: [(8,16),(8,32),(16,32),(32,64)]}
GAMES = {'bf': ('bf.gba', 0x701B0, 'run3/frames_bf.json'), 'log2': ('log2.gba', 0x3ECD1C, 'run3/frames_l2.json')}
REFS = [
 ('android17_log2', 'log2', 0x1E0D00, 0x1E6A00), ('android18_log2', 'log2', 0x1E6B00, 0x1EA000),
 ('dr_gero_android20_log2', 'log2', 0x1F4600, 0x203100), ('imperfect_cell_log2', 'log2', 0x20F228, 0x242C00),
 ('rr_military_robot_log2', 'log2', 0x2584C4, 0x267D00), ('rr_humanoid_robot_log2', 'log2', 0x26ABA0, 0x26F400),
 ('rr_drone_log2', 'log2', 0x2E9680, 0x2EB900), ('helmet_soldiers_log2', 'log2', 0x275AA4, 0x279200),
 ('soldiers_gunmen_bf', 'bf', 0x613F38, 0x616B00), ('tank_bf', 'bf', 0x62AA4C, 0x62FE00), ('gun_turrets_bf', 'bf', 0x5AEFC0, 0x5B0C00),
 ('scientist_log2', 'log2', 0x3286E8, 0x32AF00), ('future_trunks_jacket_log2', 'log2', 0x37FAB4, 0x386F00),
 ('gohan_adult_bf', 'bf', 0x4C63E0, 0x4D0000), ('tien_log2', 'log2', 0x3306B8, 0x336600),
 ('piccolo_bf', 'bf', 0x5ED828, 0x5F57F0), ('vegeta_log2', 'log2', 0x387C54, 0x38DC20), ('krillin_bf', 'bf', 0x63CB88, 0x63E6B0),
]
out = sys.argv[1]
cache = {}
for name, g, lo, hi in REFS:
    path, paloff, fj = GAMES[g]
    if g not in cache:
        rom = open(path, 'rb').read(); frames = json.load(open(fj))
        pal = np.zeros((256, 4), np.uint8); p = rom[paloff + 768: paloff + 1536]
        for i in range(256): pal[i] = [p[3*i] & 0xF8, p[3*i+1] & 0xF8, p[3*i+2] & 0xF8, 255]
        pal[0, 3] = 0
        cache[g] = (rom, frames, pal)
    rom, frames, pal = cache[g]
    sel = [(o, a) for o, a in frames if lo <= o < hi]
    imgs = []
    for o, a in sel:
        a0, a1 = a & 0xFFFF, a >> 16; w, h = SZ[(a0 >> 14) & 3][(a1 >> 14) & 3]
        s = struct.unpack_from('<I', rom, o + 4)[0]
        try: data, _ = decompress_stream(rom, o + 8, s)
        except Exception: continue
        tw = w // 8; n = min(len(data) // 64, tw * (h // 8)); idx = np.zeros((h, w), np.uint8)
        for t in range(n):
            idx[(t // tw) * 8:(t // tw) * 8 + 8, (t % tw) * 8:(t % tw) * 8 + 8] = np.frombuffer(data[64*t:64*t+64], np.uint8).reshape(8, 8)
        if (idx != 0).sum() < 20: continue
        imgs.append(Image.fromarray(pal[idx], 'RGBA'))
    cols = 12; cw = 70; ch = 140
    W = Image.new('RGBA', (cols * cw, max(1, (len(imgs) + cols - 1) // cols) * ch), (0, 0, 0, 0))
    for k, im in enumerate(imgs):
        im2 = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
        W.paste(im2, ((k % cols) * cw + (cw - im2.width) // 2, (k // cols) * ch + (ch - im2.height)), im2)
    W.save(os.path.join(out, name + '.png'))
    print('%-28s %3d frames' % (name, len(imgs)))
