"""Export S2 manifest facts without inferring unavailable per-class fallback."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
import pandas as pd

BASE=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))/'CQ/organized_moved_20261029/L1_runs/S2_augmentation/provenance_seed42'
HIST=Path('CQ/resuilt/input/results/R21_evidence_20261031/CQ/S2_seed42/ledger_inventory.json')
OUT=Path('CQ/resuilt/cq_s2_sampling_seed42_partial_20261103')
PIPES={'CDSMOTE':['V2','V6','V10','V14'],'SASMOTE':['V3','V7','V11','V15'],'RADIUS_SMOTE':['V4','V8','V12','V16']}
CLASSES={'warning':0,'average':1,'good':2}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    prior=json.loads(HIST.read_text(encoding='utf8'));inventory={(x['window'],x['pipeline']):x for x in prior['entries']};rows=[]; inv=[]
    if len(inventory)!=36:raise ValueError('prior inventory incomplete')
    for w in ('W1','W2','W3'):
      for method,pipes in PIPES.items():
       for pipe in pipes:
        folder=BASE/w/pipe; mf=folder/'run_manifest.json';ledger=folder/'synthetic_ledger.parquet';m=json.loads(mf.read_text(encoding='utf8'));previous=inventory[(w,pipe)]
        if sha(mf)!=previous.get('manifest_sha256') or not ledger.is_file() or ledger.stat().st_size!=previous.get('ledger_bytes'):raise ValueError(f'provenance mismatch {w}/{pipe}')
        if m.get('task')!='CQ' or m.get('window_id')!=w or m.get('balance_pipeline')!=pipe or int(m.get('seed_augmentation',m.get('seed',-1)))!=42 or m.get('run_status')!='SUCCESS':raise ValueError(f'wrong run {w}/{pipe}')
        before=m['class_counts_before'];after=m['class_counts_after'];plan=m['algorithm_config']['sampling_plan'];target=plan['synthetic_target_per_class'];audit=m.get('algorithm_audit') or {};majority=max(map(int,before.values()))
        if sum(map(int,before.values()))!=int(m['rows_original']) or sum(map(int,after.values()))!=int(m['rows_balanced']):raise ValueError(f'count mismatch {w}/{pipe}')
        for label,idx in CLASSES.items():
            n=int(before[label]);z=int(after[label]);generated=z-n;expected=int(target[label]);
            if generated!=expected:raise ValueError(f'sampling mismatch {w}/{pipe}/{label}')
            rows.append({'task':'CQ','window_id':w,'pipeline_id':pipe,'balancer':method,'class_index':idx,'class_code':label,'n_train_before':n,'n_target':n+expected,'n_generated':generated,'n_after':z,'achieved_expansion_ratio':z/n if n else None,'achieved_majority_to_class_ratio':majority/z if z else None,'kappa_reached':None,'kappa_status':'UNRESOLVED_DEFINITION','fallback_count':None,'fallback_rate':None,'fallback_class_status':'NOT_RECORDED_PER_CLASS' if method=='RADIUS_SMOTE' and generated else 'NOT_APPLICABLE','fallback_overall_count':audit.get('fallback_nearest_neighbour_rows') if method=='RADIUS_SMOTE' else None,'fallback_overall_rate':audit.get('fallback_nearest_neighbour_rate') if method=='RADIUS_SMOTE' else None,'sampling_seed':42,'run_manifest_sha256':sha(mf)})
        inv.append({'window_id':w,'pipeline_id':pipe,'manifest_relative_path':f'W{w[-1]}/{pipe}/run_manifest.json','manifest_sha256':sha(mf),'ledger_relative_path':f'W{w[-1]}/{pipe}/synthetic_ledger.parquet','ledger_sha256_previously_recorded':previous.get('ledger_sha256'),'ledger_bytes':previous.get('ledger_bytes'),'ledger_hash_status':'RECORDED_PRIOR_INVENTORY_NOT_REHASHED'})
    frame=pd.DataFrame(rows)
    radius_root=Path('CQ/resuilt/cq_radius_fallback_modal_20261103')
    radius_files=sorted(radius_root.rglob('part-00000.parquet'))
    if len(radius_files)!=12:raise ValueError('Expected 12 original Radius audit files')
    radius=pd.concat([pd.read_parquet(p) for p in radius_files],ignore_index=True)
    if len(radius)!=24 or radius.duplicated(['window_id','balance_pipeline','class_code']).any():raise ValueError('Radius class audit coverage mismatch')
    for rec in radius.to_dict('records'):
        manifest=json.loads((BASE/rec['window_id']/rec['balance_pipeline']/'run_manifest.json').read_text(encoding='utf8'))
        if (rec['task']!='CQ' or rec['release_id']!='CQ_V2_2' or int(rec['seed_augmentation'])!=42 or
            rec['data_release_parent_run_id']!=manifest['parent_imputation_run_id'] or
            int(rec['generated_rows'])!=int(manifest['algorithm_config']['sampling_plan']['synthetic_target_per_class'][rec['class_code']])):
            raise ValueError('Radius audit source does not match S2 manifest')
        mask=(frame.window_id==rec['window_id']) & (frame.pipeline_id==rec['balance_pipeline']) & (frame.class_code==rec['class_code'])
        if mask.sum()!=1:raise ValueError('Radius audit join is not one-to-one')
        frame.loc[mask,'fallback_count']=int(rec['fallback_nearest_neighbour_rows'])
        frame.loc[mask,'fallback_rate']=float(rec['fallback_nearest_neighbour_rate'])
        frame.loc[mask,'fallback_class_status']='VERIFIED_POSTHOC_RADIUS_AUDIT'
    frame['warning_flags']=frame.fallback_rate.map(lambda v:'RADIUS_FALLBACK_GT_0_50' if pd.notna(v) and v>0.5 else '')
    if len(frame)!=108 or len(inv)!=36:raise ValueError('coverage failure')
    OUT.mkdir(parents=True,exist_ok=True);frame.to_csv(OUT/'s2_sampling_summary_cq_seed42.csv',index=False);frame.to_parquet(OUT/'s2_sampling_summary_cq_seed42.parquet',index=False)
    (OUT/'ledger_inventory.json').write_text(json.dumps({'source_inventory_sha256':sha(HIST),'entries':inv},indent=2)+'\n',encoding='utf8')
    summary={'created_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PARTIAL_NOT_READY_FOR_M06_ACCEPTANCE','rows':len(frame),'runs':len(inv),'per_class_radius_fallback':'24_VERIFIED_POSTHOC_AUDIT_ROWS','kappa_definition':'UNRESOLVED','ledger_hashes':'PRIOR_INVENTORY_NOT_REHASHED'};(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    (OUT/'README.md').write_text('# CQ S2 sampling seed 42 — PARTIAL\n\nCounts and targets come from 36 successful run manifests. Radius fallback uses 24 original post-hoc audit rows, matched to parent imputation run IDs and generation targets. `kappa_reached` remains null pending confirmation of its definition. Ledger SHA values come from the prior R21 inventory and were not rehashed here; manifest SHA values were checked. This draft does not close M-06.\n',encoding='utf8')
    files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='sha256sums.txt');(OUT/'sha256sums.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in files),encoding='utf8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
