"""Check that each TEST prefix agrees with P4 input for observable channels."""
import json
import sys
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model.data import fit_layout

root=Path(__file__).resolve().parents[1]/'downloads/vastai/CQ_V2_2_clean_grain_seed42'
checks=[]
for window in ('W1','W2','W3'):
    train=pd.read_parquet(root/'train'/window/'V0/train.parquet')
    layout=fit_layout(train,task='CQ',phase_id='P4',use_masks=True)
    del train
    source=root/'evaluation'/window/'V0'
    allnames=set(pq.ParquetFile(source/'test_P4.parquet').schema_arrow.names)
    for prefix in (1,2,3):
        target=source/f'test_P{prefix}.parquet';other=set(pq.ParquetFile(target).schema_arrow.names)
        required=['enrollment_id','CQ_label_final']+list(layout.static_columns)+list(layout.mask_static_columns)
        for phase in range(1,prefix+1):
            required += [c for c in allnames if c.endswith(f'_P{phase}') and not c.startswith('context__')]
        required=list(dict.fromkeys(required))
        missing=[c for c in required if c not in other or c not in allnames]
        if missing:raise ValueError(f'{window}/P{prefix} missing {missing}')
        a=pd.read_parquet(target,columns=required);b=pd.read_parquet(source/'test_P4.parquet',columns=required)
        diffs=[c for c in required if not a[c].equals(b[c])]
        checks.append({'window':window,'prefix':prefix,'rows':len(a),'columns':len(required),'different_columns':diffs})
        if diffs:raise ValueError(f'{window}/P{prefix} differs from P4: {diffs}')
out=Path(__file__).resolve().parents[1]/'CQ/resuilt/mantis_v0_cq_prefix_check_20261107.json'
out.write_text(json.dumps({'status':'PASS','checks':checks},indent=2)+'\n')
print(json.dumps({'status':'PASS','checks':checks},indent=2))
