// watchrd rom state frames keys period lo hi : log Thumb loads from [lo,hi) with PC and LR
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
 long frames=atol(argv[3]); int keys=strtol(argv[4],0,0); long period=atol(argv[5]);
 uint32_t lo=strtoul(argv[6],0,16), hi=strtoul(argv[7],0,16);
 struct ARMCore*cpu=c->cpu;
 for(long f=0;f<frames;f++){
  c->setKeys(c,(period&&(f%period)<6)?keys:0);
  uint32_t fc=c->frameCounter(c);
  while(c->frameCounter(c)==fc){
   if(cpu->cpsr.t && cpu->gprs[15]-2==0x080040DC && cpu->gprs[6]==0x0877CCA4){ printf("DUMP %08X:",cpu->gprs[1]); for(int k=0;k<0x200;k++) printf("%02x",c->rawRead8(c,cpu->gprs[1]+k,-1)); printf("\n"); }
   if(cpu->cpsr.t){
    uint32_t pc=cpu->gprs[15]-2; uint16_t op=c->rawRead16(c,pc,-1); uint32_t a=0xffffffff;
    int rb=(op>>3)&7, ro=(op>>6)&7, imm=(op>>6)&31;
    if((op&0xF800)==0x7800) a=cpu->gprs[rb]+imm;            // ldrb imm
    else if((op&0xF800)==0x6800) a=cpu->gprs[rb]+imm*4;     // ldr imm
    else if((op&0xF800)==0x8800) a=cpu->gprs[rb]+imm*2;     // ldrh imm
    else if((op&0xFE00)==0x5C00||(op&0xFE00)==0x5800||(op&0xFE00)==0x5A00||(op&0xFE00)==0x5600||(op&0xFE00)==0x5E00) a=cpu->gprs[rb]+cpu->gprs[ro];
    if(a>=lo&&a<hi){ printf("F%ld pc=%08X lr=%08X addr=%08X stk",f,pc,cpu->gprs[14],a); for(int k=0;k<48;k++){uint32_t w=c->rawRead32(c,cpu->gprs[13]+4*k,-1); if((w>>24)==8) printf(" %08X",w);} printf("\n"); }
   } else {
    uint32_t pc=cpu->gprs[15]-4; uint32_t op=c->rawRead32(c,pc,-1); uint32_t a=0xffffffff;
    int rn=(op>>16)&15; uint32_t base=cpu->gprs[rn]; if(rn==15) base=pc+8;
    if((op&0x0C100000)==0x04100000){ uint32_t off; if(op&0x02000000){int rm=op&15,sh=(op>>7)&31; off=cpu->gprs[rm]<<sh;} else off=op&0xfff;
      a=(op&0x01000000)?((op&0x00800000)?base+off:base-off):base; }
    else if((op&0x0E100000)==0x08100000){ a=base; }  // ldm: first word
    else if((op&0x0E1000F0)==0x001000B0||(op&0x0E1000D0)==0x001000D0){ uint32_t off=(op&0x00400000)?(((op>>4)&0xf0)|(op&0xf)):cpu->gprs[op&15];
      a=(op&0x01000000)?((op&0x00800000)?base+off:base-off):base; }
    if((op&0x0E100000)==0x08100000){ int n=__builtin_popcount(op&0xffff); uint32_t s0=(op&0x00800000)?base:base-4*n; if(s0<hi&&s0+4*n>lo) printf("F%ld ARM-LDM pc=%08X lr=%08X addr=%08X n=%d\n",f,pc,cpu->gprs[14],s0,n); }
    else if(a>=lo&&a<hi) printf("F%ld ARM pc=%08X lr=%08X addr=%08X\n",f,pc,cpu->gprs[14],a);
   }
   c->step(c);
  }
 }
 return 0;}
