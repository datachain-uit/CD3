"""Check prediction/input hashes using shell-compatible private salt, without logging it."""
from pathlib import Path
from io import BytesIO
import hashlib, json, os, tarfile
import pandas as pd

if not os.environ.get('TEMPO_PREDICTION_SALT_FILE'):
    raise ValueError('Set TEMPO_PREDICTION_SALT_FILE to the private salt file')
SALT=Path(os.environ['TEMPO_PREDICTION_SALT_FILE'])
BASE=Path('downloads/vastai/CQ_V2_2_clean_grain_seed42/evaluation/W1')
ROOT=Path('CQ/resuilt')
NAMES={1:'cq_patchtst_v1_seed42_20261031',2:'cq_patchtst_v2_seed42_20261101',3:'cq_patchtst_v3_seed42_20261101',4:'cq_patchtst_v4_seed42_20261101',5:'cq_patchtst_v5_seed42_20261101',6:'cq_patchtst_v6_seed42_20261101'}
PARENTS={0:0,1:1,2:1,3:1,4:1,5:5,6:5}
salt=SALT.read_bytes().decode('utf-8').rstrip('\n')
results=[]
for i in range(7):
    if i==0:
        pred=pd.read_parquet(ROOT/'cq_patchtst_v0_current_seed42_r21/CQ/W1/V0/PATCHTST/seed=42/predictions/test_P1.parquet',columns=['enrollment_id_hash'])
    else:
        name=NAMES[i];archive=ROOT/name/(name+'_verified.tar.gz')
        with tarfile.open(archive,'r:gz') as tar:
            member=next(x for x in tar if x.name.endswith(f'/W1/V{i}/PATCHTST/seed=42/predictions/test_P1.parquet'))
            pred=pd.read_parquet(BytesIO(tar.extractfile(member).read()),columns=['enrollment_id_hash'])
    ids=pd.read_parquet(BASE/f'V{PARENTS[i]}'/'test_P1.parquet',columns=['enrollment_id']).enrollment_id.astype('string')
    expected=set(pred.enrollment_id_hash); actual={hashlib.sha256(f'{salt}|{value}'.encode()).hexdigest() for value in ids}
    result={'pipeline':f'V{i}','window':'W1','split':'TEST','phase':'P1','input_rows':len(ids),'prediction_rows':len(pred),'matched':len(actual&expected),'exact_unique_set':len(expected)==len(pred)==len(actual)==len(ids) and expected==actual}
    results.append(result);print(json.dumps(result),flush=True)
out=ROOT/'cq_patchtst_v0_v6_full_facts_20261103'/'salt_match_w1_p1_diagnostics.json'
out.write_text(json.dumps({'salt_source':'private local file; value excluded','salt_read_rule':'UTF-8 bytes, strip LF only, preserving CR as shell command substitution','results':results},indent=2)+'\n',encoding='utf8')
