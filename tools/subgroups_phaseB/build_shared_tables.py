"""Phase B: shared tables of the 36 units from their summary.json files.
Writes into <WORK>/phaseB/shared_pkg:
  phaseB_units_summary.csv      one row per unit (status, mismatches, report-only differences, counts, builder commit)
  phaseB_report_only_diffs.csv  one row per unit and report-only metric: largest absolute difference ALL row vs accepted facts
  phaseB_two_class_cells.csv    one row per (task, window, split, phase, axis, value) cell with two classes only, with the number of pipelines affected and unit list
usage: build_shared_tables.py"""
import json
from pathlib import Path

import pandas as pd

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import WORK

U = Path(f'{WORK}/phaseB/units')
OUT = Path(f'{WORK}/phaseB/shared_pkg')
OUT.mkdir(parents=True, exist_ok=True)

summ, diffs, two = [], [], []
for d in sorted(U.glob('*_subgroups_20261121')):
    s = json.loads((d / 'summary.json').read_text())
    name = d.name.replace('_subgroups_20261121', '')
    ro = s.get('reported_only_max_abs_diff') or {}
    summ.append({'unit': name, 'status': s['status'], 'rows': s['rows'], 'partition_fail': len(s['partition_failures']), 'qa15': s['qa15_violations'],
                 'hash_unmatched': s['hash_unmatched'], 'no_salt': len(s['no_salt_match']), 'all_mismatch': len(s['all_row_mismatch']),
                 'columns_missing_vs_ALL': len(s['columns_of_accepted_ALL_row_missing_in_subgroup_rows']),
                 'two_class_cells': len(s['two_class_cells']), 'salts': ';'.join(s['salt_families_used']),
                 'builder_commit': s['builder']['repo_commit'], 'builder_build_subgroup_facts_sha256': s['builder']['sha256'].get('build_subgroup_facts.py', '')})
    for m, v in ro.items():
        diffs.append({'unit': name, 'metric': m, 'max_abs_diff': v})
    for c in s['two_class_cells']:
        two.append({'task': s['task'], 'window_id': c['window_id'], 'eval_split': c['eval_split'], 'phase_id': c['phase_id'],
                    'subgroup_axis': c['subgroup_axis'], 'subgroup_value': c['subgroup_value'], 'unit': name, 'pipeline_id': c['pipeline_id'], 'n_eval_samples': c['n_eval_samples']})
pd.DataFrame(summ).to_csv(OUT / 'phaseB_units_summary.csv', index=False, lineterminator='\n')
pd.DataFrame(diffs).to_csv(OUT / 'phaseB_report_only_diffs.csv', index=False, lineterminator='\n')
t = pd.DataFrame(two)
if len(t):
    g = t.groupby(['task', 'window_id', 'eval_split', 'phase_id', 'subgroup_axis', 'subgroup_value']).agg(
        n_eval_samples=('n_eval_samples', 'first'), n_unit_pipeline_rows=('unit', 'size'), n_units=('unit', 'nunique')).reset_index()
else:
    g = t
g.to_csv(OUT / 'phaseB_two_class_cells.csv', index=False, lineterminator='\n')
print(len(summ), 'units;', pd.DataFrame(summ).status.value_counts().to_dict(), '; two-class cells', len(g), 'distinct,', len(t), 'unit-pipeline rows')
