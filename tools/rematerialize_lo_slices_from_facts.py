"""Correct LO slice composites from existing sufficient statistics and real-parent facts.

No predictions or training are repeated. Entropy, calibration, and performance
components are reused from old slice facts; predicted class counts come from
their confusion matrix. ALL must agree with the independently computed sanity
facts before any family is accepted. Write a new immutable output tree.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from metrics_core.evaluation import COMPOSITE_EPS, _jsd_base2
from tools.vastai_metadata_contract import PARENT_PIPELINES
from tools.vastai_audit_shared import _class_ids

KEYS = ['task', 'seed', 'model_name', 'window_id', 'pipeline_id', 'eval_split', 'phase_id']
CHECK = ['macro_f1', 'balanced_acc', 's_perf', 's_nan', 's_maj_jsd', 's_ent',
         's_drift', 's_eff', 's_leak', 's_san_plus', 'acctempo_m3']


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            sha.update(block)
    return 'sha256:' + sha.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--audit-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(f'Refusing to overwrite {args.out}')
    counts, input_hash = {}, {}
    for w in ('W1', 'W2', 'W3'):
        for parent in ('V0', 'V1', 'V5', 'V9', 'V13'):
            path = args.data_root / 'train' / w / parent / 'train.parquet'
            y = pd.read_parquet(path, columns=['LO_performance_label_3'])
            counts[(w, parent)] = np.bincount(_class_ids(y['LO_performance_label_3'], 'LO'), minlength=3)
            input_hash[str(path)] = digest(path)
            print('parent', w, parent, counts[(w, parent)].tolist(), flush=True)
    results = []
    for family in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
        old = args.audit_root / 'LO' / family / 'seed=42' / 'LO' / family / 'seed=42'
        sanity = pd.read_parquet(old / 'sanity_components.parquet')
        slices = pd.read_parquet(old / 'evaluation_slices.parquet')
        if len(sanity) != 408 or len(slices) != 1224 or sanity.duplicated(KEYS).any() or slices.duplicated(KEYS + ['slice']).any():
            raise ValueError(f'Unexpected coverage for {family}')
        parent_values = sanity[KEYS + ['s_eff', 's_leak']].rename(columns={'s_eff': '_s_eff', 's_leak': '_s_leak'})
        corrected = slices.merge(parent_values, on=KEYS, validate='many_to_one')
        for idx, row in corrected.iterrows():
            matrix = np.stack(row.confusion_matrix)
            pred_counts = matrix.sum(axis=0)
            parent = PARENT_PIPELINES.get(row.pipeline_id, row.pipeline_id)
            drift = 1 - _jsd_base2(pred_counts, counts[(row.window_id, parent)])
            parts = [row.s_nan, row.s_maj_jsd, row.s_ent, drift, row['_s_eff'], row['_s_leak']]
            composite = float(np.prod(np.clip(parts, COMPOSITE_EPS, 1)) ** (1 / 6))
            acctempo = float(max(row.s_perf, COMPOSITE_EPS) ** 0.6 * max(composite, COMPOSITE_EPS) ** 0.4)
            corrected.loc[idx, ['s_drift', 's_eff', 's_leak', 's_san_plus', 'acctempo_m3']] = [drift, row['_s_eff'], row['_s_leak'], composite, acctempo]
            scal = max(0.0, 1.0 - float(row.ece))
            corrected.loc[idx, 's_cal'] = scal
            corrected.loc[idx, 's_san_plus_v2'] = float(np.prod(np.clip([row.s_nan, row.s_maj_jsd, scal, drift, row['_s_eff'], row['_s_leak']], COMPOSITE_EPS, 1)) ** (1 / 6))
        corrected = corrected.drop(columns=['_s_eff', '_s_leak'])
        all_rows = corrected[corrected['slice'] == 'ALL']
        compare = sanity[KEYS + CHECK].merge(all_rows[KEYS + CHECK], on=KEYS, validate='one_to_one', suffixes=('_sanity', '_slice'))
        differences = {c: float((compare[c + '_sanity'] - compare[c + '_slice']).abs().max()) for c in CHECK}
        if len(compare) != 408 or any(not np.isfinite(x) or x > 1e-9 for x in differences.values()):
            raise ValueError(f'{family}: ALL/sanity mismatch {differences}')
        results.append((family, old, corrected, differences))
        print('verified', family, differences, flush=True)
    for family, old, corrected, differences in results:
        dest = args.out / 'LO' / family / 'seed=42' / 'LO' / family / 'seed=42'
        dest.mkdir(parents=True)
        for name in ('canonical_s_leak', 'sanity_components', 'metrics_per_class', 'bootstrap_metrics_per_class', 'checkpoint_selection'):
            shutil.copy2(old / (name + '.parquet'), dest / (name + '.parquet'))
        corrected.to_parquet(dest / 'evaluation_slices.parquet', index=False)
        manifest = json.loads((old / 'audit_manifest.json').read_text(encoding='utf-8'))
        manifest.update({'audit_schema_version': 'vastai_posthoc_audit_v2_slice_parent_contract',
                         'correction_method': 'RECOMPUTED_FROM_SLICE_SUFFICIENT_STATISTICS_NOT_RAW_PREDICTIONS',
                         'source_audit_manifest_sha256': digest(old / 'audit_manifest.json'),
                         'source_evaluation_slices_sha256': digest(old / 'evaluation_slices.parquet'),
                         'source_sanity_sha256': digest(old / 'sanity_components.parquet'),
                         'parent_train_sha256': input_hash, 'all_slice_max_abs_diff': differences,
                         'created_at_utc': datetime.now(timezone.utc).isoformat()})
        (dest / 'audit_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        print('wrote', dest, flush=True)


if __name__ == '__main__':
    main()
