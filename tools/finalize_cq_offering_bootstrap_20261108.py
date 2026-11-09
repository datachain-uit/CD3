"""Wait for CQ flagged cells, validate and deliver a complete bootstrap bundle."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'CQ/resuilt/cq_offering_bootstrap_grid_20261108'
OUT = ROOT / 'CQ/resuilt/cq_offering_bootstrap_delivery_20261108'
FLAGS = ROOT / 'CQ/resuilt/cq_offering_dominance_20261108/cell_flags_phase1.parquet'
SUPPORT = ROOT / 'CQ/resuilt/cq_offering_dominance_20261108/class_offering_support.csv'
DRIVE = '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'
TARGET = 'gdrive:Jobs/CQ/organized_moved_20261029/L2_facts/fact_exports/cq_offering_bootstrap_phase1_20261108'
OUT.mkdir(parents=True, exist_ok=True)

def state(value, **fields):
    (OUT / 'delivery_status.json').write_text(json.dumps({'status': value, **fields}, indent=2), encoding='utf8')

while True:
    try:
        f1 = json.loads((WORK / 'status.json').read_text(encoding='utf8'))
        f2 = json.loads((WORK / 'patchtst_status.json').read_text(encoding='utf8'))
    except (FileNotFoundError, json.JSONDecodeError):
        state('WAITING_FOR_WORKERS'); time.sleep(30); continue
    if f1['status'] == 'F1_PARTIAL_ERRORS_F2_PENDING' or f2['status'] == 'PARTIAL_ERRORS':
        state('WORKER_ERRORS', f1_errors=f1.get('errors'), f2_errors=f2.get('errors')); break
    if f1['status'] != 'F1_COMPLETE_F2_PENDING' or f2['status'] != 'COMPLETE':
        state('WAITING_FOR_WORKERS', f1_done=f1.get('f1_done'), f2_done=f2.get('cells_done')); time.sleep(30); continue
    try:
        flags = pd.read_parquet(FLAGS)
        flagged = flags[flags.single_offering_dominant]
        keys = ['task', 'window_id', 'pipeline_id', 'model_name', 'seed', 'eval_split', 'phase_id']
        expected = set(map(tuple, flagged[keys].itertuples(index=False, name=None)))
        if len(expected) != 600:
            raise ValueError('Expected 600 unique flagged cell keys')
        records, seen = [], set()
        for path in (WORK / 'cells').rglob('*.json'):
            item = json.loads(path.read_text(encoding='utf8'))
            key = tuple(item[k] for k in keys)
            if key in seen or key not in expected or item['bootstrap_replicates'] != 2000 or item['prediction_join'] != 'ONE_TO_ONE_LABELS_MATCH':
                raise ValueError(f'Invalid/duplicate cell: {path}')
            seen.add(key)
            if {x['class_code'] for x in item['class_recall']} != {'c0', 'c1', 'c2'}:
                raise ValueError(f'Incomplete class metrics: {path}')
            for row in item['class_recall']:
                records.append({**{k: item[k] for k in keys}, 'bootstrap_seed': item['bootstrap_seed'],
                                'bootstrap_replicates': item['bootstrap_replicates'],
                                'prediction_rows': item['prediction_rows'], 'prediction_join': item['prediction_join'],
                                'prediction_sha256': item['prediction_sha256'], 'prediction_source': item['prediction_source'], **row})
        if seen != expected or len(records) != 1800:
            raise ValueError(f'Coverage mismatch: cells={len(seen)}, class_rows={len(records)}')
        frame = pd.DataFrame(records)
        support = pd.read_csv(SUPPORT)
        support['class_code'] = support.class_index.map({0: 'c0', 1: 'c1', 2: 'c2'})
        check = frame.merge(support[['window_id', 'eval_split', 'class_code', 'n_support', 'n_offerings_with_class']],
                            on=['window_id', 'eval_split', 'class_code'], validate='many_to_one')
        if not check.support.eq(check.n_support).all() or not check.offering_count.eq(check.n_offerings_with_class).all():
            raise ValueError('Class support/offering counts mismatch existing M-05 table')
        frame.to_csv(OUT / 'offering_cluster_bootstrap_per_class.csv', index=False)
        frame.to_parquet(OUT / 'offering_cluster_bootstrap_per_class.parquet', index=False)
        shutil.copy2(FLAGS, OUT / 'cell_flags_phase1.parquet')
        shutil.copy2(SUPPORT, OUT / 'class_offering_support.csv')
        summary = {'task': 'CQ', 'seed': 42, 'flagged_cells': len(seen), 'class_rows': len(frame),
                   'bootstrap_repetitions': 2000, 'join': 'ONE_TO_ONE_LABELS_MATCH',
                   'support_offering_match': 'PASS', 'ci_status': frame.ci_status.value_counts().to_dict(),
                   'scope': 'CQ F1 plus PatchTST V0-V6, flagged TEST cells only; not L2 ingestion'}
        (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
        (OUT / 'README.md').write_text('# CQ offering cluster bootstrap — phase 1\n\n600 flagged test cells, B=2,000; sampling unit is (offering_id, timeline_source). Predictions are joined by salted enrollment hash and labels checked one-to-one. Class support and offering counts match the M-05 source support. CI is conditional on the resampled class being present; single-offering classes are not estimable. This export is not an official L2-ingest receipt.\n', encoding='utf8')
        with (OUT / 'sha256sums.txt').open('w', encoding='utf8') as stream:
            for name in ('offering_cluster_bootstrap_per_class.csv', 'offering_cluster_bootstrap_per_class.parquet',
                         'cell_flags_phase1.parquet', 'class_offering_support.csv', 'summary.json', 'README.md'):
                p = OUT / name
                stream.write(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {name}\n')
        state('UPLOADING')
        subprocess.run(['rclone', 'copy', str(OUT), TARGET, '--drive-root-folder-id', DRIVE,
                        '--exclude', 'delivery_status.json', '--retries', '4'], check=True, timeout=21600)
        subprocess.run(['rclone', 'check', str(OUT), TARGET, '--drive-root-folder-id', DRIVE,
                        '--exclude', 'delivery_status.json', '--one-way'], check=True, timeout=1800)
        state('DRIVE_VERIFIED', **summary)
        break
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        state('FINALIZATION_FAILED', error=str(exc)); break
