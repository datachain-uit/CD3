"""Construct a transparent partial S0 profile from exact current-state facts."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.data import fit_layout

ROOT = Path('CQ/resuilt/m13a_s0_profile_20261108')
ROOT.mkdir(parents=True, exist_ok=True)
SOURCES = {
    'CQ': Path('CQ/resuilt/s0_current_cq_20261108/L2_facts/task=CQ'),
    'LO': Path('LO/resuilt/s0_current_lo_modal_20261108/L2_facts'),
}
CLASSES = {'CQ': ['warning', 'average', 'good'], 'LO': ['I/D', 'G', 'E']}
UNAVAILABLE = ['ev_mean_observed_fraction', 'ev_mean_observed_length', 'tr_zero_activity_ratio',
               'tr_inactive_learner_ratio', 'tr_incomplete_history_ratio', 'tr_mean_events_per_enrollment',
               'tr_missing_label_mi_max', 'ev_train_overlap_share', 'days_train_end_to_test_start',
               'train_history_span_days', 'drift_tr_ev_psi_mean', 'drift_phase_prev_psi_mean']
INPUT_ROOTS = {'CQ': Path('downloads/vastai/CQ_V2_2_clean_grain_seed42'),
               'LO': Path('downloads/vastai/LO_V3_1_clean_grain_seed42')}
EXPECTED_IDS = {'CQ': 'sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045',
                'LO': 'sha256:2edf8cc293044d29c360cb2db71b8d21e26e2187cf40c6d45266f342a826d35b'}
offering_cache = {}
feature_cache = {}
overlap = pd.read_csv('CQ/resuilt/m07_split_evidence_received_20261107/temporal_overlap.csv')
if overlap.duplicated(['window_id', 'split']).any() or set(overlap.task) != {'CQ'}:
    raise ValueError('CQ overlap evidence has ambiguous keys')
overlap = overlap.set_index(['window_id', 'split'])

def offering_count(task, window, split, phase, expected_rows):
    key = (task, window, split, 'ALL' if split in ('TRAIN', 'VALIDATION') else phase)
    if key not in offering_cache:
        base = INPUT_ROOTS[task]
        m = json.loads((base / 'download_manifest.json').read_text(encoding='utf8'))
        if m['data_release_id'] != EXPECTED_IDS[task]:
            raise ValueError(f'Input release identity mismatch for {task}')
        rel = f'train/{window}/V0/train.parquet' if split == 'TRAIN' else (f'evaluation/{window}/V0/validation.parquet' if split == 'VALIDATION' else f'evaluation/{window}/V0/test_{phase}.parquet')
        df = pd.read_parquet(base / rel, columns=['enrollment_id', 'context__offering_id', 'context__timeline_source'])
        if len(df) != expected_rows or df.isna().any().any() or df.enrollment_id.duplicated().any():
            raise ValueError(f'Invalid S0-aligned cohort input {task}/{window}/{split}/{phase}')
        offering_cache[key] = (len(df), len(df[['context__offering_id', 'context__timeline_source']].drop_duplicates()))
    n, count = offering_cache[key]
    if n != expected_rows:
        raise ValueError(f'Cached cohort size mismatch {key}')
    return count

def feature_counts(task, window):
    key = (task, window)
    if key not in feature_cache:
        path = INPUT_ROOTS[task] / f'train/{window}/V0/train.parquet'
        batch = next(pq.ParquetFile(path).iter_batches(batch_size=1)).to_pandas()
        layout = fit_layout(batch, task=task, phase_id='P4', use_masks=True)
        seq, static = len(layout.dynamic_bases), len(layout.static_columns)
        feature_cache[key] = (seq, static)
    return feature_cache[key]

rows = []
for task, base in SOURCES.items():
    if not base.exists():
        continue
    for window in ('W1', 'W2', 'W3'):
        for phase_num in range(1, 5):
            phase = f'P{phase_num}'
            folder = base / f'window_id={window}' / f'phase_id={phase}'
            files = [folder / f'{kind}.parquet' for kind in ('dq_feature_profile', 'dataset_quality_summary', 'class_distribution', 'drift_measures')]
            if not all(p.exists() for p in files):
                continue
            dq, quality, classes, drift = (pd.read_parquet(p) for p in files)
            if set(dq.task) != {task} or set(dq.window_id) != {window} or set(dq.phase_id) != {phase} or set(dq.stage) != {'S0_RAW'}:
                raise ValueError(f'S0 identity mismatch {task}/{window}/{phase}')
            train_dq = dq[(dq.split == 'TRAIN') & (dq.feature_family == 'all')]
            train_quality = quality[quality.split == 'TRAIN']
            train_classes = classes[classes.split == 'TRAIN'].set_index('class_code')
            if len(train_dq) != 1 or len(train_quality) != 1 or set(train_classes.index) != set(CLASSES[task]):
                raise ValueError(f'Bad TRAIN facts: {task}/{window}/{phase}')
            td, tq = train_dq.iloc[0], train_quality.iloc[0]
            counts = [int(train_classes.loc[c, 'class_count']) for c in CLASSES[task]]
            n = int(tq.n_rows_profiled)
            if sum(counts) != n:
                raise ValueError(f'Class counts do not sum to TRAIN rows: {task}/{window}/{phase}')
            for split in ('VALIDATION', 'TEST'):
                e = dq[(dq.split == split) & (dq.feature_family == 'all')]
                eq = quality[quality.split == split]
                if len(e) != 1 or len(eq) != 1:
                    raise ValueError(f'Bad EVAL facts: {task}/{window}/{phase}/{split}')
                e, eq = e.iloc[0], eq.iloc[0]
                row = {'task': task, 'feature_regime': 'CQ_RAW_EARLY' if task == 'CQ' else 'LO_FULL_EARLY',
                       'window_id': window, 'phase_id': phase, 'cohort': 'ALL', 'eval_split': split,
                       'subgroup_axis': 'ALL', 'subgroup_value': 'ALL', 'tr_n_enrollments': n,
                       'ev_n_enrollments': int(eq.n_rows_profiled), 'tr_imbalance_ratio': float(train_classes.iloc[0].imbalance_ratio),
                       'tr_minority_ratio': min(counts) / n, 'tr_class_entropy_norm': float(train_classes.iloc[0].class_entropy_norm),
                       'tr_missing_rate': float(td.missing_rate), 'ev_missing_rate': float(e.missing_rate),
                       'tr_unavailable_rate': float(td.unavailable_rate), 'tr_structural_absence_rate': float(td.structural_absence_rate),
                       'tr_observed_zero_rate': float(td.observed_zero_rate), 'has_prev_phase': phase_num > 1}
                denominator = int(td.n_cells_observed_eligible)
                row['tr_sparsity_cell'] = ((int(td.n_cells_observed_zero) + int(td.n_cells_observed_missing)) / denominator
                                           if denominator else np.nan)
                row['tr_sparsity_cell_reason'] = None if denominator else 'NO_OBSERVED_ELIGIBLE_CELLS'
                row['tr_n_offerings'] = offering_count(task, window, 'TRAIN', phase, n)
                row['ev_n_offerings'] = offering_count(task, window, split, phase, int(eq.n_rows_profiled))
                row['tr_n_features_seq'], row['tr_n_features_static'] = feature_counts(task, window)
                row['tr_n_features_total'] = row['tr_n_features_seq'] + row['tr_n_features_static']
                row.update({f'tr_class_count_c{i}': c for i, c in enumerate(counts)})
                for name in ('n_cells_total', 'n_cells_unavailable', 'n_cells_structural_absence', 'n_cells_observed_eligible', 'n_cells_observed_value', 'n_cells_observed_missing', 'n_cells_observed_zero'):
                    row['tr_' + name] = int(td[name]); row['ev_' + name] = int(e[name])
                # S0 producer profiles full P1-P4 for TRAIN and VALIDATION at
                # every phase. Preserve those values as pooled facts, never
                # label them as prefix-specific M-13 state for P1-P3.
                for name in ('missing_rate', 'unavailable_rate', 'structural_absence_rate', 'observed_zero_rate', 'sparsity_cell'):
                    row['trpool_' + name] = row['tr_' + name]
                    if phase_num < 4:
                        row['tr_' + name] = np.nan
                        row['tr_' + name + '_reason'] = 'S0_TRAIN_IS_FULL_TRAJECTORY_PREFIX_RECOMPUTE_REQUIRED'
                for name in ('n_cells_total', 'n_cells_unavailable', 'n_cells_structural_absence', 'n_cells_observed_eligible', 'n_cells_observed_value', 'n_cells_observed_missing', 'n_cells_observed_zero'):
                    row['trpool_' + name] = row['tr_' + name]
                    if phase_num < 4:
                        row['tr_' + name] = None
                        row['tr_' + name + '_reason'] = 'S0_TRAIN_IS_FULL_TRAJECTORY_PREFIX_RECOMPUTE_REQUIRED'
                    if split == 'VALIDATION' and phase_num < 4:
                        row['evpool_' + name] = row['ev_' + name]
                        row['ev_' + name] = None
                        row['ev_' + name + '_reason'] = 'S0_VALIDATION_IS_FULL_TRAJECTORY_PREFIX_RECOMPUTE_REQUIRED'
                if split == 'VALIDATION' and phase_num < 4:
                    row['evpool_missing_rate'] = row['ev_missing_rate']
                    row['ev_missing_rate'] = np.nan
                    row['ev_missing_rate_reason'] = 'S0_VALIDATION_IS_FULL_TRAJECTORY_PREFIX_RECOMPUTE_REQUIRED'
                subset = drift[(drift.comparison == 'TRAIN_VS_EVAL') & (drift.split == split)]
                row['drift_tr_ev_jsd_mean'] = float(subset.jsd_base2.mean()) if len(subset) else np.nan
                for name in UNAVAILABLE:
                    row[name] = np.nan
                    row[name + '_reason'] = 'NOT_IN_S0_FACTS_REQUIRES_SOURCE_AUDIT'
                if task == 'CQ':
                    overlap_row = overlap.loc[(window, split.lower())]
                    if int(overlap_row.evaluation_enrollment_count) != int(eq.n_rows_profiled):
                        raise ValueError(f'CQ overlap cohort mismatch {window}/{split}')
                    row['ev_train_overlap_share'] = float(overlap_row.offering_start_overlap_share)
                    row['ev_train_overlap_share_reason'] = None
                row['drift_phase_prev_psi_mean_reason'] = 'NO_PREVIOUS_PHASE' if phase_num == 1 else 'PSI_NOT_IN_S0_FACTS'
                rows.append(row)
frame = pd.DataFrame(rows)
if frame.empty:
    raise RuntimeError('No matching current S0 facts available')
keys = ['task', 'window_id', 'phase_id', 'eval_split']
if frame.duplicated(keys).any():
    raise ValueError('Duplicate state keys')
for field in ('tr_missing_rate', 'tr_minority_ratio'):
    frame[field + '_prev'] = frame.sort_values('phase_id').groupby(['task', 'window_id', 'eval_split'])[field].shift()
    frame[field + '_prev_reason'] = np.where(frame.phase_id.eq('P1'), 'NO_PREVIOUS_PHASE',
                                             np.where(frame[field + '_prev'].isna(), 'SOURCE_PREFIX_NOT_AVAILABLE', None))
    p1 = frame[frame.phase_id.eq('P1')].set_index(['task', 'window_id', 'eval_split'])[field]
    frame[field + '_delta_p1'] = [row[field] - p1.loc[(row.task, row.window_id, row.eval_split)] for _, row in frame.iterrows()]
frame.to_csv(ROOT / 's0_profile_partial.csv', index=False)
frame.to_parquet(ROOT / 's0_profile_partial.parquet', index=False)
summary = {'rows': len(frame), 'rows_by_task': frame.task.value_counts().to_dict(), 'required_rows': 48,
           'status': 'PARTIAL_NOT_FOR_OFFICIAL_ASSEMBLY', 'missing_required_fields': UNAVAILABLE,
           'missing_due_to_prefix': ['tr_missing_rate', 'tr_unavailable_rate', 'tr_structural_absence_rate',
                                     'tr_observed_zero_rate', 'tr_sparsity_cell', 'tr_n_cells_*', 'ev_missing_rate_for_validation',
                                     'ev_n_cells_*_for_validation', 'tr_missing_rate_prev', 'tr_missing_rate_delta_p1'],
           'prefix_warning': 'S0 TRAIN and VALIDATION facts represent full P1-P4; P1-P3 rate/count fields are NULL until recomputed at cutoff',
           'source_note': 'S0_RAW facts with exact current S0 state identities; no validation/test label features included'}
(ROOT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
(ROOT / 'README.md').write_text('# S0 profile partial — not an M-14 input\n\nThe S0 producer profiles the full P1-P4 trajectory for TRAIN and VALIDATION at every phase; those fields are preserved as trpool_/evpool_, while prefix-specific rates/counts are NULL for P1-P3 until recomputed at cutoff. TEST facts are prefix views. Class counts/entropy/imbalance are TRAIN only. Offering counts use distinct (context__offering_id, context__timeline_source) from locally downloaded V0 model-input cohorts after validating release ID, row counts, no nulls and unique enrollment IDs; this checks cohort context but is not an independent checksum of every input parquet against its original source. Feature counts use the current fit_layout numeric dynamic bases (not four copies per phase) plus static columns, excluding auxiliary mask/timing channels, from the V0 schema after the current regime; historical model-specific layouts may differ, so this is a state-level convention needing assembler confirmation. CQ overlap uses M-07 offering-start-before-training-cutoff share with source cohort count checked; LO overlap remains NULL. JSD is the unweighted mean of available TRAIN_VS_EVAL per-feature phase-matched JSD. Missing fields are NULL with reasons. P1 has no previous phase. This partial export does not satisfy M-13a.\n', encoding='utf8')
with (ROOT / 'sha256sums.txt').open('w', encoding='utf8') as out:
    for name in ('s0_profile_partial.csv', 's0_profile_partial.parquet', 'summary.json', 'README.md'):
        out.write(f"{hashlib.sha256((ROOT/name).read_bytes()).hexdigest()}  {name}\n")
print(json.dumps(summary, indent=2))
