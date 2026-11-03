"""Prepare a provisional, hash-verified CQ R4 provenance inventory."""
from pathlib import Path
import hashlib,json,os
from datetime import datetime,timezone
import pandas as pd

SOURCE=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))/'CQ/organized_moved_20261029/L2_facts/fact_exports/cq_recurrent_allfamilies_grid_r4_20261023'
OUT=Path('CQ/resuilt/cq_r4_provenance_20261102')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files=sorted(p for p in SOURCE.iterdir() if p.is_file() and p.suffix in ('.csv','.parquet','.json'))
    facts=[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    resources=pd.read_parquet(SOURCE/'cq_resource_per_run.parquet')
    if len(resources)!=204: raise ValueError('unexpected CQ resource coverage')
    measurement=resources.energy_measurement_type.fillna('NULL').value_counts().to_dict()
    summary={'created_at_utc':datetime.now(timezone.utc).isoformat(),'source_path':str(SOURCE),'files':facts,'resource_runs':len(resources),'energy_measurement_types':measurement,'status':'DRAFT_PENDING_RECEIPT_RUNNER_AND_SLICE_RECONCILIATION'}
    (OUT/'source_inventory.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (OUT/'sha256sums.txt').write_text(''.join(f"{x['sha256']}  {x['name']}\n" for x in facts),encoding='utf8')
    (OUT/'README.md').write_text('''# CQ R4, seed 42 — provenance inventory (draft)

Source: Jobs/CQ/organized_moved_20261029/L2_facts/fact_exports/cq_recurrent_allfamilies_grid_r4_20261023.
One record per family, pipeline, window, split and phase; 1,632 cells and 204 resource runs.
TRAIN time is sum of epoch train_seconds; GPU energy is an NVML power-sampling estimate where recorded, not full-machine energy or CO2.
Pipelines: V0 zero-fill; V1/V2/V3/V4 median with none/CDSMOTE/SASMOTE/Radius; V5/V6/V7/V8 mean with those variants; V9/V10/V11/V12 ExtraTrees; V13/V14/V15/V16 MICE.

This inventory hashes the source files listed in sha256sums.txt. It is not final T1-EX-07 acceptance: runner and ingest receipts still need independent confirmation; ALL-slice calibration/PR-AUC differs from R4 due to distinct implementations and must be reconciled.
''',encoding='utf8')
    print(json.dumps({'files':len(files),'resource_runs':len(resources),'energy_measurement_types':measurement,'status':summary['status']},indent=2))
if __name__=='__main__': main()
