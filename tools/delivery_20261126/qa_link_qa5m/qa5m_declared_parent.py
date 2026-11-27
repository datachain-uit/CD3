"""Reads the `parent` field of run_manifest.json of the 108 balanced Mantis runs (seeds 42/43) by streaming each tar.gz (nothing but the manifest is kept). Read-only on Drive, 2 threads."""
import io, json, subprocess, sys, tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
WORK = Path(sys.argv[1]); OUT = WORK / 'qa5m'; TMP = OUT / 'tmp_parent'; TMP.mkdir(exist_ok=True)
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
ext = pd.read_csv(OUT / 'qa5_mantis_link_extension.csv')
ext = ext[ext.seed.isin([42, 43])]
cat = pd.read_parquet(sys.argv[2])
cat = cat[(cat.model_name == 'MANTIS_V2') & (cat.kind == 'tar')].drop_duplicates(['task', 'seed', 'window_id', 'pipeline_id'])
src = {(r.task, r.seed, r.window_id, r.pipeline_id): r.path for r in cat.itertuples()}
def job(k):
    task, seed, w, v = k
    f = TMP / f'{task}_{seed}_{w}_{v}.json'
    if f.exists(): return
    rel = src[k].replace('/S3_model/', f'/S3_model/seed={seed}/', 1)
    res = {'tar': Path(rel).name, 'ok': False}
    try:
        p = subprocess.Popen(RC + ['cat', f'gdrive:{rel}'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        with tarfile.open(fileobj=p.stdout, mode='r|*') as t:
            for m in t:
                if m.isfile() and m.name.endswith(f'runs/{w}/{v}/run_manifest.json'):
                    d = json.loads(t.extractfile(m).read().decode('utf-8'))
                    res.update(ok=True, parent=d.get('parent'), parent_pipeline=d.get('parent_pipeline'), seed=d.get('seed'), pipeline=d.get('pipeline'), window=d.get('window'), task=d.get('task'))
                    break
        p.kill()
    except Exception as e:
        res['error'] = type(e).__name__
    f.write_text(json.dumps(res))
    print(k, res.get('parent'), res.get('error', ''), flush=True)
keys = [(r.task, int(r.seed), r.window, r.pipeline) for r in ext.itertuples()]
with ThreadPoolExecutor(2) as ex: list(ex.map(job, keys))
print('DONE')
