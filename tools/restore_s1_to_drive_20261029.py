"""Stream verified S1 attempts from Modal to Drive one attempt at a time."""
import json, os, shutil, subprocess, sys
from pathlib import Path
task=sys.argv[1].upper()
profiles={'CQ':'sghqvbg','LO':'minhman26804'}
root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'downloads'/f's1_artifacts_{task}_20261029.json').read_text(encoding='utf-8'))
base=root/'downloads'/'s1_upload_staging_20261029'/task
r=Path(os.environ['LOCALAPPDATA'])/'Microsoft/WinGet/Packages/Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe/rclone-v1.75.1-windows-amd64/rclone.exe'
remote_root=f"gdrive:Jobs/{task}/organized_moved_20261029/L1_runs/S1_imputation/complete_seed20260922"
for row in rows:
    if not(row.get('preprocessor') and row.get('required_inputs') and row.get('status')=='SUCCESS'):
        raise SystemExit(f"Incomplete Modal S1 {row.get('window')}/{row.get('pipeline')}")
    rel=Path(row['manifest_path']).relative_to('/data')
    src=str(rel.parent).replace('\\','/')
    dst=base/row['window']/row['pipeline']
    dst.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,'-X','utf8','-m','modal','volume','get','--profile',profiles[task],'--force','tempo-data-v1',src,str(dst)],check=True)
    attempt_dir=dst/f"attempt_id={row['attempt_id'].split('-',1)[-1]}"
    manifest=attempt_dir/'run_manifest.json'
    if not manifest.is_file(): raise SystemExit(f'Manifest missing after download: {dst}')
    m=json.loads(manifest.read_text(encoding='utf-8'))
    if m.get('run_id')!=row.get('run_id') or m.get('attempt_id')!=row.get('attempt_id'):
        raise SystemExit(f'Identity mismatch: {dst}')
    rel=f"{row['window']}/{row['pipeline']}"
    remote=f"{remote_root}/{rel}"
    subprocess.run([str(r),'copy',str(dst),remote,'--immutable','--transfers','4','--checkers','8','--stats','30s'],check=True)
    subprocess.run([str(r),'check',str(dst),remote,'--one-way','--checkers','8','--stats','30s'],check=True)
    print(f"UPLOADED_AND_VERIFIED {task}/{rel}",flush=True)
    shutil.rmtree(dst)
print(f'VERIFIED_S1_COMPLETE {task}',flush=True)
