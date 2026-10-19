"""Profile historic CQ static layout on compact W1/V0 columns and a fixed sample."""
import json
import sys
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from CQ.registries import STATIC_FEATURE_CONTRACT
from tools.audit_static_columns import profile_column
from tools.probe_static_only import run, summary_table

base=ROOT/'downloads/vastai/CQ_V2_2_clean_grain_seed42'
layout=ROOT/'CQ/resuilt/cq_lstm_batch2048_full_20261018/lstm/CQ/W1/V0/LSTM/seed=42/feature_layout.json'
out=ROOT/'CQ/resuilt/cq_batch2048_closure_audit_20261019'; out.mkdir(parents=True,exist_ok=True)
cols=json.loads(layout.read_text(encoding='utf-8'))['static_columns']
paths={'TRAIN':base/'train/W1/V0/train.parquet','VALIDATION':base/'evaluation/W1/V0/validation.parquet','TEST':base/'evaluation/W1/V0/test_P1.parquet'}
frames={}
for name,path in paths.items():
    schema=pq.read_schema(path).names
    columns=list(dict.fromkeys(['CQ_label_final']+cols+[c for c in ('offering_id','course_id','course_id_code') if c in schema]))
    frame=pd.read_parquet(path,columns=columns)
    if name=='TRAIN' and len(frame)>400000: frame=frame.sample(n=400000,random_state=42)
    frames[name]=frame
    print(name,len(frame),flush=True)
train=frames['TRAIN']; evals={k:frames[k] for k in ('VALIDATION','TEST')}
fields=STATIC_FEATURE_CONTRACT['fields']
allow={k for k,v in fields.items() if v['disposition']=='IN_TENSOR'}
deny={k for k,v in fields.items() if v['disposition'] in ('EXCLUDE','CONTEXT_ONLY')}
offering=next((c for c in ('offering_id','course_id','course_id_code') if c in train),None)
records=[profile_column(c,train,'CQ_label_final',offering,evals,allow,deny) for c in cols]
details={'task':'CQ','layout':str(layout.relative_to(ROOT)),'sampling':'TRAIN random 400000 seed42, validation/test all rows',
         'offering_column_used':offering,'contract_status':STATIC_FEATURE_CONTRACT['status'], 'columns':records}
(out/'static_audit.json').write_text(json.dumps(details,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
report=run(train,evals,'CQ',layout,42); report['sampling']=details['sampling']
(out/'static_probe.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(out/'static_probe.md').write_text(summary_table(report)+'\n',encoding='utf-8')
print('OUTPUT',out,flush=True)
