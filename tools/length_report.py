"""Playtime estimate per chapter (2026-11-02): areas (walkable space), enemies (grunt 20 s, mini-boss 60 s, boss 150 s),
scene text (1.5 s per box + 18 chars/s), optional NPCs/examines (10 s), x1.1 for retries. Low bound = confident player;
first-time players ~x1.5. Chapter -> area / scene lists are in CH / SC below. usage: python3 tools/length_report.py (repo root)"""
import sys, json, re, math, glob, struct
sys.path.insert(0,'tools'); import clipcheck as C
R=C.Rom(open('log4/out/LoG4.gba','rb').read())
c=json.load(open('log4/areas.json')); S=json.load(open('log4/stats.json'))['enemies']; bf=open('bf.gba','rb').read()
def hp(t):
    if str(t) in S: return S[str(t)]['hp']
    return struct.unpack_from('<i',bf,0x711274+28*t+4)[0]
CH={1:['1:1','1:61','1:90','1:91','1:92','1:93','1:94','1:84','1:85'],
    2:['1:67','1:68','1:95','1:96','1:97','1:100','1:101','1:102','1:73'],
    3:['1:69','1:70','1:71','1:103','1:104','1:105','1:106','1:107'],
    4:['1:72','1:74','1:76','1:78','1:108','1:109','1:110'],
    5:['4:1','4:40','4:41','4:42','4:43','4:44','4:45'],
    6:['16:1','16:41','16:42','16:43','16:44','1:66','1:79'],
    7:['1:80','1:81','1:82','1:83','1:111','1:112'],
    8:['17:1','17:2','17:3','17:4','17:6','17:7','17:8','17:9','17:10','17:34','17:35','17:36','16:2'],
    9:['17:11','17:12','17:13','17:14','17:15','17:16','17:17','17:18','17:19','17:20','17:37','17:38','17:39'],
    10:['17:21','17:22','17:23','17:24','17:40'],
    11:['17:25','17:26','17:27','17:28','17:29','17:30','17:31','17:33','17:41'],
    12:['17:42','17:43','17:44','17:45','17:46','17:47']}
SC={1:['intro','act1_opening','act1_ch1','lab_talk'],2:['act1_ch2'],3:['act1_ch3'],4:['act1_ch4'],5:['act2_siblings'],6:['act2_ch6'],
    7:['act3_ch7'],8:['act3_ch8'],9:['act3_ch9'],10:['act3_ch10'],11:['secret_first_steps'],12:['act3_world','act3_world_fly']}
ent={'%d:%d'%(v['world'],v['area']):v for v in c['new_areas']+c.get('areas',[])}
rows=[]
for ch in range(1,13):
    walk=fight=0; ng=nb=nmb=0; side=0; dl=0
    for k in CH[ch]:
        w,a=map(int,k.split(':'))
        try:
            m=R.walk_mask(R.map_of(w,a)); px=int((m==1).sum())*64
        except Exception: px=0
        path=2*math.sqrt(px) if px else 0
        v=ent.get(k,{})
        scene_only = px<20000
        walk += 15 if scene_only else path/60*1.6 + 20      # ~1 px/frame, detours x1.6, +20 s finding the way
        for e in v.get('enemies',[]):
            h=hp(e['type'])
            if h>=1000: nb+=1; fight+=150
            elif h>=400: nmb+=1; fight+=60
            else: ng+=1; fight+=20
        for d in v.get('doors',[]):
            if 'examine' in d: side+=1
        side += sum(1 for s in v.get('spawns',[]) if s.get('talk'))
    chars=0; lines=0
    for f in SC[ch]:
        for ln in open('log4/scenes/%s.scene'%f, encoding='utf-8'):
            t=ln.strip()
            for p in ('say ','narrate ','journal '):
                if t.startswith(p):
                    body=t[len(p):] if p!='say ' else t.split(' ',2)[2] if len(t.split(' ',2))>2 else ''
                    chars+=len(body); lines+=1
    read = lines*1.5 + chars/18          # box pacing + ~18 chars/s reading with the typewriter
    other = side*10                      # walking up to optional people/objects
    tot=(walk+fight+read+other)*1.1      # deaths/retries/menus
    rows.append((ch,len(CH[ch]),ng,nmb,nb,lines,int(walk/60),int(fight/60),int(read/60),int(other/60),tot/60))
names={11:'Secret',12:'Open world (optional)'}
print('%-22s %5s %4s %4s %4s %6s %5s %5s %5s %5s %7s'%('chapter','areas','grnt','mini','boss','lines','walk','fight','read','side','TOTAL'))
T=0
for r in rows:
    print('%-22s %5d %4d %4d %4d %6d %5d %5d %5d %5d %6.0fm'%((names.get(r[0],'Chapter %d'%r[0]),)+r[1:]))
    T+=r[-1]
print('total %.1f h (story only %.1f h)'%(T/60,(T-rows[-1][-1])/60))
