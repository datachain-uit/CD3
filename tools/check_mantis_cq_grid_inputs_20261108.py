"""Read-only schema/identity preflight for all CQ F3 imputer and S2 inputs."""
import hashlib
import json
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "downloads/vastai/CQ_V2_2_clean_grain_seed42"
OUT = ROOT / "CQ/resuilt/mantis_grid_readiness_20261108"
PARENTS = {"V2":"V1","V3":"V1","V4":"V1","V6":"V5","V7":"V5","V8":"V5",
           "V10":"V9","V11":"V9","V12":"V9","V14":"V13","V15":"V13","V16":"V13"}
release=json.loads((DATA/'download_manifest.json').read_text(encoding='utf8'))
assert release['release_id']=='CQ_V2_2' and release['data_release_id']=='sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045'
rows=[]
for w in ('W1','W2','W3'):
    for n in range(1,17):
        v=f'V{n}'; parent=PARENTS.get(v,v); balanced=v!=parent
        train=DATA/'train'/w/v/('balanced_train.parquet' if balanced else 'train.parquet')
        validation=DATA/'evaluation'/w/parent/'validation.parquet'
        tests=[DATA/'evaluation'/w/parent/f'test_P{i}.parquet' for i in range(1,5)]
        paths=[train,validation,*tests]
        for path in paths:
            if not path.is_file(): raise FileNotFoundError(path)
        train_file=pq.ParquetFile(train); fields=set(train_file.schema_arrow.names)
        required={'enrollment_id','CQ_label_final'}|({'synthetic_id'} if balanced else set())
        if not required.issubset(fields): raise ValueError(f'{train}: missing {required-fields}')
        for path in paths[1:]:
            f=set(pq.ParquetFile(path).schema_arrow.names)
            if not {'enrollment_id','CQ_label_final'}.issubset(f): raise ValueError(f'{path}: missing identifiers or labels')
        if balanced:
            sample=next(train_file.iter_batches(batch_size=64,columns=['enrollment_id','synthetic_id'])).to_pydict()
            if any(x is not None for x in sample['synthetic_id']): raise ValueError(f'{v}/{w}: first real rows unexpected')
            last=train_file.read_row_group(train_file.num_row_groups-1,columns=['enrollment_id','synthetic_id'])
            tail=last.slice(max(0,len(last)-64),min(len(last),64)).to_pydict()
            if not all(a is not None and a==b for a,b in zip(tail['synthetic_id'],tail['enrollment_id'])):
                raise ValueError(f'{v}/{w}: synthetic sample identifiers invalid')
        rows.append({'window':w,'pipeline':v,'parent':parent,'train_rows':train_file.metadata.num_rows,
                     'train_path':str(train.relative_to(DATA)),'train_bytes':train.stat().st_size,
                     'validation_rows':pq.ParquetFile(validation).metadata.num_rows,
                     'test_rows':pq.ParquetFile(tests[-1]).metadata.num_rows,
                     'balanced':balanced,'sampled_synthetic_ids':'PASS' if balanced else 'NOT_APPLICABLE'})
assert len(rows)==48
OUT.mkdir(parents=True,exist_ok=True)
result={'status':'PATH_SCHEMA_AND_ID_SAMPLE_PASS','cells':len(rows),'release_id':release['release_id'],
        'manifest_sha256':hashlib.sha256((DATA/'download_manifest.json').read_bytes()).hexdigest(),
        'scope':'sampled ID/schema preflight only; full prefix parity and cache hash checks remain per cell', 'cells_detail':rows}
(OUT/'input_preflight.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps({'status':result['status'],'cells':len(rows),'output':str(OUT/'input_preflight.json')}))
