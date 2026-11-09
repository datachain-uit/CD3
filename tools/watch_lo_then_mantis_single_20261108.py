"""Transfer audited LO bundle, gate one CQ Mantis V, then back up its results.

Read-only for existing outputs except a new gate marker. Runs as a user-requested
local background process; it never stops a machine or deletes remote files.
"""
import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--host',required=True); parser.add_argument('--port',required=True)
parser.add_argument('--lo',required=True); parser.add_argument('--cq',required=True)
parser.add_argument('--suffix',default='')
a=parser.parse_args()
out=ROOT/'CQ/resuilt/mantis_single_queue_20261108'/a.cq
out.mkdir(parents=True,exist_ok=True)
base='/workspace/CD3'
lo_state=f'{base}/runs/lo_patch_{a.lo}_resume_credit_20261107{a.suffix}'
lo_archive=f'{base}/runs/lo_patch_{a.lo}_resume_credit_20261107.tar.gz'
f3_state=f'{base}/mantis_cq_{a.cq}_20261108/state'
f3_archive=f'{base}/runs/mantis_cq_{a.cq}_20261108_results.tar.gz'
ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','-p',a.port,f'root@{a.host}']
scp=['scp','-P',a.port,'-o','BatchMode=yes','-o','ConnectTimeout=12']
drive_id='1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'

def status(stage,**extra):
    (out/'watch_status.json').write_text(json.dumps({'updated_utc':datetime.now(timezone.utc).isoformat(),
        'lo':a.lo,'cq':a.cq,'host':f'{a.host}:{a.port}','status':stage,**extra},indent=2)+'\n',encoding='utf8')

def remote(cmd):
    return subprocess.run(ssh+[cmd],capture_output=True,text=True,timeout=40)

def digest(path,algorithm):
    h=hashlib.new(algorithm)
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def copy_checked(remote_path,sha_path,local_name,target):
    info=remote(f'cat {sha_path}')
    if info.returncode: raise RuntimeError('remote checksum unavailable')
    expected=info.stdout.split()[0].lower()
    partial=out/(local_name+'.partial'); local=out/local_name
    if not local.exists() or digest(local,'sha256')!=expected:
        p=subprocess.run(scp+[f'root@{a.host}:{remote_path}',str(partial)],timeout=21600)
        if p.returncode or digest(partial,'sha256')!=expected: raise RuntimeError('download or SHA-256 mismatch')
        partial.replace(local)
    p=subprocess.run(['rclone','copyto',str(local),target,'--drive-root-folder-id',drive_id,'--immutable','--retries','4'],timeout=21600)
    if p.returncode: raise RuntimeError('Drive upload failed')
    check=subprocess.run(['rclone','md5sum',target,'--drive-root-folder-id',drive_id],capture_output=True,text=True,timeout=180)
    if check.returncode or not check.stdout.split() or check.stdout.split()[0].lower()!=digest(local,'md5'):
        raise RuntimeError('Drive MD5 verification failed')
    return expected,local

deadline=time.monotonic()+72*3600
while time.monotonic()<deadline:
    try:
        if remote(f'test -f {lo_state}/FAILED').returncode==0:
            status('LO_FAILED_NOT_STARTING_MANTIS'); raise SystemExit(1)
        if remote(f'test -f {lo_state}/BUNDLE_READY').returncode!=0:
            status('WAITING_FOR_LO_AUDIT_AND_BUNDLE'); time.sleep(60); continue
        status('DOWNLOADING_AND_VERIFYING_LO')
        name=f'lo_patch_{a.lo}_resume_credit_20261107.tar.gz'
        target=f'gdrive:Jobs/LO/organized_moved_20261029/L1_runs/S3_model/patchtst_seed42_after_credit_20261108/{a.lo}/{name}'
        lo_sha,local=copy_checked(lo_archive,f'{lo_state}/bundle.sha256',name,target)
        if remote(f'touch {base}/mantis_LO_archive_verified_{a.cq}').returncode:
            raise RuntimeError('could not release remote gate')
        status('LO_ON_DRIVE_VERIFIED_MANTIS_GATE_RELEASED',lo_sha256=lo_sha,drive_path=target)
        # User requested reclaiming local space after verified upload.
        local.unlink()
        break
    except (OSError,subprocess.TimeoutExpired,RuntimeError) as error:
        status('LO_TRANSFER_RETRY',error=str(error)); time.sleep(60)
else: status('TIMEOUT_WAITING_FOR_LO'); raise SystemExit(1)

while time.monotonic()<deadline:
    try:
        if remote(f'test -f {f3_state}/FAILED').returncode==0:
            status('MANTIS_FAILED',lo_sha256=lo_sha); raise SystemExit(1)
        if remote(f'test -f {f3_state}/RESULTS_READY').returncode!=0:
            status('MANTIS_RUNNING_OR_WAITING_FOR_INPUT',lo_sha256=lo_sha); time.sleep(60); continue
        name=f'mantis_cq_{a.cq}_20261108_results.tar.gz'
        target=f'gdrive:Jobs/CQ/organized_moved_20261029/L1_runs/S3_model/mantis_v2_seed42_exploratory_20261108/{a.cq}/{name}'
        status('DOWNLOADING_AND_VERIFYING_MANTIS',lo_sha256=lo_sha)
        f3_sha,local=copy_checked(f3_archive,f'{f3_state}/result.sha256',name,target)
        status('MANTIS_RESULTS_ON_DRIVE_VERIFIED',lo_sha256=lo_sha,mantis_sha256=f3_sha,drive_path=target,
               note='compressed caches remain on machine; no machine stop or remote deletion')
        local.unlink()
        break
    except (OSError,subprocess.TimeoutExpired,RuntimeError) as error:
        status('MANTIS_TRANSFER_RETRY',error=str(error),lo_sha256=lo_sha); time.sleep(60)
else: status('TIMEOUT_WAITING_FOR_MANTIS',lo_sha256=lo_sha)
