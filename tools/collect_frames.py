import sys, struct, pickle, json
rom = open(sys.argv[1], 'rb').read(); base = int(sys.argv[2], 16)
res = pickle.load(open(sys.argv[3], 'rb'))
blk = {o + base: o for o, s, e in res if 128 <= s <= 16384}
def u32(a): return struct.unpack_from('<I', rom, a)[0]
fr = {}
for p in range(4, len(rom) - 3, 4):
    v = u32(p)
    if v in blk:
        a = u32(p - 4); a0 = a & 0xFFFF; a1 = a >> 16
        if a0 & 0x2000 and (a0 >> 14) != 3 and (a0 & 0x1CFF) == 0 and (a1 & 0x3FFF) == 0:
            fr.setdefault(blk[v], a)
banks = [dict(recs=[])]
out = sorted(fr.items())
json.dump(out, open(sys.argv[4], 'w'))
print('frames', len(out))
