"""Read-only trial join of R4 baselines; NOT a complete meta-release assembler."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
import numpy as np
import pandas as pd

ROOT=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))/'CQ/organized_moved_20261029/L2_facts/fact_exports/cq_recurrent_allfamilies_grid_r4_20261023'
OUT=Path('CQ/resuilt/cq_meta_r4_trial_20261103')
PARENTS={'V0':'V0','V1':'V1','V2':'V1','V3':'V1','V4':'V1','V5':'V5','V6':'V5','V7':'V5','V8':'V5','V9':'V9','V10':'V9','V11':'V9','V12':'V9','V13':'V13','V14':'V13','V15':'V13','V16':'V13'}
KEY=['task','window_id','model_name','seed','eval_split','phase_id']
def main():
    f=ROOT/'cq_family_pipeline_window_phase_metrics.parquet';df=pd.read_parquet(f)
    if len(df)!=1632 or df.duplicated(KEY+['pipeline_id']).any() or set(df.pipeline_id)!=set(PARENTS) or set(df.seed)!={42}:raise ValueError('unexpected R4 coverage')
    df['parent_pipeline_id']=df.pipeline_id.map(PARENTS)
    baseline=df[df.pipeline_id=='V0'][KEY+['s_perf']].rename(columns={'s_perf':'s_perf_baseline_v0'})
    parent=df[KEY+['pipeline_id','s_perf']].rename(columns={'pipeline_id':'parent_pipeline_id','s_perf':'s_perf_parent_imputer'})
    joined=df.merge(baseline,on=KEY,validate='many_to_one').merge(parent,on=KEY+['parent_pipeline_id'],validate='many_to_one')
    joined['delta_total_s_perf']=joined.s_perf-joined.s_perf_baseline_v0
    joined['delta_imputation_s_perf']=joined.s_perf_parent_imputer-joined.s_perf_baseline_v0
    joined['delta_balancing_s_perf']=joined.s_perf-joined.s_perf_parent_imputer
    delta=(joined.delta_total_s_perf-joined.delta_imputation_s_perf-joined.delta_balancing_s_perf).abs().max()
    m4=(joined.acctempo_m4-(joined.s_perf.clip(lower=.001)**.6*joined.s_san_plus_v2.clip(lower=.001)**.4)).abs().max()
    if delta>1e-9 or m4>1e-4:raise ValueError('trial numerical QA failure')
    joined['row_status']='INCOMPLETE_REQUIRED_META_INPUTS';joined['scenario']='hybrid'
    OUT.mkdir(parents=True,exist_ok=True);joined.to_parquet(OUT/'cq_r4_meta_join_trial.parquet',index=False)
    result={'created_at_utc':datetime.now(timezone.utc).isoformat(),'status':'TRIAL_ONLY_NOT_OFFICIAL_MDS','input_rows':len(df),'trial_rows':len(joined),'input_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'unique_keys':'PASS','v0_and_parent_join':'PASS','delta_s_perf_max_error':float(delta),'acctempo_m4_max_error':float(m4),'seed_values':[42],'row_status_counts':joined.row_status.value_counts().to_dict(),'skipped_unassigned':'NOT_EVALUATED_NO_OFFICIAL_ASSEMBLER','required_inputs_not_joined':['F0','S0 Z_D/Z_DQ/Z_T','Z_M','full subgroup/cohort facts','other seeds'],'official_qa01_qa24':'NOT_EVALUATED'}
    (OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    (OUT/'README.md').write_text('# CQ R4 trial join — NOT an official meta-release\n\nChecks R4 unique keys, V0 and parent joins, S_perf delta decomposition and M4 calculation. It does not implement the full assembler, QA01–QA24, SKIPPED/UNASSIGNED assignment, F0, S0, Z_M or other seeds. All rows remain INCOMPLETE_REQUIRED_META_INPUTS; do not use as final MDS.\n',encoding='utf8')
    files=sorted(x for x in OUT.iterdir() if x.is_file() and x.name!='sha256sums.txt');(OUT/'sha256sums.txt').write_text(''.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.name+'\n' for x in files),encoding='utf8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
