import hashlib, json, subprocess, sys, time
from pathlib import Path

root=Path(__file__).resolve().parents[1]
host,port,version=sys.argv[1:4]
target=f'root@{host}'
state=f'/workspace/CD3/runs/lo_patch_{version}_closure'
bundle=f'/workspace/CD3/runs/lo_patch_{version}_closure.tar.gz'
dest=root/'LO/resuilt'/f'lo_patch_{version}_seed42_20261107'
dest.mkdir(parents=True,exist_ok=True)
status=dest/'watch_status.json'
def record(s,**kw): status.write_text(json.dumps({'status':s,'host':host,'port':port,'version':version,**kw},indent=2),encoding='utf8')
ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-p',port,target]
for attempt in range(30240):
    try:
        ready=subprocess.run(ssh+['test -f '+state+'/BUNDLE_READY'],capture_output=True,timeout=45).returncode==0
        if ready: break
        fail=subprocess.run(ssh+['test -f '+state+'/FAILED'],capture_output=True,timeout=45).returncode==0
        if fail: record('REMOTE_FAILED'); sys.exit(1)
        record('WAITING',attempt=attempt)
    except (OSError,subprocess.TimeoutExpired) as e: record('RETRY',error=str(e))
    time.sleep(60)
else: record('TIMEOUT'); sys.exit(1)
expected=subprocess.check_output(ssh+['cat '+state+'/bundle.sha256'],text=True,timeout=45).split()[0]
partial=dest/'closure.tar.gz.partial'; final=dest/'closure.tar.gz'
for retry in range(10):
    try:
        record('DOWNLOADING',attempt=retry)
        subprocess.run(['scp','-o','BatchMode=yes','-o','ConnectTimeout=15','-P',port,target+':'+bundle,str(partial)],check=True,timeout=28800)
        with partial.open('rb') as f: got=hashlib.file_digest(f,'sha256').hexdigest()
        if got!=expected: raise RuntimeError('bundle hash mismatch')
        partial.replace(final); record('DOWNLOAD_VERIFIED',sha256=got,archive=str(final)); break
    except (OSError,RuntimeError,subprocess.SubprocessError) as e: record('DOWNLOAD_RETRY',error=str(e)); time.sleep(60)
else: record('DOWNLOAD_FAILED'); sys.exit(1)
