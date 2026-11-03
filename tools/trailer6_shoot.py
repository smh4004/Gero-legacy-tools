import subprocess, os, sys
from concurrent.futures import ThreadPoolExecutor
D=os.path.dirname(os.path.abspath(__file__))
ROM=D+'/LoG4_shoot.gba'; NAMED=D+'/named_lists_shoot.json'
def fire(n, d):
    L=[]
    for i in range(n): L+=['rec %s 3 '+d,'rec %s 4 B','rec %s 20 -']
    return L
def atk(n, step='UP'):
    L=[]
    for i in range(n): L+=['rec %s 4 A','rec %s 8 -','rec %s 4 A','rec %s 8 -','rec %s 4 A','rec %s 14 -','rec %s 6 '+step]
    return L
SH={
 'wm':      ('t_worldmap',[],['rec %s 60 -','rec %s 150 UP','rec %s 40 RIGHT','rec %s 160 UP','rec %s 30 LEFT','rec %s 120 UP']),
 'wmb':     ('t_worldmap',[],['rec %s 60 -','rec %s 200 B','rec %s 120 -']),
 'outfit':  ('sh_wc767',[],['rec %s 40 -','rec %s 30 DOWN','rec %s 4 L','rec %s 20 -','rec %s 4 L','rec %s 20 -','rec %s 4 L','rec %s 30 -','rec %s 4 B','rec %s 120 -','rec %s 40 RIGHT','rec %s 4 B','rec %s 120 -']),
 'lookout': ('sh_w_lookout',[],['rec %s 60 -','rec %s 70 UP','rec %s 50 LEFT','rec %s 40 UP','rec %s 90 RIGHT','rec %s 40 -']),
 'papaya':  ('sh_w_papaya',[],['rec %s 30 -','rec %s 60 LEFT','rec %s 50 DOWN']+atk(10,'LEFT')),
 'desert':  ('sh_w_desert',[],['rec %s 30 -','rec %s 60 RIGHT','rec %s 50 UP']+atk(12,'UP')),
 'pilaf':   ('sh_w_pilaf',[],['rec %s 30 -','rec %s 40 LEFT','rec %s 30 UP']+atk(10,'UP')),
 'osc':     ('sh_w_osc',[],['rec %s 40 -','rec %s 100 RIGHT','rec %s 40 UP','rec %s 40 -']),
 'nataday': ('sh_w_nataday',[],['rec %s 30 -','rec %s 60 UP','rec %s 30 LEFT']+atk(8,'LEFT')),
 'tank':    ('sh_drone_arena',[],['rec %s 40 -']+fire(5,'LEFT')+['rec %s 30 UP']+fire(5,'LEFT')+['rec %s 30 DOWN']+fire(5,'LEFT')),
 'lapis':   ('t_lapis_4_43',[],['rec %s 30 -','rec %s 20 UP']+atk(12,'UP')),
 'collect': ('t_lapis_16_43',[],['rec %s 30 -','rec %s 20 UP']+atk(12,'UP')),
 'nightw':  ('sh_night',[],['rec %s 40 -','rec %s 120 DOWN','rec %s 60 RIGHT','rec %s 60 DOWN']),
}
def go(name):
    lst,flags,tail=SH[name]
    out=os.path.join(D,name); os.makedirs(out,exist_ok=True)
    env=dict(os.environ, NAMED=NAMED, SHOTS='0', TAIL='|'.join([t%name for t in tail]))
    r=subprocess.run(['python3','/home/claude/rom/tools/listtest.py',ROM,out,name,'17:32:424:440',lst]+flags,env=env,capture_output=True,text=True)
    return name, r.returncode, r.stderr[-200:]
names=sys.argv[1:] or list(SH)
with ThreadPoolExecutor(3) as ex:
    for res in ex.map(go,names): print(res, flush=True)
