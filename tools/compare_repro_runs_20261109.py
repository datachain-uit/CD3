"""Compare two runs of the same Mantis cell (same seed, independent caches): row ids, probabilities, argmax, metrics, adapter, cell record.
Usage: python tools/compare_repro_runs_20261109.py --a DIR_A --b DIR_B --window W2 --pipeline V2 --out report.json
DIR_* hold runs/<W>/<V>/ and adapters/<W>/ as unpacked from a result tar."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--a', type=Path, required=True)
ap.add_argument('--b', type=Path, required=True)
ap.add_argument('--window', required=True)
ap.add_argument('--pipeline', required=True)
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
ra, rb = (d / 'runs' / args.window / args.pipeline for d in (args.a, args.b))
out = {'window': args.window, 'pipeline': args.pipeline}

# probabilities (result/*.npy) and predictions (per phase)
for split in ('validation', 'test'):
    pa, pb = np.load(ra / 'result' / f'{split}_probabilities.npy'), np.load(rb / 'result' / f'{split}_probabilities.npy')
    out[f'{split}_probabilities'] = {'shape_a': list(pa.shape), 'shape_b': list(pb.shape), 'identical_bytes': bool(pa.tobytes() == pb.tobytes()),
                                    'max_abs_diff': float(np.abs(pa - pb).max()), 'mean_abs_diff': float(np.abs(pa - pb).mean()),
                                    'argmax_equal_share': float((pa.argmax(-1) == pb.argmax(-1)).mean()),
                                    'sha256_a': hashlib.sha256(pa.tobytes()).hexdigest()[:16], 'sha256_b': hashlib.sha256(pb.tobytes()).hexdigest()[:16]}
pred = {}
for f in sorted((ra / 'predictions').glob('*.parquet')):
    a, b = pd.read_parquet(f), pd.read_parquet(rb / 'predictions' / f.name)
    same_ids = bool((a.enrollment_id_hash.to_numpy() == b.enrollment_id_hash.to_numpy()).all()) if len(a) == len(b) else False
    pc = [c for c in a.columns if c.startswith('prob_c')]
    pred[f.stem] = {'rows_a': len(a), 'rows_b': len(b), 'row_ids_identical_in_order': same_ids,
                    'y_true_equal': bool((a.y_true.to_numpy() == b.y_true.to_numpy()).all()) if len(a) == len(b) else False,
                    'y_pred_equal_share': float((a.y_pred.to_numpy() == b.y_pred.to_numpy()).mean()) if len(a) == len(b) else None,
                    'prob_max_abs_diff': float(np.abs(a[pc].to_numpy() - b[pc].to_numpy()).max()) if len(a) == len(b) else None,
                    'file_sha256_equal': sha(f) == sha(rb / 'predictions' / f.name)}
out['predictions'] = pred
# metrics_overall
ma, mb = pd.read_parquet(ra / 'metrics_overall.parquet'), pd.read_parquet(rb / 'metrics_overall.parquet')
num = [c for c in ma.columns if pd.api.types.is_numeric_dtype(ma[c]) and c in mb.columns and c not in ('seed',)]
out['metrics_overall'] = {'rows': [len(ma), len(mb)], 'max_abs_diff_per_column': {c: float(np.abs(ma[c].to_numpy(float) - mb[c].to_numpy(float)).max()) for c in num}}
# adapter and cell record
aa, ab = args.a / 'adapters' / args.window, args.b / 'adapters' / args.window
ja, jb = json.loads((aa / 'channel_adapter.json').read_text()), json.loads((ab / 'channel_adapter.json').read_text())
out['adapter'] = {'npz_sha256_equal': sha(aa / 'channel_adapter.npz') == sha(ab / 'channel_adapter.npz'), 'digest_a': ja.get('digest'), 'digest_b': jb.get('digest'),
                  'fit_rows_sha256_equal': ja.get('fit_rows_sha256') == jb.get('fit_rows_sha256'),
                  'explained_variance_equal': ja.get('explained_variance_ratio') == jb.get('explained_variance_ratio')}
ca, cb = (json.loads((r / 'result' / 'f3_cell_record.json').read_text()) for r in (ra, rb))
keys = ['spec_digest', 'encoder_digest', 'real_train_input_sha256', 'best_epoch', 'epochs_trained', 'train_rows_real', 'train_rows_synthetic', 'cache_mode']
out['cell_record'] = {k: {'a': ca.get(k), 'b': cb.get(k), 'equal': ca.get(k) == cb.get(k)} for k in keys}
ha, hb = ca['history'], cb['history']
out['history'] = {'epochs': [len(ha), len(hb)], 'max_abs_diff_validation_macro_f1': float(max(abs(x['validation_macro_f1_mean_p1_p4'] - y['validation_macro_f1_mean_p1_p4']) for x, y in zip(ha, hb)))}
args.out.write_text(json.dumps(out, indent=1, default=str) + '\n', encoding='utf-8')
print(json.dumps({'val_prob_identical': out['validation_probabilities']['identical_bytes'], 'val_prob_max_abs_diff': out['validation_probabilities']['max_abs_diff'],
                  'test_prob_identical': out['test_probabilities']['identical_bytes'], 'test_prob_max_abs_diff': out['test_probabilities']['max_abs_diff'],
                  'argmax_equal_val_test': [out['validation_probabilities']['argmax_equal_share'], out['test_probabilities']['argmax_equal_share']],
                  'predictions_files': len(pred), 'row_ids_identical_all': all(v['row_ids_identical_in_order'] for v in pred.values()),
                  'file_sha256_equal_all': all(v['file_sha256_equal'] for v in pred.values()),
                  'metrics_max_diff': max(out['metrics_overall']['max_abs_diff_per_column'].values()), 'adapter': out['adapter'],
                  'cell_record_equal': {k: v['equal'] for k, v in out['cell_record'].items()}, 'history': out['history']}, indent=1))
