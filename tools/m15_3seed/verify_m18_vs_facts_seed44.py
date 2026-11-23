"""A.9 per-cell check: the six seed-44 facts packages (checkpoint_selection) against the M-18 training-history cell summary used for the M-18 package.
Compared per cell (task, window, pipeline, model): best_epoch vs best_epoch_manifest and best_epoch_by_val_macro_f1; best_score vs best_validation_macro_f1;
checkpoint_count_evaluated vs epochs_logged. Read-only. Writes verify_m18_vs_facts_seed44.csv and prints a summary.  usage: verify_m18_vs_facts_seed44.py <out_dir>"""
import glob
import sys

import pandas as pd

sys.path.insert(0, __import__('pathlib').Path(__file__).resolve().parents[1].joinpath('seed43_44_pipeline').as_posix())
from tempo_paths import A44

out = sys.argv[1]
m18 = pd.read_csv(f'{A44}/m18_44/m18_training_history_seed44_20261119/m18_training_history_cell_summary_seed44.csv')
parts = []
for f in sorted(glob.glob(f'{A44}/facts44/*seed44/**/checkpoint_selection.csv', recursive=True)):
    parts.append(pd.read_csv(f))
fx = pd.concat(parts, ignore_index=True)
key = ['task', 'window_id', 'pipeline_id', 'model_name']
m = fx.merge(m18, on=key, how='outer', suffixes=('_facts', '_m18'), indicator=True)
m['best_epoch_vs_manifest'] = m.best_epoch == m.best_epoch_manifest
m['best_epoch_vs_val_f1'] = m.best_epoch == m.best_epoch_by_val_macro_f1
m['best_score_abs_diff'] = (m.best_score - m.best_validation_macro_f1).abs()
m['n_checkpoints_equal_epochs_logged'] = m.checkpoint_count_evaluated == m.epochs_logged
cols = key + ['_merge', 'best_epoch', 'best_epoch_manifest', 'best_epoch_by_val_macro_f1', 'best_epoch_vs_manifest', 'best_epoch_vs_val_f1', 'best_score', 'best_validation_macro_f1', 'best_score_abs_diff',
              'checkpoint_count_evaluated', 'epochs_logged', 'n_checkpoints_equal_epochs_logged']
m[cols].to_csv(f'{out}/verify_m18_vs_facts_seed44.csv', index=False, lineterminator='\n')
print('facts cells', len(fx), 'm18 cells', len(m18), 'merge', m._merge.value_counts().to_dict())
b = m[m._merge == 'both']
print('both', len(b), '| best_epoch==manifest', int(b.best_epoch_vs_manifest.sum()), '| ==val_f1', int(b.best_epoch_vs_val_f1.sum()),
      '| max |best_score diff|', float(b.best_score_abs_diff.max()), '| n_checkpoints==epochs_logged', int(b.n_checkpoints_equal_epochs_logged.sum()))
print(b.groupby(['task', 'model_name']).size().to_dict())
