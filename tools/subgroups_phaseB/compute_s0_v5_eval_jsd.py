"""Recompute subgroup TRAIN-vs-EVAL JSD using S0 locked histogram bins."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'downloads/raw_views_20261108'
OUT=ROOT/'CQ/resuilt/s0_v5_subgroup_preflight_20261122'
FLAGS = Path(os.environ.get('TEMPO_PHASEB_FLAGS_ROOT', ROOT / 'tmp/phaseB'))
VIEWS={'CQ':'CQ/phase_views_v2_2','LO':'LO/phase_views_v3_1_scored_signal_excluded'}
S0={'CQ':ROOT/'CQ/resuilt/s0_current_cq_20261108/L2_facts/task=CQ','LO':ROOT/'LO/resuilt/s0_current_lo_modal_20261108/L2_facts'}
SUBS=[('ALL','ALL'),('LEARNER','SEEN'),('LEARNER','UNSEEN'),('COURSE','SEEN'),('COURSE','UNSEEN')]


def modality(name):
    for g,p in [('video',('segment_','video_','watch_','avg_playback','fast_forward','unique_video','most_common_hour')),
                ('problem',('problem_','exercise_','score_','correct_','incorrect_','attempts_','submit_')),
                ('comment',('comment_','positive_','negative_','neutral_','avg_comment','min_comment','max_comment'))]:
        if name.startswith(p): return g
    return None


def run(task):
    hour_mapping=json.loads((OUT/'s0_hour_bin_mapping.json').read_text(encoding='utf8'))
    f=pd.read_parquet(FLAGS/f'seen_flags_{task}.parquet',columns=['window_id','split_name','phase_id','enrollment_id','seen_learner','seen_course'])
    if f.duplicated(['window_id','split_name','phase_id','enrollment_id']).any(): raise ValueError('duplicate flag keys')
    flags={(w,s,p):d.set_index('enrollment_id')[['seen_learner','seen_course']] for (w,s,p),d in f.groupby(['window_id','split_name','phase_id'],sort=False)}
    del f
    train={}
    for w in ('W1','W2','W3'):
        for k in range(1,5):
            z=pd.read_parquet(S0[task]/f'window_id={w}/phase_id=P{k}/distribution_sketch.parquet')
            z=z[(z.split=='TRAIN')&(z.value_status=='observed')]
            for row in z.itertuples():
                train[(w,k,row.feature_key)]=(np.array(json.loads(row.bin_edges_json),dtype=float),np.array(json.loads(row.bin_counts_json),dtype=float))
    features=sorted(set(k[2] for k in train))
    views=sorted((RAW/VIEWS[task]).glob('part-*.parquet'))
    if len(views)!=1: raise ValueError('expected one raw phase view')
    schema=set(pq.ParquetFile(views[0]).schema_arrow.names)
    source={}
    for feature in features:
        base='most_common_hour' if feature in ('most_common_hour_sin','most_common_hour_cos') else feature
        if base+'_P1' in schema:
            source[feature]=[(f'{base}_P{k}',k) for k in range(1,5)]
        elif base in schema:
            source[feature]=[(base,0)]
        else: raise ValueError(f'no raw source for {feature}')
    cols=list(dict.fromkeys(['window','split','enrollment_id']+[n for v in source.values() for n,_ in v]+[f'{g}_observed_mask_P{k}' for g in ('video','problem','comment') for k in range(1,5)]))
    counts={}
    inputs=[('VALIDATION',None,views)]+[('TEST',k,sorted((RAW/f'{task}_test/P{k}').glob('part-*.parquet'))) for k in range(1,5)]
    for split,only,paths in inputs:
        if not paths: raise ValueError(f'no input for {task}/{split}/{only}')
        for path in paths:
            for batch in pq.ParquetFile(path).iter_batches(batch_size=12000,columns=cols):
                frame=batch.to_pandas()
                for w in ('W1','W2','W3'):
                    d=frame[(frame.window==w)&frame.split.str.upper().eq(split)]
                    if d.empty: continue
                    for k in ([only] if only else range(1,5)):
                        fl=flags[(w,split,f'P{k}')].reindex(d.enrollment_id)
                        if fl.isna().any().any(): raise ValueError('flag join failed')
                        sels={(a,v):(np.ones(len(d),dtype=bool) if a=='ALL' else fl['seen_'+a.lower()].to_numpy()==int(v=='SEEN')) for a,v in SUBS}
                        for feature in features:
                            item=train.get((w,k,feature))
                            if item is None: continue
                            edges,_=item
                            for col,ph in source[feature]:
                                if ph>k: continue
                                values=pd.to_numeric(d[col],errors='coerce').to_numpy(dtype=float)
                                hours=values.copy() if feature=='most_common_hour_sin' else None
                                if feature=='most_common_hour_sin': values=np.sin(2*np.pi*values/24)
                                if feature=='most_common_hour_cos': values=np.cos(2*np.pi*values/24)
                                # S0's source uses notna(), then clips +/-inf to the locked edges.
                                valid=~np.isnan(values)
                                group=modality(feature)
                                if group and ph: valid &= d[f'{group}_observed_mask_P{ph}'].fillna(0).to_numpy()!=0
                                values=np.clip(values,edges[0],edges[-1])
                                # The bin boundaries are locked and strictly increasing.
                                # Assign bins once per feature; the rightmost edge belongs
                                # to the final bin, matching numpy.histogram exactly.
                                bins=np.searchsorted(edges,values,side='right')-1
                                bins=np.clip(bins,0,len(edges)-2)
                                if hours is not None:
                                    archived=hour_mapping[f'{task}|{w}']
                                    if not np.array_equal(edges,np.asarray(archived['edges'],dtype=float)):
                                        raise ValueError('hour mapping bin edges differ from S0')
                                    present=np.isfinite(hours)
                                    if not np.all((hours[present]>=0)&(hours[present]<24)&(hours[present]==np.floor(hours[present]))):
                                        raise ValueError('hour mapping requires integer hour values')
                                    bins[present]=np.asarray(archived['bin_by_hour'],dtype=int)[hours[present].astype(int)]
                                for a,v in SUBS:
                                    key=(w,split,k,a,v,feature)
                                    counts.setdefault(key,np.zeros(len(edges)-1,dtype=np.int64))[:] += np.bincount(bins[valid & sels[(a,v)]],minlength=len(edges)-1)
        print(json.dumps({'task':task,'split':split,'phase':only or 'ALL','status':'computed'}),flush=True)
    accum={}; diagnostic=[]
    for (w,split,k,a,v,feature),obs in counts.items():
        _,ref=train[(w,k,feature)]
        if not ref.sum() or not obs.sum(): continue
        p,q=ref/ref.sum(),obs/obs.sum(); mid=(p+q)/2
        jsd=.5*np.sum(np.where(p>0,p*np.log2(p/np.maximum(mid,1e-12)),0))+.5*np.sum(np.where(q>0,q*np.log2(q/np.maximum(mid,1e-12)),0))
        accum.setdefault((w,split,k,a,v),[]).append(float(jsd))
        if a=='ALL': diagnostic.append({'window_id':w,'eval_split':split,'phase_id':f'P{k}','feature_key':feature,'jsd_new':float(jsd)})
    rows=[{'task':task,'window_id':w,'eval_split':s,'phase_id':f'P{k}','subgroup_axis':a,'subgroup_value':v,
           'drift_tr_ev_jsd_mean':float(np.mean(vals)),'jsd_n_features':len(vals)} for (w,s,k,a,v),vals in accum.items()]
    out=pd.DataFrame(rows)
    ref=pd.read_parquet(ROOT/'CQ/resuilt/m13a_s0_profile_20261109_v4/s0_profile.parquet')
    keys=['task','window_id','eval_split','phase_id']
    paired=out[out.subgroup_axis.eq('ALL')].merge(ref,on=keys,validate='one_to_one',suffixes=('_new','_v4'))
    error=float((paired.drift_tr_ev_jsd_mean_new-paired.drift_tr_ev_jsd_mean_v4).abs().max())
    if len(out)!=120 or len(paired)!=24 or error>1e-10:
        diffs=[]
        for w in ('W1','W2','W3'):
            for k in range(1,5):
                z=pd.read_parquet(S0[task]/f'window_id={w}/phase_id=P{k}/drift_measures.parquet')
                z=z[z.comparison.eq('TRAIN_VS_EVAL')][['window_id','split','phase_id','feature_key','jsd_base2']].rename(columns={'split':'eval_split','jsd_base2':'jsd_v4'})
                diffs.append(z)
        diag=pd.DataFrame(diagnostic).merge(pd.concat(diffs),on=['window_id','eval_split','phase_id','feature_key'],how='outer')
        diag['abs_diff']=(diag.jsd_new-diag.jsd_v4).abs()
        diag.to_csv(OUT/f'eval_jsd_{task}_diagnostic.csv',index=False)
        raise ValueError(f'{task}: JSD ALL parity failed: rows={len(out)} all={len(paired)} max={error}')
    out.to_parquet(OUT/f'eval_jsd_{task}.parquet',index=False)
    (OUT/f'eval_jsd_{task}_qa.json').write_text(json.dumps({'status':'INTERMEDIATE_ONLY','all_parity_max_abs':error},indent=2),encoding='utf8')
    print(json.dumps({'task':task,'status':'PASS','all_parity_max_abs':error}),flush=True)


if __name__=='__main__':
    for task in (sys.argv[1:] or ['CQ','LO']): run(task)
