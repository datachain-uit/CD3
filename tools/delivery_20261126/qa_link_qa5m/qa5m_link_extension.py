#!/usr/bin/env python
"""qa5m_link_extension.py - closes the S1 link gap of the 5 MANTIS_V2 units (balanced pipelines have no model_parent_pipeline).
Inputs (all local): S1 manifests (src/S1_<TASK>), S2 sampling manifests (b34/src/seed4N), b4p mapping (seed 44), qa5 per-unit run csvs.
Run-level fields copy qa_pred_audit.py (canonical sha, QA11 / QA21 part 3 / QA13). Writes only into the output dir."""
import hashlib, json, sys
from pathlib import Path
import numpy as np, pandas as pd

BASE = Path(sys.argv[1])   # work directory holding qa5, b34, b4p, qa5m
OUT = BASE / 'qa5m'
QA5 = BASE / 'qa5' / 'full'
S2ROOT = BASE / 'b34' / 'src'
B4P = BASE / 'b4p' / 'deliver'


def canon_sha(obj):   # identical to qa_pred_audit.py
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


S1 = {}
for task in ('CQ', 'LO'):
    for f in (OUT / 'src' / f'S1_{task}').rglob('run_manifest.json'):
        b = f.read_bytes(); d = json.loads(b.decode('utf-8'))
        w, v = f.parts[-4], f.parts[-3]
        S1[(task, w, v)] = {'d': d, 'canon': canon_sha(d), 'file_sha': hashlib.sha256(b).hexdigest()}
assert len(S1) == 30, len(S1)

# S2 manifests: seeds 42/43 = b34/src/seedNN/<TASK>/<W>/<V>/run_manifest.json ; seed 44 = b34/src/seed44/<TASK>_<W>_<Vparent>__k.json
S2 = {}
for seed in (42, 43):
    for f in (S2ROOT / f'seed{seed}').rglob('run_manifest.json'):
        task, w, v = f.parts[-4], f.parts[-3], f.parts[-2]
        S2[(task, seed, w, v)] = json.loads(f.read_text(encoding='utf-8'))
for f in (S2ROOT / 'seed44').glob('*__*.json'):
    d = json.loads(f.read_text(encoding='utf-8'))
    S2[(d['task'], 44, d['window_id'], d['balance_pipeline'])] = d
print('S2 manifests', len(S2))

REG = {'V2': 'V1', 'V3': 'V1', 'V4': 'V1', 'V6': 'V5', 'V7': 'V5', 'V8': 'V5', 'V10': 'V9', 'V11': 'V9', 'V12': 'V9', 'V14': 'V13', 'V15': 'V13', 'V16': 'V13',
       'V1': 'V1', 'V5': 'V5', 'V9': 'V9', 'V13': 'V13', 'V0': 'V0'}      # tempo_fix/registries.py (expect map of the S2 plan)
b4 = pd.read_csv(B4P / 's2_seed44_per_run_link.csv')
b4 = b4[b4.model == 'MANTIS_V2'].set_index(['task', 'window', 'pipeline'])


def s1_fields(task, w, p):
    d = S1[(task, w, p)]['d']
    sp = d.get('splits') or {}
    return dict(
        future_imputed_cells_total=float(sum(x.get('future_imputed_cells', np.nan) for x in sp.values())), n_s1_splits=len(sp),
        fit_scope=d.get('fit_scope'), fit_rows=d.get('fit_rows'), train_rows=(sp.get('train') or {}).get('rows'),
        validation_test_mode=(d.get('scaling_contract') or {}).get('validation_test'), s1_preprocessor_sha256=d.get('preprocessor_sha256'))


rows = []
for f in sorted(QA5.glob('*MANTIS_V2*_qa_runs.csv')):
    u = pd.read_csv(f)
    task = f.name.split('_')[0]; model = 'MANTIS_V2'; sd = int(f.name.split('_seed')[1].split('_')[0])
    for r in u[u.s1_pipeline.isna()].itertuples():
        w, v = r.window_id, r.pipeline_id
        assert v not in ('V0', 'V1', 'V5', 'V9', 'V13')
        s2 = S2.get((task, sd, w, v))
        o = dict(task=task, model=model, seed=sd, window=w, pipeline=v)
        reg = REG[v]
        if s2 is None:
            o.update(linked_s1_pipeline=reg, link_method='registry_parent', link_verified='false: no S2 manifest found; registry mapping only')
        else:
            p = s2['parent_pipeline']
            checks = {
                'S2 seed==unit seed': int(s2['seed']) == sd and s2.get('seed_augmentation') == sd,
                'S2 balance_pipeline/window match': s2['balance_pipeline'] == v and s2['window_id'] == w,
                'S2 parent==registry parent': p == reg,
                'S2 parent_imputation_manifest_sha256==canonical sha of S1 manifest': s2.get('parent_imputation_manifest_sha256') == S1[(task, w, p)]['canon'],
                'S2 parent_imputation_run_id==S1 run_id': s2.get('parent_imputation_run_id') == S1[(task, w, p)]['d']['run_id'],
                'S2 parent_imputation_attempt_id==S1 attempt_id': s2.get('parent_imputation_attempt_id') == S1[(task, w, p)]['d']['attempt_id'],
                'S2 validation_test_touched false': s2.get('validation_test_touched') is False}
            hash_ok = checks['S2 parent_imputation_manifest_sha256==canonical sha of S1 manifest']
            o['linked_s1_pipeline'] = p
            o['s2_algorithm'] = (s2.get('algorithm_config') or {}).get('algorithm')
            o['s2_run_id_prefix'] = s2['run_id'][:16]
            if sd == 44:
                b = b4.loc[(task, w, v)]
                checks['b4p: model manifest parent==S2 parent'] = bool(b.parent_equal)
                checks['b4p: download_manifest sha256 equal and remote_path train/W/V'] = bool(b.ok_dm_sha) and bool(b.ok_path)
                checks['b4p: S2 run_id/attempt in 72-run set'] = bool(b.ref_in_set72) and str(b.s2_run_id) == s2['run_id'] and str(b.s2_attempt_id) == s2['attempt_id']
                o['link_method'] = 's2_download_mapping'
                ok = all(checks.values())
                o['link_verified'] = ('true: S2 parent hash == S1 canonical sha256 (S2->S1 by hash); model->S2 indirect via download_manifest sha256 + parent + run_id (no direct S2 field in the model run)' if ok
                                      else 'false: ' + '; '.join(k_ for k_, v_ in checks.items() if not v_))
            else:
                o['link_method'] = 's2_parent_hash'
                ok = all(checks.values())
                o['link_verified'] = ('true: S2 parent hash == S1 canonical sha256, run/attempt id equal, parent == registry; model->S2 by (task, window, pipeline, seed) key' if ok
                                      else 'false: ' + '; '.join(k_ for k_, v_ in checks.items() if not v_))
            if not hash_ok:
                o['link_method'] = 'registry_parent'; o['linked_s1_pipeline'] = reg
                o['link_verified'] = 'false: S2 hash mismatch; registry mapping only (' + o['link_verified'] + ')'
        o['registry_parent_agrees'] = o['linked_s1_pipeline'] == reg
        o.update(s1_fields(task, w, o['linked_s1_pipeline']))
        rows.append(o)

ext = pd.DataFrame(rows)
ext['link_verified_bool'] = ext.link_verified.str.startswith('true')
cols = ['task', 'model', 'seed', 'window', 'pipeline', 'linked_s1_pipeline', 'link_method', 'link_verified', 'future_imputed_cells_total', 'fit_scope', 'fit_rows', 'train_rows', 'validation_test_mode',
        's1_preprocessor_sha256', 'registry_parent_agrees', 's2_algorithm', 's2_run_id_prefix', 'n_s1_splits']
ext[cols].to_csv(OUT / 'qa5_mantis_link_extension.csv', index=False, lineterminator='\n')

ext['unit'] = ext.task + '_' + ext.model + '_seed' + ext.seed.astype(str)
sm = []
for f in sorted(QA5.glob('*_qa_runs.csv')):
    u = pd.read_csv(f); unit = f.name.replace('_qa_runs.csv', '')
    e = ext[ext.unit == unit]
    lk = u.s1_pipeline.notna()
    fut = u.qa11_future_imputed_cells_total
    sm.append(dict(unit=unit, runs=len(u), linked_before=int(lk.sum()), linked_added=len(e), linked_after=int(lk.sum()) + len(e),
                   qa11_sum_future_imputed_before=float(fut.sum()), qa11_sum_future_imputed_added=float(e.future_imputed_cells_total.sum()),
                   qa11_runs_nonzero_after=int((fut > 0).sum() + (e.future_imputed_cells_total > 0).sum()),
                   qa21p3_fit_scope_train_after=int(u.qa21p3_fit_scope.astype(str).str.startswith('TRAIN').sum() + e.fit_scope.astype(str).str.startswith('TRAIN').sum()),
                   qa21p3_fit_rows_le_train_after=int((u.qa21p3_fit_rows <= u.qa21p3_train_rows).sum() + (e.fit_rows <= e.train_rows).sum()),
                   qa21p3_transform_only_after=int((u.qa21p3_validation_test_mode == 'TRANSFORM_ONLY').sum() + (e.validation_test_mode == 'TRANSFORM_ONLY').sum()),
                   qa13_s1_preprocessor_sha256_after=int(u.qa13_s1_preprocessor_sha256.notna().sum() + e.s1_preprocessor_sha256.notna().sum()),
                   added_hash_verified=int(e.link_verified_bool.sum()), added_mapping_only=int((~e.link_verified_bool).sum())))
sm = pd.DataFrame(sm)
tot = sm.drop(columns='unit').sum(numeric_only=True); tot['unit'] = 'TOTAL'
sm = pd.concat([sm, tot.to_frame().T], ignore_index=True)
sm.to_csv(OUT / 'qa5_mantis_link_summary_by_unit.csv', index=False, lineterminator='\n')
pd.set_option('display.width', 250)
print(sm.to_string())
print(ext.groupby(['link_method', 'link_verified']).pipeline.count())
print('registry disagree:', int((~ext.registry_parent_agrees).sum()), '| nonzero future:', int((ext.future_imputed_cells_total > 0).sum()))
print(ext.fit_scope.value_counts().to_dict(), ext.validation_test_mode.value_counts().to_dict(), 'fit>train:', int((ext.fit_rows > ext.train_rows).sum()))
