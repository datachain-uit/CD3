import hashlib,subprocess
from pathlib import Path

DRIVE_ROOT='1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'
PREFIX='gdrive:Jobs/LO/organized_moved_20261029/L1_runs/S3_model/preserved_packages/'
def upload_and_verify(path:Path, filename:str)->str:
    target=PREFIX+filename
    subprocess.run(['rclone','copyto',str(path),target,'--drive-root-folder-id',DRIVE_ROOT,'--retries','5'],check=True,timeout=86400)
    result=subprocess.check_output(['rclone','md5sum',target,'--drive-root-folder-id',DRIVE_ROOT],text=True,timeout=300).strip().split()[0]
    if len(result)!=32:raise RuntimeError('Drive MD5 unavailable')
    with path.open('rb') as f:local=hashlib.file_digest(f,'md5').hexdigest()
    if local.lower()!=result.lower():raise RuntimeError('Drive MD5 differs from local file')
    return target
