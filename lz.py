def lz77(g,o,maxsz=0x40000):
    if g[o]!=0x10: return None
    size=g[o+1]|g[o+2]<<8|g[o+3]<<16
    if size==0 or size>maxsz: return None
    out=bytearray(); p=o+4
    try:
        while len(out)<size:
            f=g[p];p+=1
            for b in range(8):
                if len(out)>=size:break
                if f&0x80:
                    a=g[p];c=g[p+1];p+=2
                    n=(a>>4)+3; disp=((a&0xF)<<8|c)+1
                    if disp>len(out): return None
                    for _ in range(n): out.append(out[-disp])
                else: out.append(g[p]);p+=1
                f<<=1
    except IndexError: return None
    return bytes(out[:size]),p-o
def huff(g,o,maxsz=0x40000):
    h=g[o]
    if h not in (0x28,0x24): return None
    bits=h&0xF; size=g[o+1]|g[o+2]<<8|g[o+3]<<16
    if size==0 or size>maxsz: return None
    ts=(g[o+4]+1)*2; tree=o+5; data=o+4+ts
    if data%4: return None
    out=bytearray(); cur=0; nb=0; pos=tree; 
    p=data
    try:
        while len(out)<size:
            word=int.from_bytes(g[p:p+4],'little'); p+=4
            for i in range(32):
                bit=(word>>31)&1; word<<=1
                node=g[pos]; off=node&0x3F
                nxt=(pos&~1)+off*2+2
                isleaf = (node&0x80) if bit==0 else (node&0x40)
                pos=nxt+bit
                if isleaf:
                    cur|=g[pos]<<nb; nb+=bits; pos=tree
                    if nb==8:
                        if cur>255: return None
                        out.append(cur); cur=0; nb=0
                    if len(out)>=size: break
                if pos>=len(g): return None
    except IndexError: return None
    return bytes(out), p-o
