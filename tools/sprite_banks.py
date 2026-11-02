import sys, struct, pickle, json, collections
rom = open(sys.argv[1], 'rb').read(); base = int(sys.argv[2], 16)
res = pickle.load(open(sys.argv[3], 'rb'))
blk = {o + base: (o, s) for o, s, e in res if 128 <= s <= 16384}
def u32(a): return struct.unpack_from('<I', rom, a)[0]
recs = set()
for p in range(0, len(rom) - 20, 4):
    if u32(p + 4) in blk and 1 <= u32(p + 8) <= 8:
        recs.add(p)
runs = []; cur = []
for p in sorted(recs):
    if cur and p - cur[-1] not in (20,):
        if p - cur[-1] > 20: runs.append(cur); cur = []
    cur.append(p)
if cur: runs.append(cur)
# merge runs separated by small gaps (<=64 bytes) - likely same bank with other data between
banks = []
for r in runs:
    if banks and r[0] - banks[-1][-1] <= 0x40: banks[-1] += r
    else: banks.append(list(r))
out = []
for b in banks:
    sizes = collections.Counter(blk[u32(p + 4)][1] for p in b)
    out.append(dict(start=b[0], end=b[-1] + 20, frames=len(b), sizes=dict(sizes), recs=b))
print('frame records', len(recs), 'banks', len(out), 'banks>=20 frames', sum(1 for o in out if o['frames'] >= 20))
json.dump(out, open(sys.argv[4], 'w'))
