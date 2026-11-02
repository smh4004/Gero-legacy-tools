import sys,struct,re,signal
sys.path.insert(0,'/home/claude/rom/tools')
from wfz import decompress_stream
rom=open(sys.argv[1],'rb').read()
res=[]
o=0
while o<len(rom)-8:
    t,s=struct.unpack_from('<II',rom,o)
    if t in (1,2) and 0x20<=s<=0x100000:
        try:
            out,end=decompress_stream(rom,o+8,s)
            if len(out)==s:
                res.append((o,s,end))
                o=(end+3)&~3; continue
        except (IndexError,struct.error): pass
    o+=4
import pickle; pickle.dump(res,open(sys.argv[2],'wb'))
print(len(res),'blocks', sum(r[2]-r[0] for r in res),'compressed bytes', sum(r[1] for r in res),'raw bytes')
