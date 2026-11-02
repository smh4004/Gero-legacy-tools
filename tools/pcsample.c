#include <mgba/core/core.h>
#include <mgba/core/serialize.h>
#include <mgba-util/vfs.h>
#include <mgba/internal/arm/arm.h>
#include <stdio.h>
#include <stdlib.h>
// pcsample rom state steps : histogram of PCs (rounded to 0x40) over N instructions after loading a state
int main(int argc,char**argv){
 struct mCore*c=mCoreFind(argv[1]); c->init(c);
 mCoreInitConfig(c,0); c->opts.skipBios=true; mCoreLoadConfig(c);
 mCoreLoadFile(c,argv[1]); c->reset(c);
 struct VFile*vf=VFileOpen(argv[2],O_RDONLY); mCoreLoadStateNamed(c,vf,SAVESTATE_SAVEDATA); vf->close(vf);
 long n=strtol(argv[3],0,0); static uint32_t pcs[4096]; static long cnt[4096]; int m=0;
 struct ARMCore*cpu=c->cpu;
 for(long i=0;i<n;i++){ uint32_t pc=(cpu->gprs[15])&~0x3f; int k; for(k=0;k<m;k++)if(pcs[k]==pc)break; if(k==m&&m<4096){pcs[m++]=pc;} if(k<4096)cnt[k]++; c->step(c);}
 for(int k=0;k<m;k++) if(cnt[k]*200>n) printf("%08X %ld\n",pcs[k],cnt[k]);
 return 0;}
