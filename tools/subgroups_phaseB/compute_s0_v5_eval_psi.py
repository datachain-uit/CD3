"""Compute phase-matched PSI on each subgroup with the S0 v4 convention."""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'downloads/raw_views_20261108'
DATA = ROOT / 'tmp/s0_v5_inputs'
OUT = ROOT / 'CQ/resuilt/s0_v5_subgroup_preflight_20261122'
FLAGS = Path(os.environ.get('TEMPO_PHASEB_FLAGS_ROOT', ROOT / 'tmp/phaseB'))
VIEWS = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}
PHASE = re.compile(r'^(.*)_P([1-4])$')
SUBS = [('ALL', 'ALL'), ('LEARNER', 'SEEN'), ('LEARNER', 'UNSEEN'), ('COURSE', 'SEEN'), ('COURSE', 'UNSEEN')]


def psi(ref, cmp):
    rn, cn = ref[~np.isnan(ref)], cmp[~np.isnan(cmp)]
    edges = np.unique(np.quantile(rn, np.linspace(.1, .9, 9))) if len(rn) else np.array([])
    def dist(v, n):
        counts = np.bincount(np.searchsorted(edges, v, side='right'), minlength=len(edges)+1).astype(float) if len(v) else np.zeros(len(edges)+1)
        return np.append(counts, n-len(v))/max(n, 1)
    p, q = np.clip(dist(rn, len(ref)), 1e-6, None), np.clip(dist(cn, len(cmp)), 1e-6, None)
    p, q = p/p.sum(), q/q.sum()
    return float(np.sum((p-q)*np.log(p/q)))


def run(task):
    f = pd.read_parquet(FLAGS / f'seen_flags_{task}.parquet', columns=['window_id', 'split_name', 'phase_id', 'enrollment_id', 'seen_learner', 'seen_course'])
    if f.duplicated(['window_id', 'split_name', 'phase_id', 'enrollment_id']).any(): raise ValueError('duplicate flags')
    flags = {(w,s,p): d.set_index('enrollment_id')[['seen_learner','seen_course']] for (w,s,p),d in f.groupby(['window_id','split_name','phase_id'], sort=False)}
    del f
    views = sorted((RAW / VIEWS[task]).glob('part-*.parquet'))
    tests = {k: sorted((RAW / f'{task}_test/P{k}').glob('part-*.parquet')) for k in range(1,5)}
    if len(views)!=1 or any(len(v)!=1 for v in tests.values()): raise ValueError('Expected one parquet file per raw view')
    view = views[0]
    schema = pq.ParquetFile(view).schema_arrow.names
    input_schema = pq.ParquetFile(DATA / task / 'evaluation/W1/V0/validation.parquet').schema_arrow.names
    stems = [n.removeprefix('missing__') for n in input_schema if n.startswith('missing__') and n.removeprefix('missing__') in schema]
    bases = sorted({PHASE.match(s).group(1) for s in stems if PHASE.match(s)})
    accum = {}
    for base in bases:
        cols = [f'{base}_P{k}' for k in range(1,5)]
        if not all(c in schema for c in cols): continue
        v = pq.read_table(view, columns=['window','split','enrollment_id']+cols).to_pandas()
        tt = {k: pq.read_table(tests[k][0], columns=['window','split','enrollment_id',cols[k-1]]).to_pandas() for k in range(1,5)}
        for window in ('W1','W2','W3'):
            tr = v[(v.window==window)&(v.split=='train')]
            va = v[(v.window==window)&(v.split=='validation')]
            te = {k: tt[k][(tt[k].window==window)&(tt[k].split=='test')] for k in range(1,5)}
            selected = {}
            for split, frames in [('VALIDATION',{k:va for k in range(1,5)}),('TEST',te)]:
                for k,d in frames.items():
                    fl = flags[(window,split,f'P{k}')].reindex(d.enrollment_id)
                    if fl.isna().any().any(): raise ValueError(f'flags mismatch {task}/{window}/{split}/P{k}')
                    vals = pd.to_numeric(d[cols[k-1]], errors='coerce').to_numpy(dtype=float)
                    for axis,value in SUBS:
                        mask = np.ones(len(d), dtype=bool) if axis=='ALL' else fl['seen_'+axis.lower()].to_numpy()==int(value=='SEEN')
                        selected[(split,k,axis,value)] = vals[mask]
                for k in range(1,5):
                    ref = pd.to_numeric(tr[cols[k-1]], errors='coerce').to_numpy(dtype=float)
                    for axis,value in SUBS:
                        cur = selected[(split,k,axis,value)]
                        key = (window,split,f'P{k}',axis,value)
                        a = accum.setdefault(key, {'tr_ev': [], 'prev': []})
                        if len(cur): a['tr_ev'].append(psi(ref,cur))
                        if k>1:
                            prev = selected[(split,k-1,axis,value)]
                            if len(cur) and len(prev): a['prev'].append(psi(prev,cur))
        print(json.dumps({'task':task,'feature':base,'status':'computed'}), flush=True)
    rows=[]
    for (w,s,p,a,v), z in accum.items():
        rows.append({'task':task,'window_id':w,'eval_split':s,'phase_id':p,'subgroup_axis':a,'subgroup_value':v,
                     'drift_tr_ev_psi_mean':float(np.mean(z['tr_ev'])) if z['tr_ev'] else np.nan,
                     'drift_phase_prev_psi_mean':float(np.mean(z['prev'])) if z['prev'] else np.nan,
                     'psi_n_features':len(z['tr_ev'])})
    out=pd.DataFrame(rows)
    ref=pd.read_parquet(ROOT/'CQ/resuilt/m13a_s0_profile_20261109_v4/s0_profile.parquet')
    keys=['task','window_id','eval_split','phase_id']
    joined=out[out.subgroup_axis.eq('ALL')].merge(ref,on=keys,validate='one_to_one',suffixes=('_new','_v4'))
    errors={}
    for c in ('drift_tr_ev_psi_mean','drift_phase_prev_psi_mean'):
        x,y=joined[c+'_new'],joined[c+'_v4']
        if x.isna().ne(y.isna()).any(): raise ValueError(f'ALL NULL mismatch {c}')
        errors[c]=float((x-y).abs().max())
    if len(out)!=120 or max(errors.values())>1e-10: raise ValueError(f'{task}: PSI ALL parity failed: {errors}')
    out.to_parquet(OUT/f'eval_psi_{task}.parquet',index=False)
    (OUT/f'eval_psi_{task}_qa.json').write_text(json.dumps({'status':'INTERMEDIATE_ONLY','parity':errors},indent=2),encoding='utf8')
    print(json.dumps({'task':task,'status':'PASS','parity':errors}),flush=True)


if __name__=='__main__':
    for task in (sys.argv[1:] or ['CQ','LO']): run(task)
