"""Join verified aggregate M-07 evidence from downloaded V3.1 artifacts."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import pandas as pd
BASE=Path('LO/resuilt'); OUT=BASE/'lo_split_evidence_20261106'
REG=BASE/'split_registry_v3_1_scored_signal_excluded_overlap_audit_v1'; LABEL=BASE/'final_score_contract_audit_v3_1_scored_signal_excluded'
def read(b,sub):
 files=list((b/sub).glob('*.parquet'))
 if len(files)!=1:raise ValueError(f'Expected one parquet {b/sub}: {len(files)}')
 return pd.read_parquet(files[0])
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return h.hexdigest()
def main():
 split=read(REG,'split_registry'); block=read(REG,'block_label_audit'); dur=read(REG,'duration_summary'); overlap=read(REG,'temporal_overlap_audit_v1'); exclusion=read(LABEL,'exclusion_reason_summary')
 if set(split.window_id)!={'W1','W2','W3'} or not split.qa22_ok.all() or set(split.task)!={'LO'}:raise ValueError('Split contract failed')
 if set(split.ev_train_overlap_definition)!={'test_offering_start_date_lt_date(tau_w)'}:raise ValueError('unexpected overlap definition')
 reconstructed=pd.read_csv(OUT/'block_class_counts.csv').drop_duplicates('block').set_index('block').block_n.to_dict()
 print('block audit columns',list(block.columns),flush=True)
 count_column='n_enrollments' if 'n_enrollments' in block.columns else ('enrollment_count' if 'enrollment_count' in block.columns else None)
 if count_column:
  for row in block.to_dict('records'):
   if row['rolling_block'] in reconstructed and int(row[count_column])!=int(reconstructed[row['rolling_block']]):raise ValueError(f'Block mismatch {row["rolling_block"]}')
 split.to_csv(OUT/'split_registry_source.csv',index=False);block.to_csv(OUT/'block_label_audit_source.csv',index=False);dur.to_csv(OUT/'duration_summary.csv',index=False);overlap.to_csv(OUT/'temporal_overlap_source.csv',index=False);exclusion.to_csv(OUT/'exclusion_reason_summary.csv',index=False)
 files=['split_registry_v3_1_scored_signal_excluded_overlap_audit_v1.zip','final_score_contract_audit_v3_1_scored_signal_excluded.zip']; src={x:sha(BASE/x) for x in files}
 missing=['raw_pre_label_population_independent_evidence','slice_exclusion_reason_summary_A_T1_T2_T3','source_release_identity_independently_verified']
 summary={'status':'PARTIAL','created_at_utc':datetime.now(timezone.utc).isoformat(),'source_archives_sha256':src,'task':'LO','split_version':list(split.split_version.unique()),'qa22_all_pass':bool(split.qa22_ok.all()),'overlap_definition':'test_offering_start_date_lt_date(tau_w)','block_count_check':'PASS' if count_column else 'NOT_CHECKED_NO_RECOGNIZED_COLUMN','exclusion_status_count':len(exclusion),'exclusion_total':int(exclusion.enrollment_count.sum()),'missing':missing,'excluded_older_long_offering_audit':'manifest points to pre-V3.1 registry'}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8');(OUT/'README.md').write_text('# LO M-07 split evidence — partial\n\nA–G and STRICT computed from V0 real inputs; split and duration aggregates from downloaded V3.1 registry, exclusion reasons from final-score contract audit. ev_train_overlap_share is TEST offering-start-before-tau, not one minus P1 STRICT. Raw pre-label population and exclusion reasons by slice remain unverified. Older long-offering audit points to a prior registry and is excluded.\n',encoding='utf8');(OUT/'sha256sums.txt').write_text(''.join(sha(f)+'  '+f.name+'\n' for f in sorted(OUT.iterdir()) if f.is_file() and f.name!='sha256sums.txt'),encoding='utf8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
