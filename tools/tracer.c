// tracer rom state keysmask maxsteps watchaddr
// steps CPU instruction by instruction; reports when 16-bit value at watchaddr changes
#include <mgba/core/core.h>
#include <mgba/core/serialize.h>
#include <mgba-util/vfs.h>
#include <mgba/internal/arm/arm.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char**argv){
 struct mCore*c=mCoreFind(argv[1]); c->init(c);
 static color_t buf[256*256]; c->setVideoBuffer(c,buf,256);
 mCoreInitConfig(c,0); c->opts.skipBios=true; mCoreLoadConfig(c);
 mCoreLoadFile(c,argv[1]); c->reset(c);
 struct VFile*vf=VFileOpen(argv[2],O_RDONLY); mCoreLoadStateNamed(c,vf,SAVESTATE_SAVEDATA); vf->close(vf);
 int keys=strtol(argv[3],0,0); long max=strtol(argv[4],0,0); int pcmode=argv[5][0]=='p'; uint32_t w=strtoul(argv[5]+pcmode,0,16);
 int hits=argc>6?atoi(argv[6]):1;
 struct ARMCore*cpu=c->cpu; uint32_t ring[256]; int ri=0;
 long keysteps=argc>7?strtol(argv[7],0,0):3000000; c->setKeys(c,keys);
 uint16_t last=c->rawRead16(c,w,-1);
 for(long i=0;i<max;i++){
  ring[ri++&255]=cpu->gprs[15]; if(i==keysteps)c->setKeys(c,0);
  if(pcmode){ if((cpu->gprs[15]-(cpu->cpsr.t?2:4))==w){printf("step %ld: PC hit %08X\n",i,w);for(int r=0;r<16;r++)printf(" r%d=%08X",r,cpu->gprs[r]);printf("\n");if(--hits<=0)break;} c->step(c); continue;}
  c->step(c);
  uint16_t v=c->rawRead16(c,w,-1);
  if(v!=last){
   printf("step %ld: [%08X] %04X->%04X  PC=%08X\n",i,w,last,v,cpu->gprs[15]);
   for(int r=0;r<16;r++)printf(" r%d=%08X",r,cpu->gprs[r]);printf("\n recent PCs:");
   for(int k=32;k>0;k--)printf(" %08X",ring[(ri-k)&255]);printf("\n");
   last=v; if(--hits<=0)break;
  }
 }
 return 0;}
