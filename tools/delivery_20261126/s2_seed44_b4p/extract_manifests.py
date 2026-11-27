"""Stream seed-44 model-run tars from the shared Drive (read-only) and keep run_manifest.json members only (no extraction of other files)."""
import subprocess, tarfile, sys, os, json, hashlib, csv
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
OUT='<WORK_DIR>/raw'
ROOT='--drive-root-folder-id=1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'
env=dict(os.environ,MSYS_NO_PATHCONV='1')
plan=pd.read_csv('<WORK_DIR>/run_tar_plan.csv')
tars=sorted(plan.tar.unique())
exp={}
for l in open('<TEMPO_WORK_ROOT>/phaseB/pred_scan.jsonl'):
    r=json.loads(l); exp[r['path']]=sum(1 for m in r['members'] if m[0].endswith('run_manifest.json'))
def work(i_t):
    i,t=i_t
    done=f'{OUT}/t{i:03d}.done'
    if os.path.exists(done): return
    old=t.replace('seed=44/','',1)
    need=exp.get(old,0); n=0; names=[]
    pr=subprocess.Popen(['rclone','cat','gdrive:'+t,ROOT],stdout=subprocess.PIPE,env=env)
    try:
        with tarfile.open(fileobj=pr.stdout,mode='r|*') as tf:
            for m in tf:
                if m.isfile() and m.name.endswith('run_manifest.json'):
                    b=tf.extractfile(m).read()
                    open(f'{OUT}/t{i:03d}__{n}.json','wb').write(b); names.append(m.name); n+=1
                    if need and n>=need: break
    except Exception as e:
        print('ERR',t,e,flush=True)
    pr.kill(); pr.wait()
    json.dump({'tar':t,'members':names,'expected':need},open(done,'w'))
    print(i,t.split('/')[-1],n,need,flush=True)
with ThreadPoolExecutor(2) as ex: list(ex.map(work,enumerate(tars)))
print('ALL DONE')
