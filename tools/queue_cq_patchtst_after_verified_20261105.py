"""After a completed audited run, download/verify it, then launch the next CQ V."""
import concurrent.futures, hashlib, json, subprocess, sys, time
from pathlib import Path

CURRENT, NEXT, HOST, PORT = sys.argv[1:5]
PARENTS={'V10':'V9','V15':'V13','V16':'V13'}
NAMES={'V7':'cq_patchtst_v7_seed42_20261102','V13':'cq_patchtst_v13_seed42_20261104',
       'V9':'cq_patchtst_v9_migrated_20261104'}
assert CURRENT in NAMES and NEXT in PARENTS
parent=PARENTS[NEXT]; name=NAMES[CURRENT]; nxt=f'cq_patchtst_{NEXT.lower()}_continued_20261105'
ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-p',PORT,f'root@{HOST}']
scp=['scp','-o','BatchMode=yes','-o','ConnectTimeout=15','-P',PORT]
base=Path('downloads/vastai/CQ_V2_2_clean_grain_seed42')
def remote(cmd,check=True): return subprocess.run(ssh+[cmd],text=True,capture_output=True,check=check,timeout=1800)
def download():
    path=f'/workspace/CD3/runs/{name}_verified.tar.gz'
    remote(f'tar -czf {path} -C /workspace/CD3/runs {name} {name}_audit')
    expected=remote(f'sha256sum {path}').stdout.split()[0]
    out=Path('CQ/resuilt')/name;out.mkdir(parents=True,exist_ok=True);dest=out/Path(path).name
    subprocess.run(scp+[f'root@{HOST}:{path}',str(dest)],check=True,timeout=28800)
    with dest.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=expected:raise RuntimeError('Archive SHA-256 mismatch')
    (out/'download_receipt.json').write_text(json.dumps({'status':'download_verified','sha256':digest,'next':NEXT},indent=2))
    print('DOWNLOADED VERIFIED',CURRENT,flush=True)
def transfer(entry):
    rel=entry['local_path'].replace('\\','/')
    if '..' in rel or not rel.endswith('.parquet'):raise ValueError(rel)
    local=base/rel
    with local.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    dest=f'/workspace/CD3/data/CQ_V2_2_clean_grain_seed42/{rel}'
    check=remote(f'test -f {dest} && sha256sum {dest}',False)
    if check.returncode==0:
        if check.stdout.split()[0]!=digest:raise ValueError(f'existing input differs {rel}')
        return
    remote(f'mkdir -p {dest.rsplit("/",1)[0]}')
    subprocess.run(scp+[str(local),f'root@{HOST}:{dest}.partial'],check=True,timeout=14400,capture_output=True)
    if remote(f'sha256sum {dest}.partial').stdout.split()[0]!=digest:raise ValueError(f'upload mismatch {rel}')
    remote(f'test ! -e {dest} && mv {dest}.partial {dest}')
    print('INPUT VERIFIED',NEXT,rel,flush=True)
def main():
    while True:
        try:
            if remote(f'test -f /workspace/CD3/runs/{name}/FAILED',False).returncode==0: raise RuntimeError('Current run failed; machine retained')
            if remote(f'test -f /workspace/CD3/runs/{name}/COMPLETE',False).returncode==0:break
        except (subprocess.TimeoutExpired,subprocess.CalledProcessError):pass
        time.sleep(60)
    download()
    active=remote("pgrep -f '[v]astai_train_shared.py|[v]astai_audit_shared.py'",False)
    if active.returncode!=1:raise RuntimeError('Machine not confirmed idle')
    manifest=json.loads((base/'download_manifest.json').read_text())
    rows=[x for x in manifest['files'] if f'/{parent}/' in x['local_path'].replace('\\','/') or (f'/{NEXT}/' in x['local_path'].replace('\\','/') and x['local_path'].replace('\\','/').startswith('train/'))]
    if manifest.get('release_id')!='CQ_V2_2' or len(rows)!=21:raise ValueError(f'Expected 21 input files, got {len(rows)}')
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(transfer,rows))
    source=Path('tools/run_cq_patchtst_v12_seed42.sh').read_text().replace('V12',NEXT).replace('V9',parent).replace('cq_patchtst_v12_seed42_20261104',nxt)
    local=Path('upload_staging')/f'run_{nxt}.sh';local.write_text(source,encoding='utf8',newline='\n')
    subprocess.run(scp+[str(local),f'root@{HOST}:/workspace/CD3/tools/{local.name}'],check=True)
    conf=f'/etc/supervisor/conf.d/{nxt}.conf'
    config=f'[program:{nxt}]\ncommand=/bin/bash /workspace/CD3/tools/{local.name}\ndirectory=/workspace/CD3\nautostart=false\nautorestart=false\nstartsecs=10\nstdout_logfile=/workspace/CD3/{nxt}.log\nstderr_logfile=/workspace/CD3/{nxt}.err.log\nstdout_logfile_maxbytes=0\nstderr_logfile_maxbytes=0\n'
    localconf=Path('upload_staging')/f'{nxt}.conf';localconf.write_text(config,encoding='utf8',newline='\n')
    subprocess.run(scp+[str(localconf),f'root@{HOST}:/workspace/CD3/{nxt}.conf'],check=True)
    remote(f'cp /workspace/CD3/{nxt}.conf {conf} && supervisorctl reread && supervisorctl update && supervisorctl start {nxt}')
    print('STARTED',NEXT,'AFTER',CURRENT,flush=True)
    # Follow-up completion is supervised locally and includes audit + verified download.
    name2=nxt
    while True:
        try:
            if remote(f'test -f /workspace/CD3/runs/{name2}/FAILED',False).returncode==0:raise RuntimeError('Next run failed; machine retained')
            if remote(f'test -f /workspace/CD3/runs/{name2}/COMPLETE',False).returncode==0:break
        except (subprocess.TimeoutExpired,subprocess.CalledProcessError):pass
        time.sleep(60)
    name_old=name
    globals()['name']=name2
    download()
    if remote("pgrep -f '[v]astai_train_shared.py|[v]astai_audit_shared.py'",False).returncode!=1:raise RuntimeError('Machine not confirmed idle')
    print('DOWNLOAD VERIFIED; INSTANCE RETAINED',NEXT,flush=True)
if __name__=='__main__':main()
