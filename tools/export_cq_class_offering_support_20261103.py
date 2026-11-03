"""CQ offering/class support from real V0 cohorts, validated against R4."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
import pandas as pd

DATA=Path(os.environ.get('CQ_MODEL_INPUT_ROOT','downloads/vastai/CQ_V2_2_clean_grain_seed42'))
R4=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))/'CQ/organized_moved_20261029/L2_facts/fact_exports/cq_recurrent_allfamilies_grid_r4_20261023'
OUT=Path('CQ/resuilt/cq_class_offering_support_20261103')
CLASSES={'warning':0,'average':1,'good':2}
def main():
    rows=[]
    for w in ('W1','W2','W3'):
        for split in ('TRAIN','VALIDATION','TEST'):
            f=DATA/'train'/w/'V0'/'train.parquet' if split=='TRAIN' else DATA/'evaluation'/w/'V0'/('validation.parquet' if split=='VALIDATION' else 'test_P1.parquet')
            x=pd.read_parquet(f,columns=['enrollment_id','context__offering_id','timeline_source','CQ_label_final'])
            if x.enrollment_id.isna().any() or x.enrollment_id.duplicated().any() or x.context__offering_id.isna().any() or x.timeline_source.isna().any():raise ValueError(f'invalid grain or offering identity: {f}')
            if set(x.CQ_label_final.dropna().unique())-set(CLASSES) or x.CQ_label_final.isna().any():raise ValueError(f'invalid class: {f}')
            if split=='TEST':
                reference=x.set_index('enrollment_id').sort_index()
                for phase in ('P2','P3','P4'):
                    other=DATA/'evaluation'/w/'V0'/f'test_{phase}.parquet'
                    y=pd.read_parquet(other,columns=['enrollment_id','context__offering_id','timeline_source','CQ_label_final']).set_index('enrollment_id').sort_index()
                    if not reference.equals(y):raise ValueError(f'test cohort differs from P1: {other}')
            for label,idx in CLASSES.items():
                z=x[x.CQ_label_final==label]; groups=z.groupby(['context__offering_id','timeline_source'],dropna=False).size()
                count=len(z); n=len(groups)
                rows.append({'task':'CQ','window_id':w,'eval_split':split,'class_index':idx,'class_code':label,'n_support':count,'n_offerings_with_class':n,'top_offering_share':float(groups.max()/count) if count else None,'single_offering_flag':n<=1,'cluster_bootstrap_eligible':n>2,'offering_identity':'offering_id × timeline_source','source_path':str(f)})
            print(w,split,'rows',len(x),flush=True)
    out=pd.DataFrame(rows);r4=pd.read_parquet(R4/'cq_metrics_per_class_long.parquet')
    checks=out[out.eval_split!='TRAIN'].merge(r4[['task','window_id','eval_split','class_index','phase_id','pipeline_id','model_name','seed','n_support']],on=['task','window_id','eval_split','class_index'],validate='one_to_many')
    if len(checks)!=4896 or not checks.n_support_x.eq(checks.n_support_y).all():raise ValueError('R4 per-class support mismatch')
    OUT.mkdir(parents=True,exist_ok=True);out.to_parquet(OUT/'class_offering_support.parquet',index=False);out.to_csv(OUT/'class_offering_support.csv',index=False)
    keys=['task','window_id','eval_split','phase_id','pipeline_id','model_name','seed'];flags=checks.pivot(index=keys,columns='class_index',values='single_offering_flag').reset_index().rename(columns={0:'c0_single_offering',1:'c1_single_offering',2:'c2_single_offering'})
    if len(flags)!=1632:raise ValueError('cell flag coverage')
    flags.to_parquet(OUT/'cell_flags.parquet',index=False);flags.to_csv(OUT/'cell_flags.csv',index=False)
    note={'created_at_utc':datetime.now(timezone.utc).isoformat(),'rows':len(out),'cell_flags':len(flags),'r4_phase_support_checks':len(checks),'r4_support_match':'PASS','offering_unit':'offering_id × timeline_source','train_scope':'real V0 train per window','test_scope':'P1–P4 IDs, labels, offering and timeline exactly equal','bootstrap_eligibility_rule':'eligible iff class appears in >2 offering units; not an assertion that clustered bootstrap was run'}
    (OUT/'summary.json').write_text(json.dumps(note,indent=2)+'\n',encoding='utf8')
    (OUT/'README.md').write_text('# CQ class offering support, seed 42\n\nReal V0 model-input cohorts. Offering unit is offering_id × timeline_source. Test P1–P4 identities, labels and offering context match exactly. Per-class support was checked against all R4 cells. Bootstrap eligible means more than two offering units; clustered bootstrap was not run. See summary.json.\n',encoding='utf8')
    fs=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='sha256sums.txt');(OUT/'sha256sums.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in fs),encoding='utf8');print(json.dumps(note,indent=2))
if __name__=='__main__':main()
