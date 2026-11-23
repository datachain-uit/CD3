"""Diagnose S0 historical histogram binning at hour=16, without changing facts."""
import glob,json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'downloads/raw_views_20261108'
VIEW={'CQ':'CQ/phase_views_v2_2','LO':'LO/phase_views_v3_1_scored_signal_excluded'}
S0={'CQ':ROOT/'CQ/resuilt/s0_current_cq_20261108/L2_facts/task=CQ','LO':ROOT/'LO/resuilt/s0_current_lo_modal_20261108/L2_facts'}
for task in ('CQ','LO'):
    cols=['window','split']+[f'{x}_P{k}' for x in ('most_common_hour','video_observed_mask') for k in range(1,5)]
    view=pq.read_table(next((RAW/VIEW[task]).glob('part-*.parquet')),columns=cols).to_pandas()
    tests={k:pq.read_table(next((RAW/f'{task}_test/P{k}').glob('part-*.parquet')),columns=cols).to_pandas() for k in range(1,5)}
    for w in ('W1','W2','W3'):
        for k in range(1,5):
            sketch=pd.read_parquet(S0[task]/f'window_id={w}/phase_id=P{k}/distribution_sketch.parquet')
            for split in ('VALIDATION','TEST'):
                d=view if split=='VALIDATION' else tests[k]
                d=d[(d.window==w)&(d.split==split.lower())]
                s=sketch[(sketch.split==split)&(sketch.feature_key=='most_common_hour_sin')&(sketch.value_status=='observed')]
                if len(s)!=1: raise ValueError(f'unexpected sketch rows {task}/{w}/{split}/P{k}')
                edges=np.array(json.loads(s.iloc[0].bin_edges_json)); ref=np.array(json.loads(s.iloc[0].bin_counts_json))
                h0=np.zeros(len(ref),dtype=int); h1=h0.copy()
                for phase in range(1,k+1):
                    x=d[f'most_common_hour_P{phase}'].to_numpy(dtype=float)
                    valid=d[f'video_observed_mask_P{phase}'].fillna(0).to_numpy()!=0
                    raw=np.sin(2*np.pi*x/24)
                    adjusted=np.where(x==16,np.nextafter(raw,np.inf),raw)
                    h0+=np.histogram(np.clip(raw[valid],edges[0],edges[-1]),bins=edges)[0]
                    h1+=np.histogram(np.clip(adjusted[valid],edges[0],edges[-1]),bins=edges)[0]
                print(json.dumps({'task':task,'window':w,'phase':k,'split':split,'unadjusted_l1':int(abs(h0-ref).sum()),'adjusted_l1':int(abs(h1-ref).sum())}),flush=True)
