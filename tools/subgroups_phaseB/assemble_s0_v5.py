"""Assemble S0 v5 only after all independently parity-gated stages succeed."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'CQ/resuilt/s0_v5_subgroup_preflight_20261122'
V4=ROOT/'CQ/resuilt/m13a_s0_profile_20261109_v4/s0_profile.parquet'
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'CQ/resuilt/m13a_s0_profile_20261122_v5'
KEYS=['task','window_id','eval_split','phase_id','subgroup_axis','subgroup_value']
SUBS=[('LEARNER','SEEN'),('LEARNER','UNSEEN'),('COURSE','SEEN'),('COURSE','UNSEEN')]
STAGES=['eval_time','eval_masks','eval_zero','eval_overlap','eval_psi','eval_jsd']
FIELDS={
    'eval_time':['ev_n_enrollments','ev_n_offerings','ev_mean_observed_length','ev_mean_observed_fraction'],
    'eval_masks':['ev_n_cells_total','ev_n_cells_unavailable','ev_n_cells_structural_absence','ev_n_cells_observed_eligible',
                  'ev_n_cells_observed_value','ev_n_cells_observed_missing','ev_missing_rate','evpool_n_cells_total',
                  'evpool_n_cells_unavailable','evpool_n_cells_structural_absence','evpool_n_cells_observed_eligible',
                  'evpool_n_cells_observed_value','evpool_n_cells_observed_missing','evpool_missing_rate'],
    'eval_zero':['ev_n_cells_observed_zero','evpool_n_cells_observed_zero'],
    'eval_overlap':['ev_train_overlap_share'],
    'eval_psi':['drift_tr_ev_psi_mean','drift_phase_prev_psi_mean'],
    'eval_jsd':['drift_tr_ev_jsd_mean'],
}


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()


def main():
    original=pd.read_parquet(V4)
    if len(original)!=48 or original.duplicated(KEYS).any(): raise ValueError('invalid v4')
    additions=[]
    for axis,value in SUBS:
        z=original.copy(); z['subgroup_axis']=axis; z['subgroup_value']=value; additions.append(z)
    other=pd.concat(additions,ignore_index=True)
    inputs=[V4]
    for stage in STAGES:
        parts=[]
        for task in ('CQ','LO'):
            file=SRC/f'{stage}_{task}.parquet'; qa=SRC/f'{stage}_{task}_qa.json'
            if not file.is_file() or not qa.is_file(): raise FileNotFoundError(f'missing stage or QA: {stage}/{task}')
            q=json.loads(qa.read_text(encoding='utf8'))
            if q.get('status')!='INTERMEDIATE_ONLY': raise ValueError(f'invalid stage QA {qa}')
            inputs.extend([file,qa]); parts.append(pd.read_parquet(file))
        stage_data=pd.concat(parts,ignore_index=True)
        if len(stage_data)!=240 or stage_data.duplicated(KEYS).any(): raise ValueError(f'{stage}: wrong coverage')
        keep=stage_data[~stage_data.subgroup_axis.eq('ALL')][KEYS+FIELDS[stage]]
        other=other.merge(keep,on=KEYS,how='left',validate='one_to_one',suffixes=('','__new'),sort=False)
        for field in FIELDS[stage]:
            other[field]=other.pop(field+'__new')
            reason=field+'_reason'
            if reason in other:
                other[reason]=np.where(other[field].notna(),None,np.where(other.ev_n_enrollments.eq(0),'SLICE_EMPTY',np.where((field=='drift_phase_prev_psi_mean')&other.phase_id.eq('P1'),'NO_PREVIOUS_PHASE','NOT_COMPUTED')))
    support=SRC/'subgroup_support_preflight.parquet'; inputs.append(support)
    counts=pd.read_parquet(support)[KEYS+['n_eval']]
    other=other.merge(counts,on=KEYS,how='left',validate='one_to_one',sort=False)
    if not other.ev_n_enrollments.eq(other.n_eval).all(): raise ValueError('subgroup sample counts disagree')
    other=other.drop(columns=['n_eval'])
    expected=set(original.columns)
    if set(other.columns)!=expected: raise ValueError(f'v4 schema mismatch extra={set(other.columns)-expected} missing={expected-set(other.columns)}')
    result=pd.concat([original,other[original.columns]],ignore_index=True)
    # Preserve the physical dtype of the registered ALL reference. In
    # particular, all-null numeric reason columns must stay float64: changing
    # them to object changes the downstream feature-selection registry.
    for col in original.columns:
        if result[col].dtype != original[col].dtype:
            result[col]=result[col].astype(original[col].dtype)
    pd.testing.assert_frame_equal(result.iloc[:48].reset_index(drop=True),original.reset_index(drop=True),check_dtype=True,check_exact=True)
    if len(result)!=240 or result.duplicated(KEYS).any(): raise ValueError('invalid final coverage')
    required=['ev_n_enrollments','ev_n_offerings','ev_mean_observed_length','ev_mean_observed_fraction','ev_missing_rate','ev_train_overlap_share','drift_tr_ev_psi_mean','drift_tr_ev_jsd_mean']
    bad={c:int(result[c].isna().sum()) for c in required if result[c].isna().any()}
    if bad: raise ValueError(f'required metrics NULL: {bad}')
    OUT.mkdir(parents=True,exist_ok=True)
    result.to_parquet(OUT/'s0_profile.parquet',index=False)
    result.to_csv(OUT/'s0_profile.csv',index=False)
    persisted=pd.read_parquet(OUT/'s0_profile.parquet')
    pd.testing.assert_frame_equal(persisted.iloc[:48].reset_index(drop=True),original.reset_index(drop=True),check_dtype=True,check_exact=True)
    summary={'status':'S0_V5_READY_FOR_REVIEW','rows':len(result),'columns':len(result.columns),'all_rows':48,'all_v4_exact':True,
             'source_sha256':{str(f):digest(f) for f in inputs},'output_sha256':digest(OUT/'s0_profile.parquet')}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__': main()
