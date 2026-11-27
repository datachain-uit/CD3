"""Step 1: for each of the 1,836 runs pick the source of every accepted prediction file the way tools/subgroups_phaseB/run_unit.py does
(loose file of an official package first, else the best-ranked tar), and reduce to the run directory / tar that holds the predictions."""
import os, re, sys, pandas as pd
from pathlib import Path
OUT = Path(os.environ.get('QA13_DIR', '.'))
cat = pd.read_parquet(os.environ['PRED_CATALOG_PARQUET'])
asg = pd.read_parquet(os.environ['S3_SEED_ASSIGN_PARQUET'])[['path', 'rel', 'seed']]
asg = asg[asg.seed.astype(str).isin(['42','43','44'])]
MP = {r.path: f"{r.path.split('/L1_runs/S3_model/')[0]}/L1_runs/S3_model/seed={int(r.seed)}/{r.rel}" for r in asg.itertuples()}
TRUNC = {'lo_patchtst_seed44_V2_host40077.tar', 'LO_static_v2_BILSTM.tar'}
PREFER = ['primary/release=LO_STATIC_V2', 'primary/family=PATCHTST', 'cq_recurrent_batch2048_seed42', 'cq_lstm_batch2048_full', 'cq_rnn_historical_layout_batch2048', 'mantis_v2_seed', 'staging_incoming']
DENY = ['pilot', 'determinism', 'replay', 'ablation', '/vastai/', 'vastai_runs', 'matched_historical', 'baseline_drive', 'nvml_historical', 'cohort_audit', 'host_backups']
def rank(p):
    if any(d in p for d in DENY): return 2
    return 0 if any(x in p for x in PREFER) else 1
rows = []
for (t, m, s), g in cat.groupby(['task', 'model_name', 'seed']):
    need = {}
    for r in g.itertuples():
        old = r.path if r.kind == 'tar' else f'{t}/L1_runs/S3_model/{r.path}'
        new = MP.get(old)
        if new is None: continue
        need.setdefault((r.window_id, r.pipeline_id, r.split, r.phase_id), []).append((r.kind, new, getattr(r, 'member', None)))
    runs = {}
    for k, srcs in need.items():
        cands = sorted((x for x in srcs if x[0] == 'loose'), key=lambda x: rank(x[1]))
        pick = None
        if cands and (rank(cands[0][1]) < 2 or not any(x[0] == 'tar' and rank(x[1]) < 2 for x in srcs)):
            pick = cands[0]
        else:
            best = sorted((x for x in srcs if x[0] == 'tar' and Path(x[1]).name not in TRUNC), key=lambda x: rank(x[1])) or sorted((x for x in srcs if x[0] == 'tar'), key=lambda x: rank(x[1]))
            if best: pick = best[0]
        n_alt = len({(x[0], x[1]) for x in srcs})
        runs.setdefault(k[:2], []).append((k, pick, n_alt, srcs))
    for (w, v), lst in runs.items():
        alts = {}
        for _, _, _, srcs in lst:
            for kind, path, _ in srcs:
                rp = re.sub(r'/predictions/[^/]+\.parquet$', '', path) if kind == 'loose' else path
                alts.setdefault((kind, rp), set()).add(1)
        picks = [p for _, p, _, _ in lst if p]
        pk = set()
        for kind, path, _ in picks:
            pk.add((kind, re.sub(r'/predictions/[^/]+\.parquet$', '', path) if kind == 'loose' else path))
        pickset = {p for _, p in pk}
        others = sorted((rank(p), kind, p) for (kind, p) in alts if p not in pickset)
        rows.append(dict(other_sources='|'.join(f'{r}:{k}:{p}' for r, k, p in others), n_other_sources=len(others), best_other_rank=min([r for r, _, _ in others], default=''), pick_rank=min(rank(p) for _, p in pk), task=t, model=m, seed=s, window=w, pipeline=v, n_pred_keys=len(lst), n_picked=len(picks), kinds='|'.join(sorted({k for k, _ in pk})),
                         packages='|'.join(sorted(p for _, p in pk)), n_packages=len(pk)))
d = pd.DataFrame(rows)
d.to_csv(OUT / 'work_pred_sources_by_run.csv', index=False)
print(len(d)); print(d.groupby(['task', 'model', 'seed']).agg(runs=('window', 'size'), np_=('n_packages', 'max'), full=('n_picked', lambda x: (x == 8).sum()), kinds=('kinds', lambda x: x.value_counts().to_dict())).to_string())
