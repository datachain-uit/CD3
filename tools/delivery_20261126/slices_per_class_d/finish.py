import os as _os
# Machine roots come from environment variables (no machine paths in the repository).
REPO = _os.environ.get('TEMPO_REPO_ROOT', '.')
WORK = _os.environ.get('TEMPO_WORK_ROOT', '.')
AUDIT44 = _os.environ.get('TEMPO_AUDIT44_ROOT', '.')
WORKD = _os.environ.get('TEMPO_DELIVERY_WORK_ROOT', '.')
import json, hashlib
from pathlib import Path
import pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc

OUT = Path(f'{WORKD}/l2_slices_and_per_class_3seeds_20261126')
LIMIT = 9_500_000
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()

man = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
TABLES = ['evaluation_slices', 'metrics_per_class', 'bootstrap_metrics_per_class', 'cohort_slice_status']
parts_dir = OUT / 'parts'
parts_dir.mkdir(exist_ok=True)
for p in parts_dir.glob('*'): p.unlink()
parts = []; not_split = {}
for t in TABLES:
    f = OUT / f'{t}.parquet'
    size = f.stat().st_size
    if size <= LIMIT:
        not_split[t] = dict(bytes=size, reason='whole file is below 10 MB (limit used for splitting: 9,500,000 bytes); no parts written')
        continue
    tab = pq.read_table(f)
    for task in ('CQ', 'LO'):
        for seed in (42, 43, 44):
            sub = tab.filter(pc.and_(pc.equal(tab['task'], task), pc.equal(tab['seed'], seed)))
            name = f'{t}__{task}__seed{seed}.parquet'
            pq.write_table(sub, parts_dir / name, compression='zstd', row_group_size=20000)
            sz = (parts_dir / name).stat().st_size
            assert sz < 10_000_000, (name, sz)
            parts.append(dict(table=t, file=name, task=task, seed=seed, rows=sub.num_rows, bytes=sz, sha256=sha(parts_dir / name)))
    # verify
    tot = sum(p['rows'] for p in parts if p['table'] == t)
    assert tot == tab.num_rows, (t, tot, tab.num_rows)
(parts_dir.parent / 'parts_manifest.json').write_text(json.dumps(dict(
    convention='same as seed_level_parts/parts_manifest.json of the meta release (list of parts with file, rows, bytes, sha256); parts split by task x seed; concatenating all parts of a table in the listed order reproduces the full parquet row-for-row',
    split_rule='task x seed; only tables above 9,500,000 bytes are split', parts=parts, tables_not_split=not_split), indent=2) + '\n', encoding='utf-8')
# parts_manifest must sit in parts/ as requested: write it there too (identical content)
(parts_dir / 'parts_manifest.json').write_text((OUT / 'parts_manifest.json').read_text(encoding='utf-8'), encoding='utf-8')
(OUT / 'parts_manifest.json').unlink()

# augment manifest
units = man['units']
man['rows_per_unit'] = {f"{u['task']}/{u['model_name']}/seed{u['seed']}": {t: v['rows'] for t, v in u['tables'].items()} for u in units}
man['not_available'] = [dict(task=u['task'], model_name=u['model_name'], seed=u['seed'], table=t, status='NOT_AVAILABLE', reason=v['reason'])
                        for u in units for t, v in u['tables'].items() if v['status'] != 'OK']
man['units_complete_per_table'] = {t: sum(1 for u in units if u['tables'][t]['status'] == 'OK') for t in TABLES}
man['parts'] = dict(directory='parts/', manifest='parts/parts_manifest.json', tables_split=sorted({p['table'] for p in parts}), tables_not_split=list(not_split))
(OUT / 'manifest.json').write_text(json.dumps(man, indent=1, default=str) + '\n', encoding='utf-8')

# sha256sums (README added later -> run again after README)
print(man['units_complete_per_table'])
print(len(parts), 'parts; max bytes', max(p['bytes'] for p in parts))
