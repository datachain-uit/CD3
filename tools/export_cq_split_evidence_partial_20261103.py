"""Reconstruct CQ block and strict facts; never infer offering-start overlap."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,io,json,zipfile,os
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

DATA=Path(os.environ.get('CQ_MODEL_INPUT_ROOT','downloads/vastai/CQ_V2_2_clean_grain_seed42'))
REG=Path('CQ/resuilt/input/results/R21_evidence_20261031/registry_v1_3/split_registry.json')
LABELS=Path('CQ/resuilt/cq_labels_v1.zip')
OUT=Path('CQ/resuilt/cq_split_evidence_partial_20261103')
ASSIGN={'A':('W1','TRAIN'),'B':('W1','VALIDATION'),'C':('W1','TEST'),'D':('W2','VALIDATION'),'E':('W2','TEST'),'F':('W3','VALIDATION'),'G':('W3','TEST')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source(w,s,phase='P1'):
    return DATA/'train'/w/'V0'/'train.parquet' if s=='TRAIN' else DATA/'evaluation'/w/'V0'/('validation.parquet' if s=='VALIDATION' else f'test_{phase}.parquet')
def main():
    reg=json.loads(REG.read_text(encoding='utf8'));blocks=[];durations=[];strict=[]
    for block,(w,split) in ASSIGN.items():
        f=source(w,split);x=pd.read_parquet(f,columns=['enrollment_id','context__offering_id','timeline_source','context__duration_days','CQ_label_final'])
        if x.enrollment_id.isna().any() or x.enrollment_id.duplicated().any():raise ValueError(f'{f}: bad grain')
        if len(x)!=reg['tasks']['CQ']['blocks'][block]:raise ValueError(f'{block}: registry mismatch')
        units=x.groupby(['context__offering_id','timeline_source'],dropna=False).agg(n=('enrollment_id','size'),dur_min=('context__duration_days','min'),dur_max=('context__duration_days','max')).reset_index()
        if ((units.dur_min!=units.dur_max)&units.dur_min.notna()&units.dur_max.notna()).any():raise ValueError(f'{block}: duration varies within offering')
        units['block']=block;durations.append(units)
        counts=x.CQ_label_final.value_counts().to_dict()
        blocks.append({'task':'CQ','block':block,'window_source':w,'split_source':split,'enrollments':len(x),'offering_units':len(units),'warning':int(counts.get('warning',0)),'average':int(counts.get('average',0)),'good':int(counts.get('good',0))})
        print('block',block,len(x),'units',len(units),flush=True)
    for w in ('W1','W2','W3'):
      for split in ('VALIDATION','TEST'):
       for phase in ('P1','P2','P3','P4'):
        f=source(w,split,phase);col='context__temporal_strict_'+phase;x=pd.read_parquet(f,columns=['enrollment_id',col]);v=pd.to_numeric(x[col],errors='coerce')
        if x.enrollment_id.duplicated().any() or not v.isin([0,1]).all():raise ValueError(f'invalid strict {f}')
        strict.append({'task':'CQ','window_id':w,'eval_split':split,'phase_id':phase,'n_eval':len(x),'n_strict':int(v.sum()),'strict_share':float(v.mean()),'overlap_share':float(1-v.mean())})
    r4root=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))/'CQ/organized_moved_20261029/L2_facts/fact_exports/cq_recurrent_allfamilies_grid_r4_20261023';r4=pd.read_parquet(r4root/'cq_family_pipeline_window_phase_metrics.parquet');s=pd.DataFrame(strict)
    check=r4[r4.window_id=='W2'].merge(s[s.window_id=='W2'],on=['window_id','eval_split','phase_id'],validate='many_to_one')
    if len(check)!=544 or not np.allclose(check.w2_strict_share,check.strict_share,atol=1e-12,rtol=0):raise ValueError('strict W2 does not match R4')
    all_units=pd.concat(durations,ignore_index=True);duration=[]
    for timeline,g in all_units.groupby('timeline_source',dropna=False):
        valid=g.dur_min.dropna();total=int(g.n.sum());duration.append({'timeline_source':timeline,'offering_units':len(g),'valid_duration_units':len(valid),'duration_p50_days':float(valid.quantile(.5)) if len(valid) else None,'duration_p90_days':float(valid.quantile(.9)) if len(valid) else None,'duration_max_days':float(valid.max()) if len(valid) else None,'enrollments':total,'enrollments_gt_270':int(g.loc[g.dur_min>270,'n'].sum()),'enrollment_share_gt_270':float(g.loc[g.dur_min>270,'n'].sum()/total) if total else None})
    with zipfile.ZipFile(LABELS) as z:
        name=next(n for n in z.namelist() if n.endswith('.parquet'));frame=pq.read_table(io.BytesIO(z.read(name)),columns=['CQ_label_final','cq_exclusion_reason','cq_active_event_any']).to_pandas()
    label={'rows':len(frame),'label_counts_including_null':{str(k):int(v) for k,v in frame.CQ_label_final.value_counts(dropna=False).items()},'exclusion_reason_counts_including_null':{str(k):int(v) for k,v in frame.cq_exclusion_reason.value_counts(dropna=False).items()},'zero_activity_rows':int(frame.cq_active_event_any.eq(0).sum()),'zero_activity_warning_removed':int(frame.cq_exclusion_reason.eq('v3_sampled_zero_activity_warning_removal').sum())}
    OUT.mkdir(parents=True,exist_ok=True)
    for name,data in [('blocks',blocks),('strict_by_phase',strict),('offering_duration',duration)]:pd.DataFrame(data).to_csv(OUT/(name+'.csv'),index=False);pd.DataFrame(data).to_parquet(OUT/(name+'.parquet'),index=False)
    summary={'created_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PARTIAL_MISSING_OFFERING_START_OVERLAP_AND_RAW_POPULATION','release_id':'CQ_V2_2','registry_source_sha256':sha(REG),'labels_zip_sha256':sha(LABELS),'calendar':reg['calendar'],'labels_artifact_population':label,'w2_strict_r4_rows_checked':len(check),'w2_strict_r4':'PASS','ev_train_overlap_share':None,'ev_train_overlap_reason':'offering_start_date is not present in supplied model inputs','raw_population':'NOT_AVAILABLE_FROM_MODEL_INPUT_OR_LABEL_ARTIFACT'}
    (OUT/'split_registry_cq_v2_2.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    (OUT/'README.md').write_text('# CQ split evidence — partial\n\nBlock A–G cohorts reconstructed from real V0 input and validated against R21 split registry. Unit = offering_id × timeline_source. Labels and exclusions counted from cq_labels_v1.zip; this is artifact population, not the raw population. Temporal STRICT is per phase; W2 checked against all 544 R4 cells. ev_train_overlap_share based on offering start is NOT AVAILABLE and is not substituted with cutoff overlap. Raw population before label artifact is not available here.\n',encoding='utf8')
    fs=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='sha256sums.txt');(OUT/'sha256sums.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in fs),encoding='utf8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
