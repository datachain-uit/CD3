"""Create a non-release B.5 diagnostic input with eight NULL dtypes restored."""
import hashlib,json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026/meta_dataset_seed_agg.parquet'
SOURCE=ROOT/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r1/meta_dataset_seed_agg.parquet'
OUT=ROOT/'tmp/s0_v5_inputs/b5_dtype_diagnostic'
COLS=['ev_n_cells_total_reason','ev_n_cells_unavailable_reason','ev_n_cells_structural_absence_reason',
      'ev_n_cells_observed_eligible_reason','ev_n_cells_observed_value_reason','ev_n_cells_observed_missing_reason',
      'ev_missing_rate_reason','ev_train_overlap_share_reason']

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    if OUT.exists(): raise FileExistsError(f'diagnostic already exists: {OUT}')
    ref=pd.read_parquet(BASE); data=pd.read_parquet(SOURCE)
    changed=[]
    for c in COLS:
        if str(ref[c].dtype)!='float64' or data[c].notna().any():
            raise ValueError(f'{c} is not an all-null column with float64 reference')
        data[c]=pd.to_numeric(data[c],errors='raise').astype(ref[c].dtype); changed.append(c)
    all_rows=data[(data.subgroup_axis=='ALL')&(data.subgroup_value=='ALL')]
    for c in COLS:
        if str(all_rows[c].dtype)!=str(ref[c].dtype) or all_rows[c].notna().any(): raise ValueError(f'{c}: dtype mismatch remains')
    OUT.mkdir(parents=True)
    target=OUT/'seed_agg_dtype_diagnostic.parquet'; data.to_parquet(target,index=False)
    check=pd.read_parquet(target,columns=COLS)
    if any(str(check[c].dtype)!='float64' or check[c].notna().any() for c in COLS): raise ValueError('persisted dtype mismatch')
    (OUT/'diagnostic_manifest.json').write_text(json.dumps({'status':'DIAGNOSTIC_ONLY_NOT_A_RELEASE','rows':len(data),'changed_all_null_dtypes':changed,
        'source_sha256':sha(SOURCE),'reference_sha256':sha(BASE),'diagnostic_sha256':sha(target)},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'rows':len(data),'changed_columns':len(changed),'output':str(target),'diagnostic_only':True}),flush=True)

if __name__=='__main__':main()
