"""Match the CQ R4 resource runs to the original run_manifest.json files of the preserved packages (runner commit, layout hash)."""
import glob
import json
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf8')
BACK = chr(92)
rows = []
for f in glob.glob('upload_staging/m09/man/*/**/run_manifest.json', recursive=True):
    m = json.load(open(f, encoding='utf8'))
    pkg = f.replace(BACK, '/').split('/man/')[1].split('/')[0]
    rows.append({'pkg': pkg, 'model_name': m.get('model_name'), 'window_id': m.get('window_id'), 'pipeline_id': m.get('pipeline_id'),
                 'seed': m.get('seed'), 'runner_git_commit': m.get('runner_git_commit'), 'layout': m.get('feature_layout_sha256'),
                 'static_layout_policy': m.get('static_layout_policy'), 'created': m.get('created_at_utc'), 'elapsed': m.get('elapsed_seconds'),
                 'run_purpose': m.get('run_purpose'), 'protocol': m.get('protocol'), 'backend': m.get('execution_backend'), 'path': f})
d = pd.DataFrame(rows)
print(d.shape)
print(d.groupby(['pkg', 'model_name']).size().unstack(fill_value=0))
for pkg, g in d.groupby('pkg'):
    print(pkg, '| commits', dict(g.runner_git_commit.astype(str).value_counts().head(3)), '| layouts', dict(g.layout.astype(str).str[:19].value_counts().head(3)),
          '| policy', dict(g.static_layout_policy.astype(str).value_counts().head(3)))
r4 = pd.read_parquet('upload_staging/m09/r4/cq_resource_per_run.parquet')
key = ['model_name', 'window_id', 'pipeline_id', 'seed']
dup = d.groupby(key).size()
print('keys with several manifests:', int((dup > 1).sum()))
m = r4.merge(d, on=key, how='left', suffixes=('_r4', ''))
m['same_elapsed'] = (m.elapsed_seconds.astype(float) - m.elapsed.astype(float)).abs() < 1e-6
m['same_created'] = m.created_at_utc.astype(str) == m.created.astype(str)
print('R4 runs', len(r4), 'with a manifest of the same key:', int(m.pkg.notna().sum()))
print(m.groupby(['model_name', 'pkg'], dropna=False).agg(n=('pipeline_id', 'size'), same_elapsed=('same_elapsed', 'sum'), same_created=('same_created', 'sum')))
d.drop(columns='path').to_csv('upload_staging/m09/manifest_table.csv', index=False)
m.to_csv('upload_staging/m09/r4_vs_manifests.csv', index=False)
