// scriptlog rom state frames [keys keyframes] -> logs script entries + opcodes
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
 long frames=atol(argv[3]); int keys=argc>4?strtol(argv[4],0,0):0; long period=argc>5?atol(argv[5]):0; int verbose=argc>6;
 struct ARMCore*cpu=c->cpu; long ops=0;
 for(long f=0;f<frames;f++){
  c->setKeys(c,(period&&(f%period)<6)?keys:0);
  uint32_t fc=c->frameCounter(c);
  while(c->frameCounter(c)==fc){
   uint32_t pc=cpu->gprs[15]-(cpu->cpsr.t?2:4);
   if(pc==0x08004038) printf("F%ld ENTER ctx=%08X script=%08X r2=%08X lr=%08X\n",f,cpu->gprs[0],cpu->gprs[1],cpu->gprs[2],cpu->gprs[14]);
   else if(pc==0x08003CBE||pc==0x08003CD4){uint32_t sp=c->rawRead32(c,cpu->gprs[0],-1);uint32_t a=c->rawRead32(c,cpu->gprs[1],-1);printf("  %s %02X sp=%d [",pc==0x08003CBE?"CALL":"SET ",c->rawRead8(c,a,-1),sp);for(int k=(int)sp-1;k>=0&&k>=(int)sp-6;k--)printf(" %d",(int32_t)c->rawRead32(c,cpu->gprs[0]+4+4*k,-1));printf(" ]\n");}
   else if(verbose&&pc==0x08004066){uint32_t a=cpu->gprs[1]; printf("  %08X op %02X\n",a,c->rawRead8(c,a,-1)); ops++;}
   c->step(c);
  }
 }
 fprintf(stderr,"ops %ld\n",ops); return 0;}
