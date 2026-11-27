"""Launch qa_pred_audit.py for all 36 units (2 at a time = the rclone limit of 2 concurrent transfers), skipping units whose evidence json already exists, then aggregate.
usage:  python run_all_qa5.py --out OUT_DIR [--units LO:PATCHTST:43 ...] [--parallel 2] [--aggregate-only]
env:    TEMPO_REPO_ROOT, TEMPO_WORK_ROOT (+ TEMP/TMP on a drive with space)
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--units', nargs='*')
ap.add_argument('--parallel', type=int, default=2)
ap.add_argument('--aggregate-only', action='store_true')
a = ap.parse_args()
OUT = Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
MODELS = ['RNN', 'LSTM', 'GRU', 'BILSTM', 'PATCHTST', 'MANTIS_V2']
units = [tuple(u.split(':')) for u in a.units] if a.units else [(t, m, str(s)) for t in ('LO', 'CQ') for s in (43, 44, 42) for m in MODELS]


def run(u):
    t, m, s = u
    name = f'{t}_{m}_seed{s}'
    if (OUT / f'{name}_qa_evidence.json').exists():
        return name, 'skip'
    r = subprocess.run([sys.executable, '-I', str(HERE / 'qa_pred_audit.py'), t, m, s, '--out', str(OUT), '--tmp', str(OUT / 'tmp' / name)], capture_output=True, text=True)
    (OUT / f'{name}.log').write_text(r.stdout + r.stderr, encoding='utf-8')
    return name, r.returncode


if not a.aggregate_only:
    with ThreadPoolExecutor(a.parallel) as ex:
        for name, rc in ex.map(run, units):
            print(time.strftime('%T'), name, rc, flush=True)
rows = []
for f in sorted(OUT.glob('*_qa_evidence.json')):
    e = json.loads(f.read_text(encoding='utf-8'))
    rows.append({'unit': e['unit'], 'wall_s': e['wall_seconds'], 'GB': round(e['bytes_downloaded_total'] / 1e9, 2), 'files': f"{e['files_checked']}/{e['files_expected']}", 'rows': e['QA07']['rows_checked'], 'qa07_sum_viol': e['QA07']['n_sum_viol'],
                 'qa07_argmax_viol': e['QA07']['n_pred_below_max'], 'qa07_ties': e['QA07']['n_ties'], 'qa12_not_in_pop': e['QA12']['rows_not_in_real_population'], 'qa12_rows_ne_manifest': e['QA12']['files_rows_ne_manifest'],
                 'qa13_ckpt_field_runs': e['QA13']['runs_with_checkpoint_sha256_field'], 'qa11_nonzero_runs': e['QA11']['runs_with_nonzero'], 'qa21p1_overlap': e['QA21']['p1_val_test_overlap_total_keys'],
                 'p5_proxy_runs': e['QA21'].get('p5_runs_with_proxy_in_model_input')})
df = pd.DataFrame(rows)
df.to_csv(OUT / 'aggregate_units_qa5.csv', index=False)
print(df.to_string() if len(df) else 'no evidence yet'); print('units', len(df), 'of 36')
