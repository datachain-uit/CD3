"""Export LO seed-42 S2 counts and Radius audit, preserving provenance limits."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
import pandas as pd

ROOT = Path(r'G:\My Drive\Jobs\LO\organized_moved_20261029')
BASE = ROOT / 'L1_runs/S2_augmentation/provenance_seed42'
RADIUS = ROOT / 'L2_facts/audits_and_evidence/radius_fallback_audit_v3_1_vastai_seed42'
OUT = Path('LO/resuilt/lo_s2_sampling_seed42_20261106')
PIPES = {'CDSMOTE': ['V2','V6','V10','V14'], 'SASMOTE': ['V3','V7','V11','V15'], 'RADIUS_SMOTE': ['V4','V8','V12','V16']}
PARENT = {'V1':'V4', 'V5':'V8', 'V9':'V12', 'V13':'V16'}
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()
def main():
    files=sorted(RADIUS.rglob('radius_fallback.parquet'))
    if len(files)!=12: raise ValueError(f'Expected 12 Radius files, got {len(files)}')
    rad=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
    if len(rad)!=24 or rad.duplicated(['window_id','parent_pipeline','class_code']).any(): raise ValueError('Radius coverage mismatch')
    rows=[]; inventory=[]
    for w in ('W1','W2','W3'):
      for method,pipes in PIPES.items():
       for pipe in pipes:
        folder=BASE/w/pipe; mf=folder/'run_manifest.json'; ledger=folder/'synthetic_ledger.parquet'
        m=json.loads(mf.read_text(encoding='utf8')); plan=m['algorithm_config']['sampling_plan']
        if (m['task'],m['window_id'],m['balance_pipeline'],m['run_status'],int(m['seed_augmentation'])) != ('LO',w,pipe,'SUCCESS',42): raise ValueError(f'Identity mismatch {w}/{pipe}')
        actual=m['algorithm_config']['algorithm']
        if not (actual == method or (method == 'SASMOTE' and actual.startswith('SASMOTE_'))) or m['release_id'] != 'LO_V3_1': raise ValueError(f'Release/method mismatch {w}/{pipe}: {actual}')
        before=m['class_counts_before']; after=m['class_counts_after']; target=plan['synthetic_target_per_class']; majority=max(map(int,before.values()))
        if sum(map(int,before.values()))!=m['rows_original'] or sum(map(int,after.values()))!=m['rows_balanced'] or not ledger.is_file(): raise ValueError(f'Counts/ledger mismatch {w}/{pipe}')
        for label in ('I/D','G','E'):
            n=int(before[label]); z=int(after[label]); generated=z-n
            if generated!=int(target[label]): raise ValueError(f'Plan mismatch {w}/{pipe}/{label}')
            fallback_count=None; fallback_rate=None; fallback_status='NOT_APPLICABLE'
            if method=='RADIUS_SMOTE' and generated:
                match=rad[(rad.window_id==w)&(rad.parent_pipeline==m['parent_pipeline'])&(rad.class_code==label)]
                if len(match)!=1: raise ValueError(f'Radius missing {w}/{pipe}/{label}')
                x=match.iloc[0]
                if x.task!='LO' or int(x.seed_augmentation)!=42 or int(x.generated_rows)!=generated or PARENT[m['parent_pipeline']]!=pipe: raise ValueError(f'Radius mismatch {w}/{pipe}/{label}')
                fallback_count=int(x.fallback_nearest_neighbour_rows); fallback_rate=float(x.fallback_nearest_neighbour_rate)
                if abs(fallback_count/generated-fallback_rate)>1e-8: raise ValueError('Radius rate mismatch')
                fallback_status='MATCHED_WINDOW_PARENT_CLASS_COUNTS'
            rows.append(dict(task='LO',window_id=w,pipeline_id=pipe,parent_pipeline=m['parent_pipeline'],balancer=method,class_code=label,n_before=n,n_target=n+int(target[label]),n_generated=generated,n_after=z,majority_to_class_ratio=majority/z if z else None,kappa_reached=None,kappa_status='UNRESOLVED_DEFINITION',fallback_count=fallback_count,fallback_rate=fallback_rate,fallback_status=fallback_status,radius_warning=bool(fallback_rate is not None and fallback_rate>0.5),sampling_seed=42,run_manifest_sha256=sha(mf)))
        inventory.append(dict(window_id=w,pipeline_id=pipe,run_id=m['run_id'],manifest_path=str(mf),manifest_sha256=sha(mf),ledger_path=str(ledger),ledger_bytes=ledger.stat().st_size,ledger_sha256=sha(ledger),ledger_hash_status='RECOMPUTED_NO_INDEPENDENT_REFERENCE'))
    if len(rows)!=108 or len(inventory)!=36: raise ValueError('Coverage mismatch')
    OUT.mkdir(parents=True,exist_ok=True); d=pd.DataFrame(rows); d.to_csv(OUT/'s2_sampling_summary_lo_seed42.csv',index=False); d.to_parquet(OUT/'s2_sampling_summary_lo_seed42.parquet',index=False)
    (OUT/'ledger_inventory.json').write_text(json.dumps({'entries':inventory},indent=2)+'\n',encoding='utf8')
    summary=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),status='PARTIAL_NOT_READY_FOR_M06_ACCEPTANCE',runs=len(inventory),rows=len(rows),radius_files=len(files),radius_rows=len(rad),radius_joined=int((d.fallback_status=='MATCHED_WINDOW_PARENT_CLASS_COUNTS').sum()),ledger_sha256='RECOMPUTED_NO_INDEPENDENT_REFERENCE',kappa='UNRESOLVED_DEFINITION',radius_parent_run_id='NOT_PRESENT_IN_RADIUS_AUDIT')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    (OUT/'README.md').write_text('# LO S2 seed 42 — partial evidence\n\nSampling plans are embedded in 36 successful LO V3.1 manifests. Radius post-hoc audit is matched on window, parent, class, seed and generated counts; it does not carry parent run ID, so this does not independently establish exact parent identity. Kappa definition remains unresolved. All ledger SHA-256 hashes were recomputed from the Drive files but have no independent reference for comparison. Do not mark M-06 complete until these limits are resolved.\n',encoding='utf8')
    (OUT/'sha256sums.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='sha256sums.txt'),encoding='utf8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
