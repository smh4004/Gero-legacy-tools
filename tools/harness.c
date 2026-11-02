// Headless GBA harness: run ROM with scripted input, dump screenshots + memory
// usage: harness rom.gba script.txt outdir
// script lines: "<frames> <keys>" keys like A,B,START,UP... or "shot name" or "dump name addr len" or "save name"/"load name"
// or "rec name n keys": like "<n> <keys>" but appends every frame (raw rgb24 240x160) to name.mkv (via ffmpeg; consecutive rec lines with the same name make one clip) and the sound
// (s16 stereo 48000 Hz) to name.pcm, for video; "arec name n keys" records the sound only. Sound is drained every frame either way.
// or "pshot name": the same frame as name_full.png (all layers), name_bg.png (backgrounds) and name_obj.png (sprites) + its OAM / OBJ VRAM
// or "w8 addr value" (bus write, hex), or "lshot name mask": run one frame with only the layers in mask drawn (bit0-3 BG0-3, bit4 OBJ), save it, re-enable all
#include <mgba/core/core.h>
#include <mgba/core/serialize.h>
#include <mgba/gba/core.h>
#include <mgba-util/vfs.h>
#include <mgba/internal/gba/input.h>
#include <mgba/core/blip_buf.h>
#include <png.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static const char* names[]={"A","B","SELECT","START","RIGHT","LEFT","UP","DOWN","R","L"};
static int keymask(const char*s){int m=0;char b[256];strncpy(b,s,255);b[255]=0;for(char*t=strtok(b,",+");t;t=strtok(0,",+"))for(int i=0;i<10;i++)if(!strcmp(t,names[i]))m|=1<<i;return m;}
static FILE*recv=0,*reca=0; static char recname[128]; static int16_t abuf[8192];
static void frame_done(struct mCore*c,color_t*buf){
 blip_t*l=c->getAudioChannel(c,0),*r=c->getAudioChannel(c,1);
 int n; while((n=blip_samples_avail(l))>0){if(n>2048)n=2048; blip_read_samples(l,abuf,n,1); blip_read_samples(r,abuf+1,n,1); if(reca)fwrite(abuf,4,n,reca);}
 if(recv){unsigned char row[240*3];for(int y=0;y<160;y++){for(int x=0;x<240;x++){uint32_t c2=buf[y*256+x];row[x*3]=c2&0xFF;row[x*3+1]=(c2>>8)&0xFF;row[x*3+2]=(c2>>16)&0xFF;}fwrite(row,1,sizeof row,recv);}}}
static void shot(struct mCore*c,color_t*buf,const char*path);
/* draw one frame with only the layers in mask (DISPCNT bits 8-12) and save it */
static void lframe(struct mCore*c,color_t*buf,const char*path,unsigned mask){
 while(c->rawRead16(c,0x04000006,-1)!=160)c->step(c);       /* finish the current frame */
 while(c->rawRead16(c,0x04000006,-1)!=0)c->step(c);         /* vblank over: the game has written DISPCNT */
 uint16_t o=c->rawRead16(c,0x04000000,-1); c->busWrite16(c,0x04000000,(o&~0x1F00)|((mask&0x1F)<<8));
 while(c->rawRead16(c,0x04000006,-1)!=160)c->step(c);       /* draw it */
 c->busWrite16(c,0x04000000,o); shot(c,buf,path);}
static void shot(struct mCore*c,color_t*buf,const char*path){unsigned w,h;c->desiredVideoDimensions(c,&w,&h);FILE*f=fopen(path,"wb");png_structp p=png_create_write_struct(PNG_LIBPNG_VER_STRING,0,0,0);png_infop i=png_create_info_struct(p);png_init_io(p,f);png_set_IHDR(p,i,w,h,8,PNG_COLOR_TYPE_RGB,0,0,0);png_write_info(p,i);unsigned char row[256*3];for(unsigned y=0;y<h;y++){for(unsigned x=0;x<w;x++){uint32_t c2=buf[y*256+x];row[x*3]=c2&0xFF;row[x*3+1]=(c2>>8)&0xFF;row[x*3+2]=(c2>>16)&0xFF;}png_write_row(p,row);}png_write_end(p,0);png_destroy_write_struct(&p,&i);fclose(f);}
int main(int argc,char**argv){
 struct mCore*c=mCoreFind(argv[1]); if(!c)return 1; c->init(c);
 color_t*buf=calloc(256*256,sizeof(color_t)); c->setVideoBuffer(c,buf,256);
 mCoreInitConfig(c,0); c->opts.skipBios=true; mCoreConfigSetDefaultIntValue(&c->config,"volume",0x100); mCoreLoadConfig(c);
 mCoreLoadFile(c,argv[1]); c->reset(c);
 c->setAudioBufferSize(c,4096); blip_set_rates(c->getAudioChannel(c,0),c->frequency(c),48000); blip_set_rates(c->getAudioChannel(c,1),c->frequency(c),48000);
 FILE*s=fopen(argv[2],"r"); char line[512]; char path[600]; long frame=0;
 while(fgets(line,sizeof line,s)){
  char a[128]="",b2[128]=""; unsigned addr=0,len=0; int n;
  if(line[0]=='#'||line[0]=='\n')continue;
  if(sscanf(line,"lshot %127s %x",a,&addr)==2){snprintf(path,600,"%s/%s.png",argv[3],a);lframe(c,buf,path,addr);frame++;continue;}
  if(sscanf(line,"pshot %127s",a)==1){ /* the SAME frame twice: all layers (a_full.png) and sprites only (a_obj.png), plus
     OAM (a_oam.bin) and OBJ VRAM (a_vram.bin) of that frame: save state, draw, restore, draw again */
   char ss[600]; snprintf(ss,600,"%s/_pshot.ss",argv[3]);
   struct VFile*vf=VFileOpen(ss,O_CREAT|O_TRUNC|O_RDWR);mCoreSaveStateNamed(c,vf,SAVESTATE_SAVEDATA);vf->close(vf);
   snprintf(path,600,"%s/%s_full.png",argv[3],a); lframe(c,buf,path,0x1f);
   vf=VFileOpen(ss,O_RDONLY);mCoreLoadStateNamed(c,vf,SAVESTATE_SAVEDATA);vf->close(vf);
   snprintf(path,600,"%s/%s_bg.png",argv[3],a); lframe(c,buf,path,0x0f);
   vf=VFileOpen(ss,O_RDONLY);mCoreLoadStateNamed(c,vf,SAVESTATE_SAVEDATA);vf->close(vf);
   snprintf(path,600,"%s/%s_obj.png",argv[3],a); lframe(c,buf,path,0x10); frame++;
   snprintf(path,600,"%s/%s_oam.bin",argv[3],a);FILE*o=fopen(path,"wb");for(unsigned k=0;k<0x400;k++){uint8_t v=c->rawRead8(c,0x07000000+k,-1);fwrite(&v,1,1,o);}fclose(o);
   snprintf(path,600,"%s/%s_vram.bin",argv[3],a);o=fopen(path,"wb");for(unsigned k=0;k<0x8000;k++){uint8_t v=c->rawRead8(c,0x06010000+k,-1);fwrite(&v,1,1,o);}fclose(o);
   snprintf(path,600,"%s/%s_pal.bin",argv[3],a);o=fopen(path,"wb");for(unsigned k=0;k<0x400;k++){uint8_t v=c->rawRead8(c,0x05000000+k,-1);fwrite(&v,1,1,o);}fclose(o);
   continue;}
  { unsigned wa,wv; if(sscanf(line,"w8 %x %x",&wa,&wv)==2){c->busWrite8(c,wa,wv);continue;} }
  if(sscanf(line,"shot %127s",a)==1){snprintf(path,600,"%s/%s.png",argv[3],a);shot(c,buf,path);printf("shot %s @%ld\n",a,frame);continue;}
  if(sscanf(line,"dump %127s %x %x",a,&addr,&len)==3){snprintf(path,600,"%s/%s.bin",argv[3],a);FILE*o=fopen(path,"wb");for(unsigned k=0;k<len;k++){uint8_t v=c->rawRead8(c,addr+k,-1);fwrite(&v,1,1,o);}fclose(o);continue;}
  if(sscanf(line,"save %127s",a)==1){snprintf(path,600,"%s/%s.ss",argv[3],a);struct VFile*vf=VFileOpen(path,O_CREAT|O_TRUNC|O_RDWR);mCoreSaveStateNamed(c,vf,SAVESTATE_SAVEDATA);vf->close(vf);continue;}
  if(sscanf(line,"load %127s",a)==1){snprintf(path,600,"%s/%s.ss",argv[3],a);struct VFile*vf=VFileOpen(path,O_RDONLY);mCoreLoadStateNamed(c,vf,SAVESTATE_SAVEDATA);vf->close(vf);continue;}
  if(sscanf(line,"arec %127s %d %127s",a,&n,b2)>=2){snprintf(path,600,"%s/%s.pcm",argv[3],a);reca=fopen(path,"ab");
   int m=strcmp(b2,"-")&&b2[0]?keymask(b2):0;for(int k=0;k<n;k++){c->setKeys(c,m);c->runFrame(c);frame++;frame_done(c,buf);}c->setKeys(c,0);fclose(reca);reca=0;b2[0]=0;continue;}
  if(sscanf(line,"rec %127s %d %127s",a,&n,b2)>=2){ /* a clip: video piped to ffmpeg (lossless name.mkv), sound appended to name.pcm */
   if(!recv||strcmp(a,recname)){if(recv){pclose(recv);recv=0;} snprintf(path,600,"ffmpeg -loglevel error -y -f rawvideo -pix_fmt rgb24 -s 240x160 -r 59.7275 -i - -c:v libx264 -preset ultrafast -qp 0 '%s/%s.mkv'",argv[3],a);recv=popen(path,"w");strcpy(recname,a);}
   snprintf(path,600,"%s/%s.pcm",argv[3],a);reca=fopen(path,"ab");
   int m=strcmp(b2,"-")&&b2[0]?keymask(b2):0;for(int k=0;k<n;k++){c->setKeys(c,m);c->runFrame(c);frame++;frame_done(c,buf);}c->setKeys(c,0);fclose(reca);reca=0;b2[0]=0;continue;}
  if(sscanf(line,"%d %127s",&n,b2)>=1){int m=strcmp(b2,"-")&&b2[0]?keymask(b2):0;for(int k=0;k<n;k++){c->setKeys(c,m);c->runFrame(c);frame++;frame_done(c,buf);}c->setKeys(c,0);}
 }
 if(recv)pclose(recv);
 printf("frames %ld\n",frame); c->deinit(c); return 0;}
