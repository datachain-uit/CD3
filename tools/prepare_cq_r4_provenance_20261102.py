"""Prepare a provisional, hash-verified CQ R4 provenance inventory."""
from pathlib import Path
import hashlib,json,os,shutil
from datetime import datetime,timezone
import pandas as pd

SOURCE=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))/'CQ/organized_moved_20261029/L2_facts/fact_exports/cq_recurrent_allfamilies_grid_r4_20261023'
L0=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))/'CQ/organized_moved_20261029/L0_registry/modal_L0_registry/L0_registry'
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
    receipt=L0/'external_fact_ingests/task=CQ/ingest_id=vastai_cq_f1_batch2048_seed42_slice_r2_20261019/receipt.json'
    provenance={'source':'NOT_FOUND'}
    if receipt.is_file():
        doc=json.loads(receipt.read_text(encoding='utf8'));shutil.copy2(receipt,OUT/'prior_153_run_ingest_receipt.json')
        provenance={'source':'prior 153-run LSTM/GRU/BiLSTM ingest receipt, not a separate R4 receipt','receipt_sha256':sha(receipt),'contract_count':doc.get('contract_count'),'runner_sha256_as_recorded':doc.get('uniform_execution',{}).get('runner_sha256')}
    state=L0/'state_manifests/s0_CQ.json';release=json.loads(state.read_text(encoding='utf8'))['release']
    summary={'created_at_utc':datetime.now(timezone.utc).isoformat(),'source_path':str(SOURCE),'files':facts,'resource_runs':len(resources),'energy_measurement_types':measurement,'data_release_id_as_recorded_in_s0':release.get('data_release_id'),'s0_manifest_sha256':sha(state),'prior_receipt':provenance,'status':'DRAFT_PENDING_RNN_RECEIPT_AND_SLICE_RECONCILIATION'}
    (OUT/'source_inventory.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (OUT/'sha256sums.txt').write_text(''.join(f"{x['sha256']}  {x['name']}\n" for x in facts),encoding='utf8')
    (OUT/'README.md').write_text('''# CQ R4, seed 42 — provenance inventory (draft)

Source: Jobs/CQ/organized_moved_20261029/L2_facts/fact_exports/cq_recurrent_allfamilies_grid_r4_20261023.
One record per family, pipeline, window, split and phase; 1,632 cells and 204 resource runs.
TRAIN time is sum of epoch train_seconds; GPU energy is an NVML power-sampling estimate where recorded, not full-machine energy or CO2.
Pipelines: V0 zero-fill; V1/V2/V3/V4 median with none/CDSMOTE/SASMOTE/Radius; V5/V6/V7/V8 mean with those variants; V9/V10/V11/V12 ExtraTrees; V13/V14/V15/V16 MICE.

This inventory hashes the source files listed in sha256sums.txt. `prior_153_run_ingest_receipt.json` records the LSTM/GRU/BiLSTM prior ingest and its declared runner SHA; it is not a receipt for the full R4 export. The S0 manifest supplies the recorded release ID and its own hash in source_inventory.json. This is not final T1-EX-07 acceptance: the RNN/full-R4 receipt and runner still need independent confirmation; ALL-slice calibration/PR-AUC differs from R4 due to distinct implementations and must be reconciled.
''',encoding='utf8')
    print(json.dumps({'files':len(files),'resource_runs':len(resources),'energy_measurement_types':measurement,'status':summary['status']},indent=2))
if __name__=='__main__': main()
