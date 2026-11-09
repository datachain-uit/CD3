"""Post-hoc audit facts for Mantis CQ cells (sanity components, per-class metrics, bootstrap, STRICT/OVERLAP slices,
checkpoint selection, canonical S_leak) using the existing tools/vastai_audit_shared.py unchanged.

Mantis cells keep their own result layout (runs/<W>/<V>/{predictions,result,run_manifest.json,metrics_overall.parquet}).
This adapter only builds the TASK/W/V/MODEL/seed=N tree the audit expects: it copies the predictions, writes a
run_manifest.json with the identity keys the audit checks, a metadata_contract.json carrying the release id, a
train_history.parquet taken from the cell record, and a feature_layout.json fitted on the parent TRAIN input (the same
fit_layout call the F1 runners use). It never reloads a probe or retrains.

Usage: python -I tools/mantis_posthoc_audit_20261108.py --data-root DATA --work WORK --audit-root OUT --extracted DIR [DIR ...]
Each DIR is an extracted Mantis result package that contains runs/<W>/<V>/.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

MODEL = 'MANTIS_V2'
PARENTS = {'V1': 'V1', 'V13': 'V13', 'V2': 'V1', 'V3': 'V1', 'V4': 'V1', 'V5': 'V5', 'V9': 'V9'}

parser = argparse.ArgumentParser()
parser.add_argument('--data-root', type=Path, required=True)
parser.add_argument('--work', type=Path, required=True)
parser.add_argument('--audit-root', type=Path, required=True)
parser.add_argument('--extracted', type=Path, nargs='+', required=True)
parser.add_argument('--bootstrap-repetitions', type=int, default=2000)
args = parser.parse_args()

from model.data import fit_layout
release = json.loads((args.data_root / 'download_manifest.json').read_text(encoding='utf8'))
if args.work.exists():
    raise SystemExit(f'work dir exists: {args.work}')
layouts = {}
built = []
for root in args.extracted:
    for run_dir in sorted((root / 'runs').glob('W*/V*')):
        window, pipeline = run_dir.parent.name, run_dir.name
        if not (run_dir / 'COMPLETE').is_file():
            if any(run_dir.iterdir()):
                raise SystemExit(f'not complete: {run_dir}')
            continue   # empty directory left by an interrupted start (V13 W3 on the first machine)
        record = json.loads((run_dir / 'result' / 'f3_cell_record.json').read_text(encoding='utf8'))
        source = json.loads((run_dir / 'run_manifest.json').read_text(encoding='utf8'))
        if source['release_id'] != release['release_id'] or source['data_release_id'] != release['data_release_id']:
            raise SystemExit(f'release identity mismatch: {run_dir}')
        parent = PARENTS[pipeline] if pipeline in PARENTS else source['parent']
        if parent != source['parent']:
            raise SystemExit(f'parent mismatch for {run_dir}: {parent} vs {source["parent"]}')
        key = (window, parent)
        if key not in layouts:
            first = next(pq.ParquetFile(args.data_root / 'train' / window / parent / 'train.parquet').iter_batches(batch_size=1)).to_pandas()
            layouts[key] = fit_layout(first, task='CQ', phase_id='P4', use_masks=True)
        target = args.work / 'CQ' / window / pipeline / MODEL / 'seed=42'
        (target / 'predictions').mkdir(parents=True)
        for p in (run_dir / 'predictions').glob('*.parquet'):
            shutil.copy2(p, target / 'predictions' / p.name)
        manifest = {**source, 'task': 'CQ', 'window_id': window, 'pipeline_id': pipeline, 'best_epoch': record['best_epoch'],
                    'model_name': MODEL, 'source_cell_record_sha': None}
        (target / 'run_manifest.json').write_text(json.dumps(manifest, indent=2, default=str), encoding='utf8')
        (target / 'metadata_contract.json').write_text(json.dumps({'release': {'release_id': release['release_id']}}), encoding='utf8')
        pd.DataFrame(record['history']).to_parquet(target / 'train_history.parquet', index=False)
        (target / 'feature_layout.json').write_text(json.dumps({'dynamic_bases': list(layouts[key].dynamic_bases)}), encoding='utf8')
        built.append((window, pipeline))
print(json.dumps({'runs_built': built, 'release_id': release['release_id']}), flush=True)

# Read only the columns the audit uses (missing flags, availability/observed masks, label) from the large input files.
_original = pd.read_parquet
LABEL = 'CQ_label_final'


def _pruned(path, *a, **k):
    p = str(path).replace('\\', '/')
    if k.get('columns') is None and not a and p.endswith('.parquet') and ('/train/' in p or '/evaluation/' in p):
        names = pq.ParquetFile(path).schema_arrow.names
        keep = [n for n in names if n == LABEL or n.startswith('missing__') or n.startswith('phase_available_')
                or n.endswith(tuple(f'_observed_mask_P{i}' for i in range(1, 5)))]
        return _original(path, columns=keep, **k)
    return _original(path, *a, **k)


pd.read_parquet = _pruned
import vastai_audit_shared
sys.argv = ['vastai_audit_shared', '--task', 'CQ', '--data-root', str(args.data_root), '--run-root', str(args.work),
            '--audit-root', str(args.audit_root), '--model-name', MODEL, '--seed', '42', '--allow-partial',
            '--bootstrap-repetitions', str(args.bootstrap_repetitions)]
vastai_audit_shared.main()
