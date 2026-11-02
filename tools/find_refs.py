"""Enumerate dialogue references (event steps: u16 id, u8 type=5, u8 speaker, u32 packed ref)."""
import struct, sys, json, collections
rom = open(sys.argv[1], 'rb').read()
banks = [open(f'dump/text/bank{i}.txt').read() for i in range(6)]
import importlib.util
sys.path.insert(0, '/home/claude/rom/tools')
from wfz import unpack
b6, _ = unpack(rom, 0x7B5AA0); banks.append(b6.decode('utf-16-le'))
lens = [len(b) for b in banks]
hits = []
for p in range(0, len(rom) - 8):
    if rom[p + 2] != 5:
        continue
    sid = struct.unpack_from('<H', rom, p)[0]
    v = struct.unpack_from('<I', rom, p + 4)[0]
    b, o, l = v & 63, (v >> 6) & 0x7FFF, v >> 21
    if b < 7 and l > 0 and o + l <= lens[b] and sid < 2000:
        hits.append((p, sid, rom[p + 3], b, o, l))
# keep hits whose step chain looks real: neighbor step id-1 or id+1 nearby within 64 bytes
ids = collections.defaultdict(list)
for h in hits: ids[h[0] // 4096].append(h)
def chained(h):
    p, sid = h[0], h[1]
    for q in range(p + 3, p + 80):
        if q + 3 < len(rom) and struct.unpack_from('<H', rom, q)[0] == sid + 1 and rom[q + 2] in (0, 1, 2, 3, 4, 5, 6, 7, 8): return True
    for q in range(max(0, p - 80), p - 2):
        if struct.unpack_from('<H', rom, q)[0] == sid - 1 and rom[q + 2] in (0, 1, 2, 3, 4, 5, 6, 7, 8): return True
    return False
good = [h for h in hits if chained(h)]
# coverage check per bank
for b in range(7):
    iv = sorted({(h[4], h[5]) for h in good if h[3] == b})
    cov = sum(l for o, l in iv); ov = sum(1 for (o1, l1), (o2, l2) in zip(iv, iv[1:]) if o1 + l1 > o2)
    print('bank', b, 'unique strings', len(iv), 'chars covered %.1f%%' % (100 * cov / lens[b]), 'overlaps', ov)
print('raw hits', len(hits), 'chained', len(good))
json.dump(good, open(sys.argv[2], 'w'))
