"""Group WFZ blocks into sprite sets via the pointer tables that reference them."""
import sys, struct, pickle, json, collections
rom = open(sys.argv[1], 'rb').read(); base = int(sys.argv[2], 16)
res = pickle.load(open(sys.argv[3], 'rb'))
blk = {o + base: (o, s) for o, s, e in res if 256 <= s <= 8192}
refs = collections.defaultdict(list)   # block -> referencing offsets
for i in range(0, len(rom) - 3, 4):
    v = struct.unpack_from('<I', rom, i)[0]
    if v in blk: refs[v].append(i)
# referencing sites -> clusters of nearby sites (same table region)
sites = sorted((i, v) for v, L in refs.items() for i in L)
clusters = []; cur = []
for i, v in sites:
    if cur and i - cur[-1][0] > 64:
        clusters.append(cur); cur = []
    cur.append((i, v))
if cur: clusters.append(cur)
out = []
for c in clusters:
    bl = sorted({v for i, v in c})
    if len(bl) < 4: continue
    sizes = collections.Counter(blk[v][1] for v in bl)
    out.append(dict(start=c[0][0], end=c[-1][0], n=len(bl), sizes=dict(sizes), blocks=[blk[v][0] for v in bl]))
print('blocks', len(blk), 'referenced', len(refs), 'clusters>=4', len(out))
json.dump(out, open(sys.argv[4], 'w'))
