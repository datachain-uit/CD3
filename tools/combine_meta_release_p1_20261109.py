"""M-14: combine the two phase-1 meta-releases (CQ_V2_2_p1, LO_V3_1_p1, built by `metamodel assemble --planned-seeds 42`)
into meta_release_CQ_LO_p1/ : row-wise concatenation of seed_level and seed_agg (union of columns), merged column dictionary,
manifest with the sha256 of every input fact/resource/context file and of both child releases, RUN_LOG.md, sha256sums.txt.
Usage: python tools/combine_meta_release_p1_20261109.py --cq DIR --lo DIR --pkg DIR --inputs-json FILE --out DIR
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--cq', type=Path, required=True)
ap.add_argument('--lo', type=Path, required=True)
ap.add_argument('--pkg', type=Path, required=True, help='dir holding metamodel/ and tempo_fix/')
ap.add_argument('--inputs-json', type=Path, required=True, help='{"label": "path", ...} of every input file to hash')
ap.add_argument('--notes', type=Path, required=True, help='markdown with commands, test results and QA notes for RUN_LOG.md')
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()



def _py(v):
    if isinstance(v, (list, tuple)) or (hasattr(v, 'dtype') and getattr(v, 'ndim', 0) > 0):
        return [_py(x) for x in v]
    return v.item() if hasattr(v, 'item') else v


args.out.mkdir(parents=True, exist_ok=True)
child = {}
for name, d in (('CQ_V2_2_p1', args.cq), ('LO_V3_1_p1', args.lo)):
    m = json.loads((d / 'meta_release_manifest.json').read_text(encoding='utf-8'))
    child[name] = {'manifest': m, 'files': {p.name: sha(p) for p in sorted(d.iterdir()) if p.is_file()}}

tables = {}
for t in ('meta_dataset_seed_level', 'meta_dataset_seed_agg'):
    a = pd.read_parquet(args.cq / f'{t}.parquet')
    b = pd.read_parquet(args.lo / f'{t}.parquet')
    both = pd.concat([a, b], ignore_index=True, sort=False)
    both = both[list(dict.fromkeys(list(a.columns) + list(b.columns)))]
    for col in both.columns[both.dtypes == object]:
        # array-valued cells (e.g. confusion_matrix stored as ndarray in one child, as text in the other) -> JSON text
        both[col] = both[col].map(lambda v: json.dumps(_py(v)) if isinstance(v, (list, tuple)) or hasattr(v, 'tolist') else v)
    tables[t] = both
    both.to_parquet(args.out / f'{t}.parquet', index=False)
    both.to_csv(args.out / f'{t}.csv', index=False)
    print(t, a.shape, b.shape, '->', both.shape)

sl, ag = tables['meta_dataset_seed_level'], tables['meta_dataset_seed_agg']
expected = child['CQ_V2_2_p1']['manifest']['n_rows_seed_level'] + child['LO_V3_1_p1']['manifest']['n_rows_seed_level']
assert len(sl) == expected, (len(sl), expected)  # sum of the two children (3,432 for F2 = V0-V6; 3,672 for V0-V16)
assert (ag.row_status_agg == 'COMPLETE').all() if 'row_status_agg' in ag.columns else True
dup = sl.duplicated([c for c in ('task', 'window_id', 'seed', 'phase_id', 'cohort', 'eval_split', 'subgroup_axis', 'subgroup_value', 'model_name', 'pipeline_id') if c in sl.columns]).sum()
assert dup == 0, f'{dup} duplicate fact keys'

cq_d = pd.read_csv(args.cq / 'meta_column_dictionary.csv')
lo_d = pd.read_csv(args.lo / 'meta_column_dictionary.csv')
cd = pd.concat([cq_d, lo_d], ignore_index=True)
key = cd.columns[0]
role_conflicts = int(cd.groupby(key).role.nunique().gt(1).sum() + cd.groupby(key).block.nunique().gt(1).sum())
assert role_conflicts == 0, 'role/block differ between the two dictionaries'
conflicts = int(cd.drop_duplicates().groupby(key).size().gt(1).sum())
cd = cd.groupby(key, sort=False).agg(block=('block', 'first'), role=('role', 'first'), nullable=('nullable', 'max')).reset_index()
cd['dtype'] = cd[key].map(lambda c: str(sl[c].dtype) if c in sl.columns else '')
cd = cd[['column_name', 'block', 'role', 'dtype', 'nullable']] if list(cq_d.columns) == ['column_name', 'block', 'role', 'dtype', 'nullable'] else cd
cd.to_csv(args.out / 'meta_column_dictionary.csv', index=False)

inputs = json.loads(args.inputs_json.read_text(encoding='utf-8'))
manifest = {
    'meta_release_id': 'meta_release_CQ_LO_p1', 'created_utc': datetime.now(timezone.utc).isoformat(),
    'phase': 1, 'planned_seeds': [42], 'synthetic': False,
    'n_rows_seed_level': int(len(sl)), 'n_rows_seed_agg': int(len(ag)),
    'rows_by_task': sl.task.value_counts().to_dict(),
    'f2_scope': 'CQ PatchTST V0-V16 (Q-30 (b), author decision 2026-11-09)',
    'lo_f0': 'NOT_AVAILABLE_PHASE1', 's0_profile': 'v4 (tr_inactive_learner_ratio removed, Q-28)',
    'excluded_by_design': ['lo_patchtst_v0_v16_full_facts_20261109 (MIXED_LEAK_PROBE, Q-27)', 'CQ MANTIS_V2 (EXPLORATORY)'],
    'registry': 'tempo_fix/examples/registries_v1.6 (registries_rev_2026-11-09)',
    'registry_manifest_sha256': sha(args.pkg / 'tempo_fix/examples/registries_v1.6/registry_manifest.json'),
    'metamodel_version': json.loads(json.dumps(child['CQ_V2_2_p1']['manifest']['builder_version'])),
    'column_dictionary': {'columns': int(len(cd)), 'differences_between_children_resolved': int(conflicts), 'rule': 'role/block identical in both; nullable = any; dtype from the combined seed_level table'},
    'registry_imputer_only_ref_status': child['CQ_V2_2_p1']['manifest'].get('registry_imputer_only_ref_status'),
    'imputer_only_ref_definition': child['CQ_V2_2_p1']['manifest'].get('imputer_only_ref_definition'),
    'has_state_profile': {k: v['manifest'].get('has_state_profile') for k, v in child.items()},
    'has_f0_reference': {k: v['manifest'].get('has_f0_reference') for k, v in child.items()},
    'builder_version': child['CQ_V2_2_p1']['manifest'].get('builder_version'),
    'child_releases': {k: {'manifest_sha256': v['files']['meta_release_manifest.json'], 'qa_pass_rates': v['manifest']['qa_pass_rates'],
                           'row_status_counts': v['manifest']['row_status_counts'], 'files_sha256': v['files']} for k, v in child.items()},
    'input_files_sha256': {label: {'path': str(p), 'sha256': sha(p)} for label, p in inputs.items()},
    'known_qa_note': 'qa_run_level_invariant_ok = 0.0 in both children: the check requires s_leak constant within a run (8 rows = 4 phases x 2 splits) '
                     'while s_leak is defined per (window, split, phase) in the source facts; s_eff passes (0 violations). See RUN_LOG.md.',
}
(args.out / 'meta_release_manifest.json').write_text(json.dumps(manifest, indent=2, default=str) + '\n', encoding='utf-8')

freeze = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
log = ['# RUN_LOG — meta_release_CQ_LO_p1 (M-14)', '', f'Created {manifest["created_utc"]} UTC.', '',
       args.notes.read_text(encoding='utf-8'), '', '## pip freeze', '', '```', freeze.strip(), '```', '']
(args.out / 'RUN_LOG.md').write_text('\n'.join(log), encoding='utf-8')
files = sorted(p for p in args.out.rglob('*') if p.is_file() and p.name != 'sha256sums.txt')
with open(args.out / 'sha256sums.txt', 'w', encoding='utf-8', newline='\n') as fh:  # LF endings so `sha256sum -c` works on Linux
    fh.write(''.join(sha(p) + '  ' + p.relative_to(args.out).as_posix() + '\n' for p in files))
print('written', args.out, len(files), 'files; column-dictionary conflicts', conflicts)
