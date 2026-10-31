"""Compare the first epoch of current CQ PatchTST V0 with its one-epoch replay."""
import hashlib
import json
import struct
from pathlib import Path
import pandas as pd

root=Path(__file__).resolve().parents[1]
base=root/'CQ/resuilt/cq_patchtst_v0_current_seed42_r21/CQ/W1/V0/PATCHTST/seed=42'
replay=root/'CQ/resuilt/cq_patchtst_r21_replay_1epoch_20261029/CQ/W1/V0/PATCHTST/seed=42'
out=root/'CQ/resuilt/cq_patchtst_v0_current_seed42_r21_report/current_epoch1_replay_receipt.json'
fields=('runner_git_commit','static_layout_policy','batch_size','micro_batch_size','accumulation_steps',
        'seed','seed_model','seed_dataloader','data_release_id','input_download_manifest_sha256',
        'torch_version','cuda_version','gpu','learning_rate','warmup_epochs','gradient_clip_norm')
m1=json.loads((base/'run_manifest.json').read_text(encoding='utf8'))
m2=json.loads((replay/'run_manifest.json').read_text(encoding='utf8'))
checks={k:{'current':m1.get(k),'replay':m2.get(k),'matches':m1.get(k)==m2.get(k)} for k in fields}
layout1=hashlib.sha256((base/'feature_layout.json').read_bytes()).hexdigest()
layout2=hashlib.sha256((replay/'feature_layout.json').read_bytes()).hexdigest()
h1=pd.read_parquet(base/'train_history.parquet').query('epoch == 1').iloc[0]
h2=pd.read_parquet(replay/'train_history.parquet').query('epoch == 1').iloc[0]
metrics={}
for k in ('train_cross_entropy_mean_p1_p4','validation_macro_f1_mean_p1_p4','validation_cross_entropy_mean_p1_p4'):
    a,b=float(h1[k]),float(h2[k])
    metrics[k]={'current':a,'replay':b,'equal_bitwise_float64':struct.pack('!d',a)==struct.pack('!d',b)}
receipt={'task':'CQ','window':'W1','pipeline':'V0','model':'PATCHTST','seed':42,
         'scope':'current runner versus one-epoch replay; first epoch only',
         'current_layout_sha256':layout1,'replay_layout_sha256':layout2,'layout_matches':layout1==layout2,
         'contract_checks':checks,'metrics':metrics,
         'pass':layout1==layout2 and all(x['matches'] for x in checks.values()) and all(x['equal_bitwise_float64'] for x in metrics.values()),
         'limitations':'Does not compare full-run predictions or demonstrate equivalence with the older 12-column pilot or an earlier training loop.'}
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('PASS' if receipt['pass'] else 'FAIL',out)
if not receipt['pass']: raise SystemExit(1)
