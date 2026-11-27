"""Build static_layout_by_unit.csv (36 units: task x model x seed) from the facts resource tables that are the inputs of the 3-seed release
(verified by sha256 against meta_release_manifest.json) plus feature_layout.json / run_manifest.json files of the preserved packages.
No salt, no training, no recomputation of models. Usage: python build_static_layout_by_unit.py WORK_DIR REPO_DIR
"""
import glob, hashlib, json, os, sys
import pandas as pd

WORK, REPO = sys.argv[1], sys.argv[2]
SRC = os.path.join(WORK, 'src')
rel = json.load(open(os.path.join(SRC, 'release_manifest.json')))['input_files_sha256']


def sha_file(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def load(p):
    return pd.read_parquet(p) if p.endswith('parquet') else pd.read_csv(p)


# 1) hash -> field list, from every feature_layout.json we hold (hash = sha256 of file bytes, as the runner does)
layouts = {}
roots = [os.path.join(SRC, 'cq42hist'), os.path.join(SRC, 'lo42prim'), os.path.join(REPO, 'CQ', 'resuilt')]
for root in roots:
    for f in glob.glob(os.path.join(root, '**', 'feature_layout.json'), recursive=True):
        try:
            b = open(f, 'rb').read()
        except OSError:
            continue
        layouts.setdefault('sha256:' + hashlib.sha256(b).hexdigest(), json.loads(b)['static_columns'])

# 2) per-run table
runs = []
for key, v in rel.items():
    if 'resource' not in key or key == 'cq_resources_R4':
        continue
    r = load(v['path'])
    r['_input'] = key
    runs.append(r[['task', 'model_name', 'seed', 'window_id', 'pipeline_id', 'runner_git_commit', 'feature_layout_sha256', '_input']])
runs = pd.concat(runs, ignore_index=True)
runs['layout_origin'] = 'resource_per_run.feature_layout_sha256'

# 3) CQ seed 42 F1 (R4 resource table has no layout column): match R4 rows to the original run_manifest.json of the preserved packages
r4 = load(rel['cq_resources_R4']['path'])
manifests = {}
for f in glob.glob(os.path.join(SRC, 'cq42hist', '**', 'run_manifest.json'), recursive=True):
    if any(t in f for t in ('matched_historical', 'baseline_drive', 'patchtst_pilot', 'replay_protocol27')):
        continue  # later replays / pilots are not the R4 runs
    m = json.load(open(f))
    if m.get('task') == 'CQ' and m.get('model_name') in ('RNN', 'LSTM', 'GRU', 'BILSTM') and m.get('seed') == 42:
        lay = os.path.join(os.path.dirname(f), 'feature_layout.json')
        manifests[(m['model_name'], m['window_id'], m['pipeline_id'])] = (m, 'sha256:' + sha_file(lay))
rows = []
for x in r4.itertuples():
    m, h = manifests[(x.model_name, x.window_id, x.pipeline_id)]
    assert m['created_at_utc'] == x.created_at_utc and abs(m['elapsed_seconds'] - x.elapsed_seconds) < 1e-6, (x.model_name, x.window_id, x.pipeline_id)
    rows.append({'task': 'CQ', 'model_name': x.model_name, 'seed': 42, 'window_id': x.window_id, 'pipeline_id': x.pipeline_id,
                 'runner_git_commit': m.get('runner_git_commit'), 'feature_layout_sha256': h, '_input': 'cq_resources_R4',
                 'layout_origin': 'sha256 of feature_layout.json of the original package, run matched to R4 by created_at_utc + elapsed_seconds'})
runs = pd.concat([runs, pd.DataFrame(rows)], ignore_index=True)
runs.to_csv(os.path.join(WORK, 'static_layout_by_run.csv'), index=False)

# 4) unit table
SRC_TXT = {
    'cq_resources_R4': 'Bảng R4 (cq_resource_per_run; sha256 khớp meta_release_manifest) khớp 1-1 (created_at_utc + elapsed_seconds) với run_manifest.json gốc của gói lưu trữ; hash = sha256 của feature_layout.json gốc; commit = run_manifest.runner_git_commit (rỗng ở mọi run)',
}
out = []
for (task, model, seed), g in runs.groupby(['task', 'model_name', 'seed']):
    hs = sorted(g.feature_layout_sha256.dropna().unique())
    cm = g.runner_git_commit.fillna('NULL_NOT_RECORDED').astype(str)
    cm = ';'.join(f'{k}({n})' for k, n in cm.value_counts().items()) if cm.nunique() > 1 else cm.iloc[0]
    fields = [layouts.get(h) for h in hs]
    if all(f is not None for f in fields):
        nf = ';'.join(str(len(f)) for f in fields)
        fl = ' | '.join(';'.join(f) for f in fields)
    else:
        nf, fl = 'NOT_AVAILABLE', 'NOT_AVAILABLE'
    inp = g._input.unique()
    if inp[0] == 'cq_resources_R4':
        src = SRC_TXT['cq_resources_R4']
    else:
        src = 'resource_per_run của gói facts (' + ','.join(sorted(inp)) + '; sha256 khớp meta_release_manifest); danh sách cột lấy từ feature_layout.json có cùng hash'
    out.append({'task': task, 'model_name': model, 'seed': seed, 'n_runs': len(g), 'layout_sha256': ';'.join(hs),
                'n_static_fields': nf, 'static_fields_list': fl, 'runner_commit': cm, 'source': src})
df = pd.DataFrame(out)
order = {'RNN': 0, 'LSTM': 1, 'GRU': 2, 'BILSTM': 3, 'PATCHTST': 4, 'MANTIS_V2': 5}
df = df.sort_values(['task', 'model_name', 'seed'], key=lambda s: s.map(order) if s.name == 'model_name' else s).reset_index(drop=True)
df.to_csv(os.path.join(WORK, 'static_layout_by_unit.csv'), index=False, encoding='utf-8-sig')
pd.set_option('display.width', 250, 'display.max_colwidth', 60)
print(df[['task', 'model_name', 'seed', 'n_runs', 'layout_sha256', 'n_static_fields', 'runner_commit']].to_string())
print(len(df), 'units;', 'known layouts:', {k[:19]: len(v) for k, v in layouts.items()})
