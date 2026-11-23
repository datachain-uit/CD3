"""Infer exact historical hour-sine histogram bins and prove uniqueness.

Use integer counts of each hour and archived ALL histogram as constraints.
No model, subgroup or outcome score is used. Ambiguous mappings are rejected.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.optimize import Bounds, LinearConstraint, milp

ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'downloads/raw_views_20261108'
OUT=ROOT/'CQ/resuilt/s0_v5_subgroup_preflight_20261122'
VIEW={'CQ':'CQ/phase_views_v2_2','LO':'LO/phase_views_v3_1_scored_signal_excluded'}
S0={'CQ':ROOT/'CQ/resuilt/s0_current_cq_20261108/L2_facts/task=CQ','LO':ROOT/'LO/resuilt/s0_current_lo_modal_20261108/L2_facts'}
result={}
for task in ('CQ','LO'):
    cols=['window','split']+[f'{x}_P{k}' for x in ('most_common_hour','video_observed_mask') for k in range(1,5)]
    view=pq.read_table(next((RAW/VIEW[task]).glob('part-*.parquet')),columns=cols).to_pandas()
    tests={k:pq.read_table(next((RAW/f'{task}_test/P{k}').glob('part-*.parquet')),columns=cols).to_pandas() for k in range(1,5)}
    for window in ('W1','W2','W3'):
        hist=[]; inputs=[]; edges0=None
        for k in range(1,5):
            sketch=pd.read_parquet(S0[task]/f'window_id={window}/phase_id=P{k}/distribution_sketch.parquet')
            for split in ('VALIDATION','TEST'):
                d=view if split=='VALIDATION' else tests[k]
                d=d[(d.window==window)&(d.split==split.lower())]
                s=sketch[(sketch.split==split)&(sketch.feature_key=='most_common_hour_sin')&(sketch.value_status=='observed')].iloc[0]
                edges=np.array(json.loads(s.bin_edges_json)); expected=np.array(json.loads(s.bin_counts_json),dtype=int)
                if edges0 is None: edges0=edges
                if not np.array_equal(edges0,edges): raise ValueError(f'{task}/{window}: changed bin edges')
                count=np.zeros(24,dtype=int)
                for phase in range(1,k+1):
                    x=d[f'most_common_hour_P{phase}'].to_numpy(dtype=float)
                    valid=(d[f'video_observed_mask_P{phase}'].fillna(0).to_numpy()!=0)&np.isfinite(x)
                    x=x[valid]
                    if not np.all((x>=0)&(x<24)&(x==np.floor(x))): raise ValueError('noninteger hour')
                    count+=np.bincount(x.astype(int),minlength=24)
                hist.append(expected); inputs.append(count)
        choices=[]
        for h in range(24):
            x=float(np.sin(2*np.pi*h/24)); candidates=[x]
            lo=hi=x
            for _ in range(3):
                lo=np.nextafter(lo,-np.inf); hi=np.nextafter(hi,np.inf); candidates.extend((lo,hi))
            choices.append(sorted({int(np.clip(np.searchsorted(edges0,np.clip(v,edges0[0],edges0[-1]),side='right')-1,0,len(edges0)-2)) for v in candidates}))
        variables=[(h,b) for h in range(24) for b in choices[h]]
        matrix=[]; target=[]
        for h in range(24):
            matrix.append([int(h==i) for i,_ in variables]); target.append(1)
        for counts,expected in zip(inputs,hist):
            for b in range(len(expected)):
                matrix.append([int(counts[h]) if bb==b else 0 for h,bb in variables]); target.append(int(expected[b]))
        A=np.asarray(matrix,dtype=float); y=np.asarray(target,dtype=float)
        constraint=LinearConstraint(A,y,y)
        fit=milp(np.zeros(len(variables)),integrality=np.ones(len(variables)),bounds=Bounds(0,1),constraints=constraint,options={'time_limit':30})
        if not fit.success: raise ValueError(f'{task}/{window}: no exact mapping: {fit.message}')
        mapping={h:b for j,(h,b) in enumerate(variables) if fit.x[j]>.5}
        ambiguous=[]
        for h in range(24):
            if len(choices[h])<2 or not any(c[h] for c in inputs): continue
            selected=variables.index((h,mapping[h])); bounds_hi=np.ones(len(variables)); bounds_hi[selected]=0
            alt=milp(np.zeros(len(variables)),integrality=np.ones(len(variables)),bounds=Bounds(np.zeros(len(variables)),bounds_hi),constraints=constraint,options={'time_limit':30})
            if alt.success: ambiguous.append(h)
        if ambiguous: raise ValueError(f'{task}/{window}: histogram mapping ambiguous for hours {ambiguous}')
        key=f'{task}|{window}'
        result[key]={'edges':edges0.tolist(),'bin_by_hour':[mapping[h] for h in range(24)],'constraints':len(hist),'ambiguous_observed_hours':ambiguous}
        print(json.dumps({'task':task,'window':window,'histograms':len(hist),'status':'EXACT_UNIQUE_FOR_OBSERVED_HOURS'}),flush=True)
(OUT/'s0_hour_bin_mapping.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
