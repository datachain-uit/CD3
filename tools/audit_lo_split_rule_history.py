"""Audit LO historical static-layout mismatch and full split-rule input values."""
from collections import Counter
from pathlib import Path
import json
import sys

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.data import fit_layout
from tools.audit_static_columns import audit, registry_allowlist

data = ROOT/'downloads/vastai/LO_V3_1_clean_grain_seed42'
runs = ROOT/'LO/resuilt/vastai_f2_batch2048_seed42_20261013'
out = ROOT/'LO/resuilt/static_contract_history_20261019'
out.mkdir(parents=True, exist_ok=True)
layouts = sorted(runs.rglob('feature_layout.json'))
records=[]
for path in layouts:
    obj=json.loads(path.read_text(encoding='utf-8'))
    records.append({'path':str(path.relative_to(ROOT)), 'present':'split_rule_version' in obj['static_columns']})
files=[]
for window in ('W1','W2','W3'):
    for parent in ('V0','V1','V5','V9','V13'):
        files.append((window,parent,'train',data/'train'/window/parent/'train.parquet'))
        for name in ('validation','test_P1','test_P2','test_P3','test_P4'):
            files.append((window,parent,name,data/'evaluation'/window/parent/(name+'.parquet')))
    for pipeline in ('V2','V3','V4','V6','V7','V8','V10','V11','V12','V14','V15','V16'):
        files.append((window,pipeline,'balanced_train',data/'train'/window/pipeline/'balanced_train.parquet'))
results=[]
for window,parent,split,path in files:
    pf=pq.ParquetFile(path)
    if 'split_rule_version' not in pf.schema_arrow.names:
        raise ValueError(f'Missing split_rule_version: {path}')
    counts=Counter()
    for batch in pf.iter_batches(columns=['split_rule_version'],batch_size=65536):
        counts.update(batch.column(0).to_pylist())
    results.append({'window':window,'parent':parent,'split':split,'rows':pf.metadata.num_rows,
                    'value_counts':{str(k):v for k,v in counts.items()}, 'path':str(path.relative_to(ROOT))})
    print(window,parent,split,dict(counts),flush=True)
sample=next(pq.ParquetFile(data/'train/W1/V0/train.parquet').iter_batches(batch_size=10000)).to_pandas()
new_layout=fit_layout(sample,task='LO',phase_id='P4',use_masks=True)
strict_audit=audit(sample,'LO',{},registry_allowlist('LO'))
flags=strict_audit['summary']['flag_counts']
strict_pass=flags['DENIED']==0 and flags['UNLISTED']==0
summary={'task':'LO','release':'LO_V3_1','historical_layouts_total':len(records),
         'historical_layouts_with_split_rule_version':sum(r['present'] for r in records),
         'current_fit_layout_contains_split_rule_version':'split_rule_version' in new_layout.static_columns,
         'current_layout_scope':'first 10000 rows LO W1/V0 input; model.data.fit_layout current code',
         'current_strict_audit':strict_audit['summary'], 'current_strict_pass':strict_pass,
         'value_scan_scope':'full rows in 3 windows x 5 parents x train/validation/test P1-P4 plus all 36 balanced TRAIN files',
         'files':results,'historical_layouts':records,
         'interpretation':'Historical checkpoints unchanged; constant per file does not by itself prove identical across train and eval or no influence.'}
(out/'history_audit.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print('SUMMARY',len(records),summary['historical_layouts_with_split_rule_version'],len(results),flush=True)
