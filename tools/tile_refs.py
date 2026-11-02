import json, sys, collections
good = json.load(open(sys.argv[1]))
banks = [open(f'dump/text/bank{i}.txt').read() for i in range(6)]
lens = [len(b) for b in banks] + [218]
keep = []
for b in range(7):
    S = {(h[4], h[5]) for h in good if h[3] == b}
    starts = {o for o, l in S} | {0}; ends = {o + l for o, l in S} | {lens[b]}
    ok = {(o, l) for o, l in S if (o in ends) and (o + l in starts)}
    # iterate: remove intervals overlapping a better-supported one
    srt = sorted(ok); ov = sum(1 for (o1, l1), (o2, l2) in zip(srt, srt[1:]) if o1 + l1 > o2)
    cov = len(set().union(*[set(range(o, o + l)) for o, l in ok])) if ok else 0
    print('bank', b, 'strings', len(ok), 'coverage %.1f%%' % (100 * cov / lens[b]), 'overlaps', ov)
    keep += [h for h in good if h[3] == b and (h[4], h[5]) in ok]
json.dump(keep, open(sys.argv[2], 'w'))
print('kept ref sites', len(keep))
