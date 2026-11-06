// badstore rom frames: boots with the clipcheck START/A pattern and prints PC / LR / registers at every
// "Bad memory Store" (writes to unmapped addresses), to find code writing through junk pointers.
#include <mgba/core/core.h>
#include <mgba/core/log.h>
#include <mgba/internal/arm/arm.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
static struct mCore*C; static long frame;
static void lg(struct mLogger*l,int cat,enum mLogLevel lv,const char*fmt,va_list a){
 char m[256]; vsnprintf(m,sizeof m,fmt,a);
 if(strstr(m,"Bad memory Store")){struct ARMCore*cpu=C->cpu;
  printf("f%ld %s pc=%08x lr=%08x r0=%08x r1=%08x r2=%08x r3=%08x r4=%08x r5=%08x r6=%08x r7=%08x sp=%08x\n",frame,m,
   cpu->gprs[15],cpu->gprs[14],cpu->gprs[0],cpu->gprs[1],cpu->gprs[2],cpu->gprs[3],cpu->gprs[4],cpu->gprs[5],cpu->gprs[6],cpu->gprs[7],cpu->gprs[13]);}
}
int main(int argc,char**argv){
 static struct mLogger L={.log=lg}; mLogSetDefaultLogger(&L);
 C=mCoreFind(argv[1]); C->init(C); static color_t buf[256*256]; C->setVideoBuffer(C,buf,256);
 mCoreInitConfig(C,0); C->opts.skipBios=true; mCoreLoadConfig(C); mCoreLoadFile(C,argv[1]); C->reset(C);
 long n=atol(argv[2]);
 for(frame=0;frame<n;frame++){ int ph=frame%68; int k=0;
  if(frame<60*68){ if(ph>=30&&ph<34)k=8; else if(ph>=64)k=1; } else { if(frame%34>=30)k=1; }
  C->setKeys(C,k); C->runFrame(C);}
 return 0;}
