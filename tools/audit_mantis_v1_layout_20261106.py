"""Compare CQ V1 Mantis input layout with locked PatchTST and test-prefix data."""
from pathlib import Path
import json,hashlib,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from model.data import fit_layout
BASE=Path('downloads/vastai/CQ_V2_2_clean_grain_seed42')
ADAPTER=Path('CQ/resuilt/mantis_v2_v1_adapter_20261106.json')
PATCH=Path('CQ/resuilt/cq_patchtst_v0_current_seed42_r21/CQ/W1/V0/PATCHTST/seed=42/feature_layout.json')
OUT=Path('CQ/resuilt/mantis_v2_v1_layout_audit_20261106.json')
def main():
 train=next(pq.ParquetFile(BASE/'train/W1/V1/train.parquet').iter_batches(batch_size=100)).to_pandas()
 layout=fit_layout(train,task='CQ',phase_id='P4',use_masks=True);saved=json.loads(PATCH.read_text());adapter=json.loads(ADAPTER.read_text())
 names=list(layout.dynamic_bases)+[f'missing__{x}' for x in layout.dynamic_bases if f'missing__{x}_P1' in train.columns]+list(layout.mask_phase_bases)+['phase_fraction','delta_t']
 testroot=BASE/'evaluation/W1/V1';p4=testroot/'test_P4.parquet';results=[]
 for k in range(1,5):
  static=list(layout.static_columns)+list(layout.mask_static_columns)
  dyn=[f'{base}_P{p}' for p in range(1,k+1) for base in layout.dynamic_bases]
  mask=[f'missing__{base}_P{p}' for p in range(1,k+1) for base in layout.dynamic_bases if f'missing__{base}_P{p}' in train.columns]
  phases=[f'{base}_P{p}' for p in range(1,k+1) for base in layout.mask_phase_bases]
  cols=['enrollment_id','CQ_label_final']+static+dyn+mask+phases
  a=pd.read_parquet(testroot/f'test_P{k}.parquet',columns=cols).sort_values('enrollment_id').reset_index(drop=True)
  b=pd.read_parquet(p4,columns=cols).sort_values('enrollment_id').reset_index(drop=True)
  mismatches={c:int((~((a[c]==b[c])|(a[c].isna()&b[c].isna()))).sum()) for c in cols}; mismatches={x:y for x,y in mismatches.items() if y}
  results.append({'phase':f'P{k}','rows_prefix':len(a),'rows_p4':len(b),'columns_compared':len(cols),'mismatch_columns':mismatches,'all_equal':len(a)==len(b) and not mismatches})
  print('prefix',k,'rows',len(a),'mismatched_columns',len(mismatches),flush=True)
 fields=['dynamic_bases','mask_dynamic_columns','mask_phase_bases','static_columns','mask_static_columns']
 report={'scope':'CQ W1 V1, local V1 files and current PatchTST V0 layout; mask availability checked via full P1–P4 test input','dynamic_features':len(layout.dynamic_bases),'missing_indicators_per_phase':sum(x.endswith('_P1') for x in layout.mask_dynamic_columns),'phase_masks':len(layout.mask_phase_bases),'time_channels':2,'dynamic_tensor_channels':len(names),'static_values':len(layout.static_columns),'static_masks':len(layout.mask_static_columns),'static_tensor_channels':len(layout.static_columns)+len(layout.mask_static_columns),'adapter_names_exact_order':names==adapter['channel_names'],'layout_matches_patchtst_v0':{x:list(getattr(layout,x))==saved[x] for x in fields},'test_prefix_vs_p4':results,'note':'Comparison uses local downloaded inputs; full TRAIN row content on Modal not independently hashed in this audit. Dynamic data prefix equality does not prove architecture output parity.'}
 OUT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
