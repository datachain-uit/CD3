import os as _os
# Machine roots come from environment variables (no machine paths in the repository).
REPO = _os.environ.get('TEMPO_REPO_ROOT', '.')
WORK = _os.environ.get('TEMPO_WORK_ROOT', '.')
AUDIT44 = _os.environ.get('TEMPO_AUDIT44_ROOT', '.')
WORKD = _os.environ.get('TEMPO_DELIVERY_WORK_ROOT', '.')
import sys, json
sys.path.insert(0, f'{WORKD}/code')
from pathlib import Path
import pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
import registry
OUT = Path(f'{WORKD}/l2_slices_and_per_class_3seeds_20261126')
man = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
U = registry.units()
R4S = Path(f'{REPO}/CQ/resuilt/cq_r4_slices_reconciled_20261103/cq_evaluation_slices.parquet')
R4D = Path(f'{WORKD}/src/CQ/seed42/F1_recurrent/cq_recurrent_allfamilies_grid_r4_20261023')
LOA = Path(f'{REPO}/CQ/resuilt/input/results/R21_evidence_20261031/LO/audit_seed42')
def local(task, model, seed, table):
    if seed == 42 and model in registry.REC:
        if task == 'CQ':
            f = {'evaluation_slices': R4S, 'metrics_per_class': R4D / 'cq_metrics_per_class_long.parquet', 'bootstrap_metrics_per_class': R4D / 'cq_bootstrap_metrics_per_class_long.parquet'}.get(table)
            if f is None: return None
            t = pq.read_table(f); return t.filter(pc.equal(t['model_name'], model))
        if table == 'cohort_slice_status': return None
        d = LOA / ('audits_seed42/LO/BILSTM/seed=42' if model == 'BILSTM' else f'{model}/LO/{model}/seed=42')
        return pq.read_table(d / f'{table}.parquet')
    return pa.concat_tables([pq.read_table(Path(d) / f'{table}.parquet') for d, _ in U[(task, model, seed)]['dirs']], promote_options='permissive')
full = {t: pq.read_table(OUT / f'{t}.parquet') for t in registry.TABLES}
bad = 0; checked = 0
for u in man['units']:
    for t in registry.TABLES:
        src = local(u['task'], u['model_name'], u['seed'], t)
        o = full[t].filter(pc.and_(pc.and_(pc.equal(full[t]['task'], u['task']), pc.equal(full[t]['model_name'], u['model_name'])), pc.equal(full[t]['seed'], u['seed'])))
        if src is None:
            ok = (o.num_rows == 0 and u['tables'][t]['status'] == 'NOT_AVAILABLE')
        else:
            ok = o.num_rows == src.num_rows == u['tables'][t]['rows'] and o.select(src.column_names).equals(src) and u['tables'][t]['status'] == 'OK'
            # added cols constant checks
            ok = ok and set(pc.unique(o['source_package']).to_pylist()) == set(sf['source_package'] for sf in u['tables'][t]['source_files'])
        checked += 1
        if not ok:
            bad += 1; print('FAIL', u['task'], u['model_name'], u['seed'], t, o.num_rows, None if src is None else src.num_rows)
print('checked', checked, 'bad', bad)
# parts reproduce full
pm = json.loads((OUT / 'parts/parts_manifest.json').read_text())
import hashlib
for t in set(p['table'] for p in pm['parts']):
    ps = [pq.read_table(OUT / 'parts' / p['file']) for p in pm['parts'] if p['table'] == t]
    cat = pa.concat_tables(ps)
    f = full[t]
    key = ['task', 'seed']
    # same rows regardless of order: compare sorted by a stable key via counts per unit and equality per task-seed
    ok = cat.num_rows == f.num_rows
    for task in ('CQ', 'LO'):
        for s in (42, 43, 44):
            a = f.filter(pc.and_(pc.equal(f['task'], task), pc.equal(f['seed'], s)))
            b = cat.filter(pc.and_(pc.equal(cat['task'], task), pc.equal(cat['seed'], s)))
            ok = ok and a.equals(b)
    print('parts', t, 'ok', ok, cat.num_rows)
for p in pm['parts']:
    h = hashlib.sha256((OUT / 'parts' / p['file']).read_bytes()).hexdigest()
    assert h == p['sha256'] and (OUT / 'parts' / p['file']).stat().st_size == p['bytes'] and p['bytes'] < 10_000_000
print('parts sha ok')
# paths leak scan
import re
for f in list(OUT.rglob('*.json')):
    s = f.read_text(encoding='utf-8')
    for pat in ('D:/', 'C:/', 'D:\\\\', 'C:\\\\', _os.environ.get('USERNAME', '<user>'), 'audit44', 'tmp_aud', 'Source_code'):
        if pat in s: print('PATH LEAK', f.name, pat)
for t in registry.TABLES:
    names = full[t].schema.names
    print(t, full[t].num_rows, 'cols', len(names), 'first cols', names[:4], 'last', names[-2:], 'dupe cols', len(names) - len(set(names)))
