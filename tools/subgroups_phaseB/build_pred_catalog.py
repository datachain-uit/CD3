import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import WORK
import collections
import json
import re

import pandas as pd

MODELS = ['RNN', 'LSTM', 'GRU', 'BILSTM', 'PATCHTST', 'MANTIS_V2']
rows = []
for line in open(f'{WORK}/phaseB/pred_scan.jsonl', encoding='utf-8'):
    r = json.loads(line)
    tar = r['path']
    task_tar = tar.split('/')[0]
    seed_tar = re.search(r'seed[_=]?(\d+)', tar.split('S3_model/')[-1])
    for name, size in r['members']:
        if 'predictions/' not in name or not name.endswith('.parquet'):
            continue
        m = re.search(r'(?:(CQ|LO)/)?(W\d)/(V\d+)/([A-Z][A-Z0-9_]*)/seed=(\d+)/predictions/(validation|test)_(P\d)\.parquet$', name)
        if m:
            task = m.group(1) or task_tar
            window, pipe, model, seed, split, phase = m.group(2), m.group(3), m.group(4), int(m.group(5)), m.group(6), m.group(7)
        else:
            m = re.search(r'runs/(W\d)/(V\d+)/predictions/(validation|test)_(P\d)\.parquet$', name)
            if not m or not seed_tar:
                continue
            task, window, pipe, split, phase = task_tar, m.group(1), m.group(2), m.group(3), m.group(4)
            model, seed = 'MANTIS_V2', int(seed_tar.group(1))
        rows.append({'task': task, 'window_id': window, 'pipeline_id': pipe, 'model_name': model, 'seed': seed, 'split': split.upper(), 'phase_id': phase,
                     'bytes': size, 'tar': tar, 'tar_status': r['status'], 'member': name})
d = pd.DataFrame(rows)
d.to_parquet(f'{WORK}/phaseB/pred_files.parquet', index=False)
print('prediction file entries', len(d), 'distinct (run,split,phase)', d.drop_duplicates(['task', 'window_id', 'pipeline_id', 'model_name', 'seed', 'split', 'phase_id']).shape[0])
ok = d[d.bytes > 0]
key = ['task', 'window_id', 'pipeline_id', 'model_name', 'seed']
per_tar = ok.groupby(key + ['tar']).apply(lambda g: g[['split', 'phase_id']].drop_duplicates().shape[0], include_groups=False).rename('n_files').reset_index()
best = per_tar.sort_values('n_files', ascending=False).drop_duplicates(key)
full = best[best.n_files == 8]
cov = pd.DataFrame([(t, m, s) for t in ('CQ', 'LO') for m in MODELS for s in (42, 43, 44)], columns=['task', 'model_name', 'seed'])
cov['runs_expected'] = 51
cov['runs_all8_files'] = cov.apply(lambda r: int(((full.task == r.task) & (full.model_name == r.model_name) & (full.seed == r.seed)).sum()), axis=1)
cov['runs_partial'] = cov.apply(lambda r: int(((best.task == r.task) & (best.model_name == r.model_name) & (best.seed == r.seed) & (best.n_files < 8)).sum()), axis=1)
cov['runs_none'] = cov.runs_expected - cov.runs_all8_files - cov.runs_partial
print(cov.to_string())
print('totals: complete', int(cov.runs_all8_files.sum()), 'partial', int(cov.runs_partial.sum()), 'none', int(cov.runs_none.sum()), 'of', int(cov.runs_expected.sum()))
cov.to_csv(f'{WORK}/phaseB/pred_coverage.csv', index=False)
best.to_csv(f'{WORK}/phaseB/pred_best_tar_per_run.csv', index=False)
