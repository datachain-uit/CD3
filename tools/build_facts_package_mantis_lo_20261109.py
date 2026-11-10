"""Build F2 facts packages (audit tables + SEEN/UNSEEN cohort slices + per-run resources) for
  --kind mantis   : CQ Mantis (MANTIS_V2, EXPLORATORY) V0-V16, seed 42
  --kind lo       : LO PatchTST V0-V16, seed 42
Same table set and checks as the CQ PatchTST packages (cq_patchtst_v0_v6_full_facts_20261103 / v7_v16_..._20261109).
Audit roots are given oldest first; for a (window, pipeline) cell the rows of the LAST root containing it win.
"""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--kind', choices=('mantis', 'lo', 'lo_mantis'), required=True)
ap.add_argument('--audit-roots', type=Path, nargs='+', required=True)
ap.add_argument('--cohort-roots', type=Path, nargs='+', required=True, help='dirs holding V<n>/ cohort audits (later wins)')
ap.add_argument('--std-roots', type=Path, nargs='*', default=[], help='mantis: standardized run roots with CQ/W*/V*/MANTIS_V2/seed=42')
ap.add_argument('--lo-resources', type=Path, help='lo: dir holding V<n>/run_manifests.parquet')
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()

TABLES = ['sanity_components', 'evaluation_slices', 'metrics_per_class', 'bootstrap_metrics_per_class', 'checkpoint_selection']
CELL = ['window_id', 'pipeline_id']
K = ['pipeline_id', 'window_id', 'eval_split', 'phase_id']
if args.kind == 'mantis':
    TASK, MODEL, RELEASE, PIPES = 'CQ', 'MANTIS_V2', 'CQ_V2_2', [f'V{i}' for i in range(17)]
elif args.kind == 'lo_mantis':
    TASK, MODEL, RELEASE, PIPES = 'LO', 'MANTIS_V2', 'LO_V3_1', [f'V{i}' for i in range(17)]
else:
    TASK, MODEL, RELEASE, PIPES = 'LO', 'PATCHTST', 'LO_V3_1', [f'V{i}' for i in range(17)]
N = len(PIPES)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def save(frame, name):
    frame.to_parquet(args.out / (name + '.parquet'), index=False)
    frame.to_csv(args.out / (name + '.csv'), index=False)


def merged(name):
    chosen = {}
    for root in args.audit_roots:
        for p in sorted(root.rglob(name + '.parquet')):
            frame = pd.read_parquet(p)
            if not set(CELL) <= set(frame.columns):
                continue
            for key, part in frame.groupby(CELL):
                chosen[key] = part
    return pd.concat([chosen[k] for k in sorted(chosen, key=lambda t: (t[0], int(t[1][1:])))], ignore_index=True)


args.out.mkdir(parents=True, exist_ok=True)
combined = {n: merged(n) for n in TABLES}
exp = {'sanity_components': 24 * N, 'evaluation_slices': 72 * N, 'metrics_per_class': 72 * N,
       'bootstrap_metrics_per_class': 216 * N, 'checkpoint_selection': 3 * N}
for n, count in exp.items():
    if len(combined[n]) != count:
        raise SystemExit(f'{n}: expected {count} rows, got {len(combined[n])}')
sanity = combined['sanity_components']
if 'acctempo_m4' not in sanity.columns:
    sanity['acctempo_m4'] = float('nan')
miss = sanity.acctempo_m4.isna()
sanity.loc[miss, 'acctempo_m4'] = sanity.loc[miss, 's_perf'].clip(lower=1e-3).pow(.6) * sanity.loc[miss, 's_san_plus_v2'].clip(lower=1e-3).pow(.4)
for n, frame in combined.items():
    save(frame, n)

# resources
if args.kind in ('mantis', 'lo_mantis'):
    rows = []
    for root in args.std_roots:
        for mp in sorted(root.glob(f'{TASK}/W*/V*/{MODEL}/seed=42/run_manifest.json')):
            m = json.loads(mp.read_text(encoding='utf-8'))
            m['train_seconds'] = float(pd.read_parquet(mp.parent / 'train_history.parquet').train_seconds.sum())
            rows.append(m)
    res = pd.DataFrame(rows).drop_duplicates(['pipeline_id', 'window_id'], keep='last')
else:
    res = pd.concat([pd.read_parquet(p) for p in sorted(args.lo_resources.glob('V*/run_manifests.parquet'))], ignore_index=True)
keys = ['task', 'model_name', 'window_id', 'pipeline_id', 'seed', 'train_seconds', 'elapsed_seconds', 'gpu', 'batch_size', 'micro_batch_size',
        'accumulation_steps', 'energy_measurement_type', 'energy_gpu_estimated_kwh', 'energy_sample_count', 'energy_sample_attempt_count',
        'energy_missing_sample_rate', 'energy_sampling_duration_s', 'energy_boundary', 'execution_backend', 'runner_git_commit', 'feature_layout_sha256']
for k in keys:
    if k not in res:
        res[k] = None
res = res[keys]
if len(res) != 3 * N or res.train_seconds.isna().any() or res.duplicated(['pipeline_id', 'window_id']).any():
    raise SystemExit(f'resource coverage failed: {len(res)} rows')
save(res, 'resource_per_run')

# cohort
cohort_dir = args.out / 'cohort_audit'
frames = []
for v in PIPES:
    src = None
    for root in args.cohort_roots:
        if (root / v / 'summary.json').is_file():
            src = root / v
    if src is None:
        raise SystemExit(f'cohort audit missing for {v}')
    meta = json.loads((src / 'summary.json').read_text(encoding='utf-8'))
    if meta['prediction_files'] != 24 or meta['duplicate_hashes'] or meta['invalid_strict']:
        raise SystemExit(f'{v} cohort checks failed')
    f = pd.read_parquet(src / 'seen_unseen_strict_overlap_metrics.parquet')
    if len(f) != 96:
        raise SystemExit(f'{v}: cohort cells {len(f)}')
    frames.append(f)
    for name in ('summary.json', 'seen_unseen_strict_overlap_metrics.parquet', 'seen_unseen_strict_overlap_metrics.csv', 'prediction_invariants.parquet'):
        (cohort_dir / v).mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / name, cohort_dir / v / name)
c = pd.concat(frames, ignore_index=True)
if len(c) != 96 * N or c.duplicated(K + ['course_cohort', 'temporal_slice']).any():
    raise SystemExit('cohort keys not unique')
tot = c.groupby(K, as_index=False).n_eval.sum().merge(sanity[K + ['n_eval_samples']], on=K, validate='one_to_one')
if len(tot) != 24 * N or not tot.n_eval.eq(tot.n_eval_samples).all():
    raise SystemExit('cohort partition mismatch')
n = (c[['support_c0', 'support_c1', 'support_c2']] > 0).sum(axis=1)
c['status'] = 'OK'
c.loc[n.eq(1), 'status'] = 'ONE_CLASS'
c.loc[c.n_eval.eq(0), 'status'] = 'SLICE_EMPTY'
save(c, 'cohort_slice_status')

summary = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'task': TASK, 'model': MODEL, 'seed': 42, 'release_id': RELEASE,
           'versions': PIPES, 'sanity_cells': len(sanity), 'slice_rows': len(combined['evaluation_slices']),
           'per_class_rows': len(combined['metrics_per_class']), 'bootstrap_rows': len(combined['bootstrap_metrics_per_class']),
           'resource_runs': len(res), 'cohort_status_rows': len(c), 'cohort_status': 'COMPLETE_FULL_JOIN',
           'cohort_status_counts': c.status.value_counts().to_dict(), 'cohort_partition_counts': 'PASS', 'strict_partition_counts': 'PASS',
           'run_purpose': 'EXPLORATORY' if args.kind in ('mantis', 'lo_mantis') else 'PRIMARY_GRID'}
(args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
extra = ('Mantis is an EXPLORATORY frozen-backbone linear-probe run (MANTIS_V2), not the primary model grid. V0 predictions were rebuilt from stored '
         'probabilities (validation score equals the cell record); its elapsed time and GPU energy were not recorded and are null. runner_git_commit is null.'
         if args.kind == 'mantis' else
         ('Mantis is an EXPLORATORY frozen-backbone linear-probe run (MANTIS_V2) on task LO, not the primary model grid. All 51 cells were run with the grid runner of '
          'tools/run_mantis_grid_zstd_20261109.py; elapsed time, peak RAM and GPU energy come from the run manifests. runner_git_commit is mapped retroactively by blob match (see runner_commit_evidence.json).')
         if args.kind == 'lo_mantis' else
         'LO PatchTST seed 42, labels LO_performance_label_3 (I/D, G, E). Audit tables come from the standard audit of the result trees; '
         'pipelines V5, V6, V8-V10, V13-V16 use the audit stored in their bundles.')
(args.out / 'README.md').write_text(
    f"# {TASK} {MODEL} V0–V16, seed 42\n\n{summary['sanity_cells']} split/window/phase sanity cells; {summary['slice_rows']} ALL/STRICT/OVERLAP rows; "
    f"{summary['per_class_rows']} per-class rows; {summary['bootstrap_rows']} bootstrap rows with B=2,000; {summary['resource_runs']} run-resource rows. "
    "`acctempo_m4` is S_perf^0.6 × S_san_plus_v2^0.4 with floor 0.001.\n\n"
    f"`cohort_slice_status` contains {len(c)} audited SEEN/UNSEEN × STRICT/OVERLAP facts with OK/ONE_CLASS/SLICE_EMPTY flags "
    f"({summary['cohort_status_counts']}). All four-slice sums match evaluation totals; prediction hashes are unique and strict flags valid. "
    f"SEEN is a course that occurs in the real parent TRAIN of the same window.\n\n{extra}\n", encoding='utf-8')
files = sorted(p for p in args.out.rglob('*') if p.is_file() and p.name != 'sha256sums.txt')
(args.out / 'sha256sums.txt').write_text(''.join(sha(p) + '  ' + p.relative_to(args.out).as_posix() + '\n' for p in files), encoding='utf-8')
print(json.dumps({'kind': args.kind, 'cells': len(sanity), 'cohort': len(c), 'status': summary['cohort_status_counts'], 'files': len(files)}, indent=2))
