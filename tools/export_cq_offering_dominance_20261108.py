"""Join CQ offering dominance thresholds to the seed-42 recurrent facts."""
from pathlib import Path
import hashlib
import json
import pandas as pd

root = Path('CQ/resuilt/cq_offering_dominance_20261108')
root.mkdir(parents=True, exist_ok=True)
src = Path('CQ/resuilt/cq_class_offering_support_20261103')
facts_path = Path('CQ/resuilt/input/results/GD1_CQ_V2_2_clean_r1/cq_family_pipeline_window_phase_metrics.parquet')
support = pd.read_csv(src / 'class_offering_support.csv')
support['single_offering_dominant'] = support.top_offering_share.ge(.5)
evaluation = support[support.eval_split.isin(['VALIDATION', 'TEST'])].copy()
assert len(evaluation) == 18 and not evaluation.duplicated(['window_id', 'eval_split', 'class_index']).any()
dom = evaluation.pivot(index=['window_id', 'eval_split'], columns='class_index', values='single_offering_dominant')
dom.columns = [f'c{c}_single_offering_dominant' for c in dom.columns]
dom = dom.reset_index()
flags = pd.read_csv(src / 'cell_flags.csv')
flags = flags.merge(dom, on=['window_id', 'eval_split'], validate='many_to_one')
flags['single_offering_dominant'] = flags[[f'c{i}_single_offering_dominant' for i in range(3)]].any(axis=1)
facts = pd.read_parquet(facts_path)
keys = ['task', 'window_id', 'pipeline_id', 'model_name', 'seed', 'eval_split', 'phase_id']
assert len(flags) == len(facts) == 1632 and not flags.duplicated(keys).any() and not facts.duplicated(keys).any()
joined = flags.merge(facts[keys], on=keys, how='outer', indicator=True, validate='one_to_one')
assert joined._merge.eq('both').all()
patch_facts = pd.read_parquet('CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103/sanity_components.parquet')
support_n = evaluation.groupby(['window_id', 'eval_split'], as_index=False).n_support.sum()
patch_check = patch_facts.merge(support_n, on=['window_id', 'eval_split'], validate='many_to_one')
if not patch_check.n_eval_samples.eq(patch_check.n_support).all():
    raise ValueError('PatchTST evaluation support differs from source offering cohort')
patch = patch_facts[keys].merge(dom, on=['window_id', 'eval_split'], validate='many_to_one')
patch['single_offering_dominant'] = patch[[f'c{i}_single_offering_dominant' for i in range(3)]].any(axis=1)
assert len(patch) == 168 and not patch.duplicated(keys).any()
phase1 = pd.concat([flags, patch], ignore_index=True)
assert len(phase1) == 1800 and not phase1.duplicated(keys).any()
support.to_csv(root / 'class_offering_support.csv', index=False)
flags.to_csv(root / 'cell_flags.csv', index=False)
flags.to_parquet(root / 'cell_flags.parquet', index=False)
phase1.to_csv(root / 'cell_flags_phase1.csv', index=False)
phase1.to_parquet(root / 'cell_flags_phase1.parquet', index=False)
summary = {'task': 'CQ', 'cells': len(flags), 'dominant_cells': int(flags.single_offering_dominant.sum()),
           'phase1_cells': len(phase1), 'phase1_dominant_cells': int(phase1.single_offering_dominant.sum()),
           'threshold': 'top_offering_share >= 0.5', 'offering_unit': 'offering_id x timeline_source',
           'keys_match_r4': 'PASS', 'cluster_bootstrap': 'PILOT_4_CELLS_ONLY' if (root / 'offering_bootstrap_pilot_w1_v0_test_p1.csv').exists() else 'NOT_YET_RUN'}
(root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
(root / 'README.md').write_text('# CQ offering dominance — seed 42\n\nDerived from the existing CQ class offering support table and matched one-to-one with 1,632 R4 cell keys. The phase1 table additionally contains 168 PatchTST V0–V6 keys. The flag is true when the largest offering share for any class is at least 0.5. Clustered bootstrap is present only for the four W1/V0/TEST/P1 recurrent pilot cells; it is not complete for all flagged cells.\n', encoding='utf8')
with (root / 'sha256sums.txt').open('w', encoding='utf8') as out:
    for file in sorted(root.iterdir()):
        if file.is_file() and file.name != 'sha256sums.txt' and not file.name.endswith('_probe.parquet'):
            out.write(f'{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}\n')
print(json.dumps(summary, indent=2))
