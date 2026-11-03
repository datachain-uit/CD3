"""Export LO static-v2 facts, preserving recorded resource provenance."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

ROOT = Path(os.environ.get('CD3_JOBS_ROOT', 'data/Jobs')) / 'LO/organized_moved_20261029/L1_runs/S3_model/run_bundles/lo_static_v2_seed42_20261026/models'
OUT = Path('LO/resuilt/lo_static_v2_grid_seed42_20261102')
FAMILIES = ('RNN', 'LSTM', 'GRU', 'BILSTM')
KEYS = ['task','window_id','pipeline_id','model_name','seed','eval_split','phase_id']

def write(frame, name):
    frame.to_parquet(OUT / (name + '.parquet'), index=False)
    frame.to_csv(OUT / (name + '.csv'), index=False)

def load_resource(item):
    family, path = item
    m=json.loads(path.read_text(encoding='utf-8')); h=pd.read_parquet(path.parent/'train_history.parquet')
    if m.get('task')!='LO' or m.get('model_name','').upper()!=family or int(m.get('seed',-1))!=42: raise ValueError(f'wrong manifest {path}')
    if 'train_seconds' not in h or h.train_seconds.isna().any(): raise ValueError(f'missing timing {path}')
    row={k:m.get(k) for k in ('task','model_name','window_id','pipeline_id','seed','elapsed_seconds','energy_measurement_type','energy_measurement','energy_gpu_estimated_kwh','energy_gpu_run_kwh','gpu','batch_size','micro_batch_size','accumulation_steps','execution_backend','created_at_utc','runner_git_commit','data_release_id','feature_layout_sha256')}
    row['train_seconds']=float(h.train_seconds.sum())
    metrics=pd.read_parquet(path.parent/'metrics_overall.parquet')
    if len(metrics)!=8: raise ValueError(f'expected 8 metrics rows {path}')
    return row,metrics

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cells=[]; slices=[]; resources=[]; layouts=set(); commits=set(); pending=[]
    for family in FAMILIES:
        root=ROOT/family
        audit=(ROOT.parent/'audits'/'closure_seed42'/'audits_seed42'/'LO'/family/'seed=42') if family=='BILSTM' else (root/'audits'/'LO'/family/'seed=42')
        sanity=pd.read_parquet(audit/'sanity_components.parquet')
        sl=pd.read_parquet(audit/'evaluation_slices.parquet')
        if len(sanity)!=408 or len(sl)!=1224: raise ValueError(f'{family}: incorrect audit coverage')
        if sanity.duplicated(KEYS).any(): raise ValueError(f'{family}: duplicate sanity key')
        sanity['acctempo_m4']=sanity.s_perf.clip(lower=1e-3).pow(.6)*sanity.s_san_plus_v2.clip(lower=1e-3).pow(.4)
        strict=sl[sl['slice'].isin(['ALL','STRICT'])].pivot(index=KEYS,columns='slice',values='n_eval_samples').reset_index()
        strict['strict_share']=strict['STRICT']/strict['ALL']
        sanity=sanity.merge(strict[KEYS+['strict_share']],on=KEYS,validate='one_to_one')
        cells.append(sanity); slices.append(sl)
        manifests=list((root/('metadata' if family=='BILSTM' else 'runs')).rglob('run_manifest.json'))
        if len(manifests)!=51: raise ValueError(f'{family}: expected 51 manifests, found {len(manifests)}')
        pending.extend((family,path) for path in manifests)
    metrics_frames=[]
    with ThreadPoolExecutor(max_workers=12) as pool:
        for row,metrics in pool.map(load_resource,pending):
            resources.append(row); layouts.add(row['feature_layout_sha256']); commits.add(row['runner_git_commit'])
            metrics_frames.append(metrics)
            if len(resources)%25==0: print(f'resources loaded {len(resources)}/204',flush=True)
    cell=pd.concat(cells,ignore_index=True); res=pd.DataFrame(resources); sl=pd.concat(slices,ignore_index=True)
    if len(cell)!=1632 or len(res)!=204 or len(sl)!=4896 or res.duplicated(['task','model_name','window_id','pipeline_id','seed']).any(): raise ValueError('coverage failure')
    all_rows=sl[sl['slice']=='ALL']; cmp=cell.merge(all_rows,on=KEYS,validate='one_to_one',suffixes=('_cell','_slice'))
    for c in ('macro_f1','balanced_acc','s_perf','s_san_plus','acctempo_m3'):
        if not ((cmp[c+'_cell']-cmp[c+'_slice']).abs().fillna(0)<=1e-12).all(): raise ValueError(f'slice ALL mismatch {c}')
    n=sl.pivot(index=KEYS,columns='slice',values='n_eval_samples')
    if not (n['ALL']==n['STRICT']+n['OVERLAP']).all(): raise ValueError('partition count mismatch')
    metrics=pd.concat(metrics_frames,ignore_index=True)
    missing_cols=[c for c in metrics.columns if c not in cell.columns and c not in KEYS]
    cell=cell.merge(metrics[KEYS+missing_cols],on=KEYS,validate='one_to_one')
    if len(cell)!=1632: raise ValueError('metrics join coverage mismatch')
    cell['w2_strict_share']=cell['strict_share'].where(cell.window_id=='W2')
    write(cell,'lo_family_pipeline_window_phase_metrics')
    write(res,'lo_resource_per_run')
    summary=res.groupby(['model_name','pipeline_id'],as_index=False).agg(runs=('window_id','count'),train_seconds_mean=('train_seconds','mean'),train_seconds_sum=('train_seconds','sum'))
    write(summary,'lo_train_time_family_pipeline')
    means=cell.groupby(['model_name','eval_split','window_id','phase_id'],as_index=False)[['acctempo_m3','acctempo_m4','macro_f1','balanced_acc','s_perf','s_san_plus','s_san_plus_v2','s_ent','s_cal','s_eff','s_leak','c0_recall','c1_recall','c2_recall','strict_share']].mean()
    write(means,'lo_family_window_phase_mean')
    metadata={'created_at_utc':datetime.now(timezone.utc).isoformat(),'cells':len(cell),'runs':len(res),'slices_checked':len(sl),'all_slice_and_partition':'PASS','layout_sha256':sorted(str(x) for x in layouts),'runner_commits':sorted(str(x) for x in commits),'energy_measurement_types':res.energy_measurement_type.fillna('NULL').value_counts().to_dict()}
    (OUT/'summary.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    (OUT/'README.md').write_text('# LO static-v2 seed 42\n\nSource: four immutable LO static-v2 family audits and corresponding run manifests/history under Jobs/LO/.../lo_static_v2_seed42_20261026/models. One row per family, pipeline, window, split and phase. acctempo_m4 = max(s_perf,0.001)^0.6 * max(s_san_plus_v2,0.001)^0.4. STRICT share uses the matching audit slices. train_seconds sums epoch train_seconds; elapsed_seconds is the recorded wall time. Energy values and types are preserved exactly as recorded in each manifest; estimated GPU energy is not total energy or CO2. Per-class and bootstrap sources are each family audit.\n\nSee summary.json for coverage, runner commits and layout hashes.\n',encoding='utf-8')
    files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='sha256sums.txt')
    (OUT/'sha256sums.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files),encoding='utf-8')
    print(json.dumps(metadata,indent=2))

if __name__=='__main__': main()
