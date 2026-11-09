import json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
host,port,previous,following=sys.argv[1:5]
target=f'root@{host}'
state=root/'logs'/f'lo_queue_{previous}_to_{following}_{port}.json'
state.parent.mkdir(parents=True,exist_ok=True)
ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-p',port,target]
def record(value,**kwargs): state.write_text(json.dumps({'status':value,'host':host,'port':port,'previous':previous,'next':following,**kwargs},indent=2),encoding='utf8')
def remote(cmd): return subprocess.run(ssh+[cmd],capture_output=True,text=True,timeout=90)
for attempt in range(30240):
    try:
        running=remote('pgrep -af vastai_train_shared.py')
        if running.returncode not in (0,1):record('SSH_RETRY',attempt=attempt);time.sleep(60);continue
        if running.returncode==0:record('WAITING_TRAIN',attempt=attempt);time.sleep(60);continue
        manifest=f'/workspace/CD3/runs/lo_patchtst_seed42/LO/W3/{previous}/PATCHTST/seed=42/run_manifest.json'
        if remote('test -s '+manifest).returncode!=0:
            record('BLOCKED_MISSING_W3_MANIFEST');sys.exit(1)
        if previous=='V2':
            receipt=root/'LO/resuilt/lo_patchtst_v2_w3_20261107/watch_status.json'
            try: data=json.loads(receipt.read_text(encoding='utf8'))
            except (FileNotFoundError,json.JSONDecodeError): data={}
            if data.get('status')!='DOWNLOAD_VERIFIED' or data.get('audit_status')!='SUCCESS':
                record('WAITING_V2_AUDIT_AND_VERIFIED_DOWNLOAD',attempt=attempt);time.sleep(60);continue
        size=remote('df -Pk /workspace')
        if size.returncode!=0:record('SSH_RETRY',attempt=attempt);time.sleep(60);continue
        available=int(size.stdout.strip().splitlines()[-1].split()[3])
        if available<6*1024*1024:
            record('WAITING_DISK',available_kib=available,attempt=attempt);time.sleep(300);continue
        record('DEPLOYING')
        proc=subprocess.run([sys.executable,str(root/'tools/deploy_lo_patch_grid_20261107.py'),host,port,following],cwd=root)
        if proc.returncode:record('DEPLOY_FAILED',exit=proc.returncode);sys.exit(1)
        creation=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'DETACHED_PROCESS',0)
        subprocess.Popen([sys.executable,str(root/'tools/watch_lo_patch_complete_20261107.py'),host,port,following],cwd=root,creationflags=creation,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.Popen([sys.executable,str(root/'tools/cleanup_lo_patch_bundle_when_verified_20261107.py'),host,port,following],cwd=root,creationflags=creation,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        record('LAUNCHED_AND_WATCHING');sys.exit(0)
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        record('RETRY',error=str(e),attempt=attempt);time.sleep(60)
record('TIMEOUT')
