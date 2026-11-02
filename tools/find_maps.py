"""Find map records: struct with 4 layer-header pointers at +0x18 and tile list / page table at +0x4C/+0x50."""
import struct, sys, collections, json
rom = open(sys.argv[1], 'rb').read(); base = int(sys.argv[2], 16)   # bus base of image (0x08000000 or 0x08800000)
N = len(rom)
def u32(a): return struct.unpack_from('<I', rom, a)[0]
def isptr(v): return base <= v < base + N
flagsets = collections.Counter()
hdrs = set()
for a in range(0, N - 32, 4):
    f = u32(a)
    if (f & 1) and base <= f < base + 0x100000 and u32(a + 4) <= 0x1000 and u32(a + 8) <= 0x1000:
        d = u32(a + 20)
        w, h = (d >> 8) & 0xFF, d & 0xFF
        if 0 < w <= 64 and 0 < h <= 64 and isptr(u32(a + 24)):
            hdrs.add(a); flagsets[f] += 1
maps = []
for a in range(0, N - 0x58, 4):
    L = [u32(a + 0x18 + 4 * i) for i in range(4)]
    if isptr(u32(a)) and L[0] and isptr(L[0]) and (L[0] - base) in hdrs and isptr(u32(a + 0x4C)) and isptr(u32(a + 0x50)):
        if all(x == 0 or (isptr(x) and (x - base) in hdrs) for x in L):
            maps.append(a)
print('layer headers', len(hdrs), dict(flagsets.most_common(5)))
print('map records', len(maps), ['%X' % m for m in maps[:10]])
json.dump(maps, open(sys.argv[3], 'w'))
