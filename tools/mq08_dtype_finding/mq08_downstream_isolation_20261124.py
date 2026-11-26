"""Exploratory real-data isolation: no registered full-grid rerun."""
from pathlib import Path
import json,sys
import pandas as pd
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tmp/metamodel_handoff_20261121'))
from metamodel import experiment as E
base=root/'CQ/resuilt/mm_runs_phaseC_r2_20261123/full_main_cal_time';out=root/'CQ/resuilt/mq08_downstream_isolation_20261124';out.mkdir(parents=True,exist_ok=True)
raw=json.loads((base/'mm_config.json').read_text());raw.update(protocols=['E1-B'],learners=['L3'],extra_learners=[],feature_sets=['FS3'],n_trials=2,bootstrap_b=20,learner_seeds=[0,1],hypotheses=[])
cfg=E.MMConfig(**raw);meta=pd.read_parquet(root/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_dataset_seed_agg.parquet')
print('starting original MQ08',flush=True);a=E.run_experiment(meta,cfg,out/'original',write=False)
original=E._negative_control
def nop(*args,**kwargs):return {'mean_regret_permuted':float('nan'),'harm_rate_permuted':float('nan')}
E._negative_control=nop
try:
 print('starting disabled MQ08',flush=True);b=E.run_experiment(meta,cfg,out/'disabled',write=False)
finally:E._negative_control=original
results={}
for name in a:
 if name=='mm_negative_control':continue
 aa=a[name].copy();bb=b[name].copy()
 if name=='mm_run_registry':aa=aa.drop(columns=['elapsed_s_total'],errors='ignore');bb=bb.drop(columns=['elapsed_s_total'],errors='ignore')
 try:pd.testing.assert_frame_equal(aa.reset_index(drop=True),bb.reset_index(drop=True),check_exact=True);results[name]='IDENTICAL'
 except AssertionError as exc:results[name]='DIFFERENT: '+str(exc)[:500]
print(json.dumps(results,indent=2),flush=True)
(out/'comparison.json').write_text(json.dumps({'design':'EXPLORATORY_REDUCED_E1B_L3_FS3_2trials_2seeds_B20','original_control_vs_noop':results,'excluded':'mm_negative_control; elapsed_s_total in registry','any_difference':any(v!='IDENTICAL' for v in results.values())},indent=2)+'\n')
