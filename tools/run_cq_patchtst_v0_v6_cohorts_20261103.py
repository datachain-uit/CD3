"""Compute remaining CQ cohort slices from verified run archives and local salt."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys,tarfile,shutil,json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103'
NAMES={1:'cq_patchtst_v1_seed42_20261031',2:'cq_patchtst_v2_seed42_20261101',3:'cq_patchtst_v3_seed42_20261101',4:'cq_patchtst_v4_seed42_20261101',5:'cq_patchtst_v5_seed42_20261101',6:'cq_patchtst_v6_seed42_20261101'}
def work(i):
    name=NAMES[i];out=BASE/'cohort_audit'/f'V{i}'
    if (out/'summary.json').exists():return f'V{i} already complete'
    receipt=json.loads((ROOT/'CQ/resuilt'/name/'download_receipt.json').read_text(encoding='utf8'))
    if receipt.get('status')!='download_verified':raise ValueError(f'V{i} not verified')
    archive=Path(receipt['archive'])
    root=ROOT/'CQ/resuilt/cq_patchtst_cohort_staging_20261103'/f'V{i}'
    root.mkdir(parents=True,exist_ok=True)
    if True:
        count=0
        with tarfile.open(archive,'r:gz') as tar:
            for member in tar:
                if not member.isfile() or '/predictions/' not in member.name or not member.name.endswith('.parquet'):continue
                parts=Path(member.name).parts
                try:idx=parts.index('CQ')
                except ValueError:continue
                dest=root.joinpath(*parts[idx:]);dest.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(member) as src,dest.open('wb') as dst:shutil.copyfileobj(src,dst)
                count+=1
        if count!=24:raise ValueError(f'V{i}: expected 24 prediction files, got {count}')
        cmd=[sys.executable,'-u','-X','utf8',str(ROOT/'tools/audit_prediction_course_cohort.py'),'--task','CQ','--data-root',str(ROOT/'downloads/vastai/CQ_V2_2_clean_grain_seed42'),'--model-root',str(root),'--output-root',str(out),'--pipeline-id',f'V{i}','--model-name','PATCHTST','--seed','42','--prediction-salt-file',str(ROOT/'CQ/resuilt/private/.cq_matched_replay_prediction_salt')]
        subprocess.run(cmd,cwd=ROOT,check=True)
    return f'V{i} complete'
if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(work,range(1,7)):print(result,flush=True)
