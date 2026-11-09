"""Collect verified CQ PatchTST V7-V16 (seed 42) facts, same layout as the V0-V6 package; never export private salts.

Inputs: the verified bundle of each pipeline (CQ/resuilt/<dir>/<dir>_verified.tar.gz with its download_receipt.json) and
the per-pipeline cohort audits written by tools/audit_prediction_course_cohort.py (--cohort-root/V<i>/).
Output: CQ/resuilt/cq_patchtst_v7_v16_full_facts_20261109/
"""
import argparse
import hashlib
import json
import shutil
import tarfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd

ROOT = Path('CQ/resuilt')
OUT = ROOT / 'cq_patchtst_v7_v16_full_facts_20261109'
NAMES = {7: 'cq_patchtst_v7_seed42_20261102', 8: 'cq_patchtst_v8_seed42_20261104', 9: 'cq_patchtst_v9_migrated_20261104',
         10: 'cq_patchtst_v10_continued_20261105', 11: 'cq_patchtst_v11_seed42_20261104', 12: 'cq_patchtst_v12_seed42_20261104',
         13: 'cq_patchtst_v13_seed42_20261104', 14: 'cq_patchtst_v14_seed42_20261104', 15: 'cq_patchtst_v15_continued_20261105',
         16: 'cq_patchtst_v16_continued_20261105'}
AUDITS = ['sanity_components', 'evaluation_slices', 'metrics_per_class', 'bootstrap_metrics_per_class', 'checkpoint_selection']
K = ['pipeline_id', 'window_id', 'eval_split', 'phase_id']
N = len(NAMES)

parser = argparse.ArgumentParser()
parser.add_argument('--cohort-root', type=Path, required=True)
args = parser.parse_args()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def save(frame, name):
    frame.to_parquet(OUT / (name + '.parquet'), index=False)
    frame.to_csv(OUT / (name + '.csv'), index=False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames = {k: [] for k in AUDITS}
    runs, sources = [], []
    for i, name in NAMES.items():
        archive = ROOT / name / (name + '_verified.tar.gz')
        receipt = json.loads((ROOT / name / 'download_receipt.json').read_text(encoding='utf8'))
        digest = sha(archive)
        if digest != receipt['sha256'] or receipt['status'] != 'download_verified':
            raise ValueError(f'V{i}: bad checksum')
        sources.append({'version': f'V{i}', 'archive': archive.as_posix(), 'sha256': digest})
        manifests, histories, found = {}, {}, set()
        with tarfile.open(archive, 'r:gz') as tar:
            for member in tar:
                if not member.isfile():
                    continue
                p = Path(member.name)
                stem = p.stem
                if '_audit/' in member.name and stem in AUDITS and p.suffix == '.parquet':
                    frames[stem].append(pd.read_parquet(BytesIO(tar.extractfile(member).read())))
                    found.add(stem)
                elif '/CQ/W' in member.name and p.name in ('run_manifest.json', 'train_history.parquet'):
                    key = p.parent.as_posix()
                    if p.name == 'run_manifest.json':
                        manifests[key] = json.load(tar.extractfile(member))
                    else:
                        histories[key] = pd.read_parquet(BytesIO(tar.extractfile(member).read()))
        if set(manifests) != set(histories) or len(manifests) != 3 or found != set(AUDITS):
            raise ValueError(f'V{i}: incomplete artifacts')
        for key, m in manifests.items():
            m['train_seconds'] = float(histories[key].train_seconds.sum())
            runs.append(m)
        print('verified', name, flush=True)
    combined = {name: pd.concat(items, ignore_index=True) for name, items in frames.items()}
    expected = {'sanity_components': 24 * N, 'evaluation_slices': 72 * N, 'metrics_per_class': 72 * N,
                'bootstrap_metrics_per_class': 216 * N, 'checkpoint_selection': 3 * N}
    for name, n in expected.items():
        if len(combined[name]) != n:
            raise ValueError(f'{name}: expected {n}, got {len(combined[name])}')
    sanity = combined['sanity_components']
    sanity['acctempo_m4'] = sanity.s_perf.clip(lower=1e-3).pow(.6) * sanity.s_san_plus_v2.clip(lower=1e-3).pow(.4)
    for name, frame in combined.items():
        save(frame, name)
    m = pd.DataFrame(runs)
    keys = ['task', 'model_name', 'window_id', 'pipeline_id', 'seed', 'train_seconds', 'elapsed_seconds', 'gpu', 'batch_size',
            'micro_batch_size', 'accumulation_steps', 'energy_measurement_type', 'energy_gpu_estimated_kwh', 'energy_sample_count',
            'energy_sample_attempt_count', 'energy_missing_sample_rate', 'energy_sampling_duration_s', 'energy_boundary',
            'execution_backend', 'runner_git_commit', 'feature_layout_sha256']
    for k in keys:
        if k not in m:
            m[k] = None
    resources = m[keys]
    if len(resources) != 3 * N or resources.train_seconds.isna().any() or resources.duplicated(['pipeline_id', 'window_id']).any():
        raise ValueError('resource coverage failed')
    save(resources, 'resource_per_run')

    # cohort slices
    cohort_dir = OUT / 'cohort_audit'
    frames_c = []
    for i in NAMES:
        src = args.cohort_root / f'V{i}'
        meta = json.loads((src / 'summary.json').read_text(encoding='utf8'))
        if meta['prediction_files'] != 24 or meta['duplicate_hashes'] or meta['invalid_strict']:
            raise ValueError(f'V{i} cohort audit checks failed')
        frame = pd.read_parquet(src / 'seen_unseen_strict_overlap_metrics.parquet')
        if len(frame) != 96:
            raise ValueError(f'V{i} missing cohort cells')
        frames_c.append(frame)
        shutil.copytree(src, cohort_dir / f'V{i}', dirs_exist_ok=True)
    c = pd.concat(frames_c, ignore_index=True)
    if len(c) != 96 * N or c.duplicated(K + ['course_cohort', 'temporal_slice']).any():
        raise ValueError('cohort keys not unique')
    total = c.groupby(K, as_index=False).n_eval.sum().merge(sanity[K + ['n_eval_samples']], on=K, validate='one_to_one')
    if len(total) != 24 * N or not total.n_eval.eq(total.n_eval_samples).all():
        raise ValueError('cohort partition mismatch')
    n = (c[['support_c0', 'support_c1', 'support_c2']] > 0).sum(axis=1)
    c['status'] = 'OK'
    c.loc[n.eq(1), 'status'] = 'ONE_CLASS'
    c.loc[c.n_eval.eq(0), 'status'] = 'SLICE_EMPTY'
    save(c, 'cohort_slice_status')

    (OUT / 'source_inventory.json').write_text(json.dumps(sources, indent=2) + '\n', encoding='utf8')
    summary = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'task': 'CQ', 'model': 'PATCHTST', 'seed': 42,
               'versions': [f'V{i}' for i in NAMES], 'sanity_cells': expected['sanity_components'],
               'slice_rows': expected['evaluation_slices'], 'per_class_rows': expected['metrics_per_class'],
               'bootstrap_rows': expected['bootstrap_metrics_per_class'], 'resource_runs': len(resources),
               'cohort_status_rows': len(c), 'cohort_status': 'COMPLETE_FULL_JOIN',
               'cohort_status_counts': c.status.value_counts().to_dict(), 'cohort_partition_counts': 'PASS',
               'strict_partition_counts': 'PASS', 'nvml_energy': 'GPU_ONLY_ESTIMATE'}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
    (OUT / 'README.md').write_text(
        f"# CQ PatchTST V7–V16, seed 42\n\n{expected['sanity_components']} split/window/phase sanity cells; {expected['evaluation_slices']} ALL/STRICT/OVERLAP rows; "
        f"{expected['metrics_per_class']} per-class rows; {expected['bootstrap_metrics_per_class']} bootstrap rows with B=2,000; {len(resources)} run-resource rows. "
        "`acctempo_m4` is S_perf^0.6 × S_san_plus_v2^0.4 with floor 0.001. NVML energy is a GPU-only estimate; `train_seconds` sums recorded epoch train durations. "
        f"See source_inventory.json for verified archive provenance.\n\n`cohort_slice_status` contains {len(c)} audited SEEN/UNSEEN × STRICT/OVERLAP facts with "
        "OK/ONE_CLASS/SLICE_EMPTY flags. All four-slice sums match evaluation totals; prediction hashes are unique and strict flags valid. SEEN is a course that "
        "occurs in the real parent TRAIN of the same window. Companion package: cq_patchtst_v0_v6_full_facts_20261103 (V0–V6). Seeds 43/44 are outside this package.\n",
        encoding='utf8')
    files = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name != 'sha256sums.txt')
    (OUT / 'sha256sums.txt').write_text(''.join(sha(p) + '  ' + p.relative_to(OUT).as_posix() + '\n' for p in files), encoding='utf8')
    print(json.dumps({'cells': len(c), 'status_counts': summary['cohort_status_counts'], 'files_hashed': len(files)}, indent=2), flush=True)


if __name__ == '__main__':
    main()
