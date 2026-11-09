import hashlib,json,subprocess,sys,time
from pathlib import Path
from drive_verify_shared_20261107 import upload_and_verify
root=Path(__file__).resolve().parents[1]
host,port,version=sys.argv[1:4]
directory=root/'LO/resuilt'/f'lo_patch_{version}_seed42_20261107'
receipt=directory/'watch_status.json'
status=directory/'remote_cleanup_status.json'
directory.mkdir(parents=True,exist_ok=True)
remote=f'/workspace/CD3/runs/lo_patch_{version}_closure.tar.gz'
ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-p',port,f'root@{host}']
def rec(s,**kw):status.write_text(json.dumps({'status':s,'host':host,'port':port,'version':version,**kw},indent=2),encoding='utf8')
for attempt in range(30240):
    try:
        data=json.loads(receipt.read_text(encoding='utf8'))
        if data.get('status')=='DOWNLOAD_VERIFIED':break
        if data.get('status') in ('REMOTE_FAILED','DOWNLOAD_FAILED','TIMEOUT'):
            rec('BLOCKED',reason=data['status']);sys.exit(1)
    except (FileNotFoundError,json.JSONDecodeError):pass
    rec('WAITING_VERIFIED_DOWNLOAD',attempt=attempt);time.sleep(60)
else:rec('TIMEOUT');sys.exit(1)
try:
    expected=data['sha256']
    local=Path(data['archive'])
    if not local.is_file():raise RuntimeError('verified local archive missing')
    with local.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise RuntimeError('local hash mismatch')
    rec('UPLOADING_DRIVE',sha256=expected,local=str(local))
    drive=upload_and_verify(local,f'LO_PATCHTST_{version}_seed42_W1_W3_20261107.tar.gz')
    rec('DRIVE_VERIFIED',sha256=expected,local=str(local),drive=drive)
    result=subprocess.check_output(ssh+['sha256sum '+remote],text=True,timeout=300).split()[0]
    if result!=expected:raise RuntimeError('remote hash changed')
    subprocess.run(ssh+['rm -- '+remote],check=True,timeout=60)
    rec('REMOTE_ARCHIVE_REMOVED',sha256=expected,local=str(local),drive=drive)
    local.unlink()
    rec('DRIVE_VERIFIED_LOCAL_AND_REMOTE_TEMP_REMOVED',sha256=expected,drive=drive)
except Exception as exc:
    rec('BLOCKED',error=str(exc));raise
