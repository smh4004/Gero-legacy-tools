"""Render Buu's Fury / LoG2 maps from ROM.

Map record (address M):
  +0x00 ptr (props/objects?)          +0x18..+0x24 layer headers BG0..BG3 (0 = unused)
  +0x38, +0x3C  8 KB WFZ grids (collision/attributes)
  +0x4C tile list (WFZ, u16 deltas: id[i] = id[i-1] + v + 1)
  +0x50 page table: pointers to WFZ 256-tile 8bpp pages (16 KB)
Layer header: +0 handler fn, +4/+8 parallax X/Y (0x400 = 1.0), +0xC/+0x10 X/Y origin offset ((v>>16)*64 px), +0x14 dims (byte0 = chunks wide, byte1 = chunks high),
  +0x18 chunk pointers (row-major). Chunk = WFZ 32x32 u16: bits 0-9 tile, bit 10 hflip, bit 11 vflip.
Palette: one global master palette per game, 24-bit RGB, 256 BG entries.
"""
import struct, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfz import unpack, decompress_stream
import numpy as np
from PIL import Image

GAMES = {
    'bf': dict(rom='bf.gba', base=0x08000000, pal=0x701B0),
    'log2': dict(rom='log2.gba', base=0x08800000, pal=0x3ECD1C),
}


class Game:
    def __init__(self, path, base, paloff):
        self.rom = open(path, 'rb').read()
        self.base = base
        p = self.rom[paloff:paloff + 768]
        self.pal = np.zeros((256, 4), np.uint8)
        for i in range(256):
            r, g, b = p[3 * i], p[3 * i + 1], p[3 * i + 2]
            self.pal[i] = ((r >> 3) << 3, (g >> 3) << 3, (b >> 3) << 3, 255)
        self.pal[0, 3] = 0
        self._pages = {}

    def u32(self, a): return struct.unpack_from('<I', self.rom, a)[0]
    def off(self, ptr): return ptr - self.base
    def ok(self, ptr): return self.base <= ptr < self.base + len(self.rom)

    def wfz(self, ptr):
        d, _ = unpack(self.rom, self.off(ptr))
        return d

    def tiles(self, m):
        lst = self.wfz(self.u32(m + 0x4C))
        raw = np.frombuffer(lst[:len(lst) // 2 * 2], '<u2').astype(np.int64)
        ids = np.cumsum(raw + 1) - 1
        ids[0] = raw[0]
        ids = ids if raw[0] == 0 else ids  # first entry absolute
        table = self.u32(m + 0x50)
        out = np.zeros((len(ids), 8, 8), np.uint8)
        for k, gid in enumerate(ids):
            p = int(gid) >> 8
            key = (table, p)
            if key not in self._pages:
                ptr = self.u32(self.off(table) + 4 * p)
                self._pages[key] = np.frombuffer(self.wfz(ptr), np.uint8) if self.ok(ptr) else np.zeros(16384, np.uint8)
            pg = self._pages[key]
            t = int(gid) & 0xFF
            if 64 * t + 64 <= len(pg):
                out[k] = pg[64 * t:64 * t + 64].reshape(8, 8)
        # animated tiles (frame 0): count at M+0x10, list at M+0x14; def = {u8 frames, u8 ntiles, u16 dest slot, frame ptrs}
        n = self.u32(m + 0x10); lp = self.u32(m + 0x14)
        if 0 < n < 256 and self.ok(lp):
            for k in range(n):
                d = self.u32(self.off(lp) + 4 * k)
                if not self.ok(d): continue
                d = self.off(d)
                ntiles = self.rom[d + 1]; dest = struct.unpack_from('<H', self.rom, d + 2)[0]
                fr = self.u32(d + 4)
                if not self.ok(fr): continue
                try:
                    raw, _ = decompress_stream(self.rom, self.off(fr) + 4, ntiles * 64)
                    data = np.frombuffer(raw, np.uint8)
                except (IndexError, struct.error):
                    continue
                if dest + ntiles > len(out):
                    out = np.concatenate([out, np.zeros((dest + ntiles - len(out), 8, 8), np.uint8)])
                for t in range(ntiles):
                    if 64 * t + 64 <= len(data):
                        out[dest + t] = data[64 * t:64 * t + 64].reshape(8, 8)
        return out

    def layer(self, hdr, tiles):
        h = self.off(hdr)
        dims = self.u32(h + 0x14)
        w, ht = dims & 0xFF, (dims >> 8) & 0xFF
        idx = np.zeros((ht * 32, w * 32), np.uint8)
        canvas = np.zeros((ht * 256, w * 256), np.uint8)
        for ci in range(w * ht):
            cp = self.u32(h + 0x18 + 4 * ci)
            if not self.ok(cp):
                continue
            ch = np.frombuffer(self.wfz(cp)[:2048], '<u2').reshape(32, 32)
            cy, cx = (ci // w) * 256, (ci % w) * 256
            for ty in range(32):
                for tx in range(32):
                    v = int(ch[ty, tx]); t = v & 0x3FF
                    if t == 0 or t >= len(tiles):
                        continue
                    tile = tiles[t]
                    if v & 0x400: tile = tile[:, ::-1]
                    if v & 0x800: tile = tile[::-1, :]
                    canvas[cy + ty * 8:cy + ty * 8 + 8, cx + tx * 8:cx + tx * 8 + 8] = tile
        px = (self.u32(h + 4), self.u32(h + 8))
        # +0xC / +0x10: layer origin offset, (value >> 16) * 64 px (BF West City: 0, 64, 128, 192 for BG0-3; the
        # hardware scroll differs by the same amounts). The content sits that much up/left in world space.
        ox, oy = (self.u32(h + 0xC) >> 16) * 64, (self.u32(h + 0x10) >> 16) * 64
        if ox or oy: canvas = np.roll(canvas, (-oy, -ox), axis=(0, 1))
        return canvas, px

    def render(self, m):
        tiles = self.tiles(m)
        layers = []
        for i in range(4):
            hp = self.u32(m + 0x18 + 4 * i)
            if hp and self.ok(hp):
                try: layers.append((i,) + self.layer(hp, tiles))
                except (IndexError, ValueError): pass     # special layers (BF 6:1's sky: chunk words aren't pointers)
        main = [l for l in layers if l[2] == (0x400, 0x400)] or layers
        H = max(l[1].shape[0] for l in main); W = max(l[1].shape[1] for l in main)
        out = np.zeros((H, W, 4), np.uint8); out[..., 3] = 255
        blend = self.u32(m + 4)
        bldcnt, eva, evb = blend & 0xFFFF, min((blend >> 16) & 31, 16), min((blend >> 24) & 31, 16)
        mode = (bldcnt >> 6) & 3
        for i, can, px in sorted(layers, key=lambda l: -l[0]):          # BG3 first, BG0 on top
            if px != (0x400, 0x400):                                   # parallax layer: tile it as backdrop
                reps = (-(-H // can.shape[0]), -(-W // can.shape[1]))
                can = np.tile(can, reps)[:H, :W]
            rgba = self.pal[can][:H, :W]
            sub = out[:rgba.shape[0], :rgba.shape[1]]
            mask = can[:H, :W] != 0
            if mode == 1 and bldcnt & (1 << i) and (bldcnt >> 8) & 0x0F:   # alpha-blended first target
                top = rgba[..., :3].astype(np.int32); bot = sub[..., :3].astype(np.int32)
                mix = np.minimum(255, (top * eva + bot * evb) // 16).astype(np.uint8)
                sub[..., :3][mask] = mix[mask]
            else:
                sub[mask] = rgba[mask]
        return Image.fromarray(out, 'RGBA'), [(l[0], l[1].shape[1] // 256, l[1].shape[0] // 256, l[2]) for l in layers]


if __name__ == '__main__':
    g = sys.argv[1]; cfg = GAMES[g]
    G = Game(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', cfg['rom']), cfg['base'], cfg['pal'])
    m = int(sys.argv[2], 16)
    im, info = G.render(m)
    im.save(sys.argv[3]); print(info, im.size)
