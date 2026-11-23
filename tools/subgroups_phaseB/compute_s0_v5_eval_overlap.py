"""Compute offering-start-before-tau overlap by subgroup from split evidence."""
import json
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'CQ/resuilt/s0_v5_subgroup_preflight_20261122'
FLAGS = Path(os.environ.get('TEMPO_PHASEB_FLAGS_ROOT', ROOT / 'tmp/phaseB'))
SUBS=[('ALL','ALL'),('LEARNER','SEEN'),('LEARNER','UNSEEN'),('COURSE','SEEN'),('COURSE','UNSEEN')]


def run(task):
    flags=pd.read_parquet(FLAGS/f'seen_flags_{task}.parquet',columns=['window_id','split_name','phase_id','enrollment_id','seen_learner','seen_course'])
    if flags.duplicated(['window_id','split_name','phase_id','enrollment_id']).any(): raise ValueError('duplicate flags')
    lookup={(w,s,p):d.set_index('enrollment_id')[['seen_learner','seen_course']] for (w,s,p),d in flags.groupby(['window_id','split_name','phase_id'],sort=False)}
    del flags
    accum={}
    source=ROOT/f'tmp/s0_v5_inputs/{task}/temporal_strict_context.parquet'
    for batch in pq.ParquetFile(source).iter_batches(batch_size=100000,columns=['window_id','split','enrollment_id','offering_start_overlap_flag']):
        d=batch.to_pandas()
        for w in ('W1','W2','W3'):
            for split in ('VALIDATION','TEST'):
                part=d[(d.window_id==w)&d.split.str.upper().eq(split)]
                if part.empty: continue
                for k in range(1,5):
                    fl=lookup[(w,split,f'P{k}')].reindex(part.enrollment_id)
                    valid=fl.notna().all(axis=1).to_numpy()
                    if not valid.any(): continue
                    ov=pd.to_numeric(part.offering_start_overlap_flag,errors='coerce').to_numpy()
                    if not np.isin(ov[valid],[0,1]).all(): raise ValueError('invalid overlap flag')
                    for a,v in SUBS:
                        sel=valid if a=='ALL' else valid & (fl['seen_'+a.lower()].to_numpy()==int(v=='SEEN'))
                        key=(w,split,f'P{k}',a,v); acc=accum.setdefault(key,[0,0])
                        acc[0]+=int(sel.sum()); acc[1]+=int(ov[sel].sum())
    rows=[{'task':task,'window_id':w,'eval_split':s,'phase_id':p,'subgroup_axis':a,'subgroup_value':v,
           'n_joined':n,'ev_train_overlap_share':z/n if n else np.nan} for (w,s,p,a,v),(n,z) in accum.items()]
    out=pd.DataFrame(rows)
    ref=pd.read_parquet(ROOT/'CQ/resuilt/m13a_s0_profile_20261109_v4/s0_profile.parquet')
    keys=['task','window_id','eval_split','phase_id']
    paired=out[out.subgroup_axis.eq('ALL')].merge(ref,on=keys,validate='one_to_one',suffixes=('_new','_v4'))
    nerr=int((paired.n_joined-paired.ev_n_enrollments).abs().max())
    err=float((paired.ev_train_overlap_share_new-paired.ev_train_overlap_share_v4).abs().max())
    if len(out)!=120 or len(paired)!=24 or nerr or err>1e-10: raise ValueError(f'{task}: overlap ALL parity failed rows={len(out)}, nerr={nerr}, max={err}')
    out.to_parquet(OUT/f'eval_overlap_{task}.parquet',index=False)
    (OUT/f'eval_overlap_{task}_qa.json').write_text(json.dumps({'status':'INTERMEDIATE_ONLY','join_n_max_abs':nerr,'all_parity_max_abs':err},indent=2),encoding='utf8')
    print(json.dumps({'task':task,'status':'PASS','all_parity_max_abs':err}),flush=True)


if __name__=='__main__':
    for task in (sys.argv[1:] or ['CQ','LO']): run(task)
