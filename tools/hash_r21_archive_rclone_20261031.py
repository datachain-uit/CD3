"""Stream the closure archive from Drive to SHA-256 without local staging."""
from pathlib import Path
import hashlib,json,subprocess,sys
RCLONE=Path.home()/'AppData/Local/Microsoft/WinGet/Packages/Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe/rclone-v1.75.1-windows-amd64/rclone.exe'
REMOTE='gdrive:Jobs/LO/organized_moved_20261029/L1_runs/S3_model/run_bundles/lo_static_v2_seed42_20261026/archives/LO_static_v2_closure_20261028.tar.gz'
EXPECTED='9108372950940430d9b72f950637088912bdc476bc062a54527527ddf60740d3'
OUT=Path('CQ/resuilt/input/results/R21_evidence_20261031/lo_archive_rclone_sha256.json')
def main():
    h=hashlib.sha256(); size=0
    p=subprocess.Popen([str(RCLONE),'cat',REMOTE],stdout=subprocess.PIPE)
    while chunk:=p.stdout.read(4*1024*1024):
        h.update(chunk); size+=len(chunk)
        if size//(256*1024*1024)!=(size-len(chunk))//(256*1024*1024): print(f'read {size//(1024*1024)} MiB',flush=True)
    code=p.wait(); result={'source':REMOTE,'bytes':size,'sha256':h.hexdigest(),'expected_sha256':EXPECTED,'matches':code==0 and h.hexdigest()==EXPECTED,'rclone_exit_code':code}
    OUT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8'); print(json.dumps(result),flush=True)
    if not result['matches']: sys.exit(1)
if __name__=='__main__': main()
