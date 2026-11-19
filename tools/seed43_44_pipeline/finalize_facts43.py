"""Bring the seed-43 facts packages to the `_r2` format required by item 7 of the 13/11 request:
 - sanity_components: probe_fit_rows, s_leak_probe_n_eval, probe_score_scope (filled from the reference probe fit of the delivered seed-42 packages, same data; marked), model_tier, variant_role, run_purpose
 - checkpoint_selection: model_tier, variant_role, run_purpose on all 51 rows
 - resource_per_run: resource_null_reason, runner_git_commit_basis (+ the retroactive commit for Mantis)
 - source_inventory.json, runner_commit_evidence.json, summary.json (revision r2 + r2_changes), README note, sha256sums.txt
Nothing is invented: a field that is not recorded stays empty and gets a reason."""
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
F43 = Path('D:/audit43/facts43')
R = Path('D:/Source_code/myself')
COLL = Path('D:/audit43/m43_collect')
EV_LO = Path('D:/audit43/evidence43/runner_commit_evidence_lo_seed43_20261116')
TIER = {'RNN': 'F1_RECURRENT', 'LSTM': 'F1_RECURRENT', 'GRU': 'F1_RECURRENT', 'BILSTM': 'F1_RECURRENT', 'PATCHTST': 'F2_TS_TRANSFORMER', 'MANTIS_V2': 'F3_TS_FOUNDATION'}
SRC = {('CQ', 'F1'): 'CQ/L1_runs/S3_model/staging_incoming/f1_recurrent_seed43_20261110', ('LO', 'F1'): 'LO/L1_runs/S3_model/staging_incoming/f1_recurrent_seed43_20261110',
       ('CQ', 'PT'): 'CQ/L1_runs/S3_model/staging_incoming/patchtst_seed43_cells_20261112', ('LO', 'PT'): 'LO/L1_runs/S3_model/staging_incoming/patchtst_seed43_cells_20261114'}
COMMIT_F = '5ba982958c9ce50ac6be6a28ff9c812e0f17b31e'

# reference probe-fit counts from the delivered seed-42 packages (the probe is fitted on the real parent TRAIN rows and scored on the real eval prefix: the same data for every seed)
ref = []
for p in ('CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103_r2', 'CQ/resuilt/cq_patchtst_v7_v16_full_facts_20261109_r2', 'LO/resuilt/lo_patchtst_v0_v16_full_facts_20261109_r2'):
    ref.append(pd.read_csv(R / p / 'sanity_components.csv', usecols=['task', 'window_id', 'parent_pipeline', 'eval_split', 'phase_id', 'probe_fit_rows', 's_leak_probe_n_eval', 'probe_score_scope']))
ref = pd.concat(ref).drop_duplicates()
K = ['task', 'window_id', 'parent_pipeline', 'eval_split', 'phase_id']
assert not ref.duplicated(K).any(), 'reference probe counts are not unique per key'
cells = pd.read_csv(COLL / 'runner_commit_check_seed43_cells.csv')
mant_inv = json.loads((COLL / 'mantis_inventory.json').read_text())
listing = {}
for key, path in SRC.items():
    listing[key] = json.loads(subprocess.run(RC + ['lsjson', '-R', '--files-only', '--hash', f'gdrive:{path}'], capture_output=True, text=True).stdout)
ev_cq = json.loads(subprocess.run(RC + ['cat', 'gdrive:CQ/L1_runs/S3_model/staging_incoming/mantis_v2_seed43_exploratory_20261111/runner_commit_evidence_20261113/runner_commit_evidence_cq_seed43.json'], capture_output=True, text=True).stdout)
ev_lo = json.loads((EV_LO / 'runner_commit_evidence_lo_seed43.json').read_text())


def save(df, d, name):
    df.to_parquet(d / f'{name}.parquet', index=False)
    df.to_csv(d / f'{name}.csv', index=False, lineterminator='\n')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


report = []
for d in sorted(p for p in F43.rglob('summary.json') if 'cohort_audit' not in p.parts):
    d = d.parent
    s = json.loads((d / 'summary.json').read_text())
    task, model = s['task'], s['model']
    kind = 'F1' if model in ('RNN', 'LSTM', 'GRU', 'BILSTM') else ('PT' if model == 'PATCHTST' else 'MANTIS')
    mantis = kind == 'MANTIS'
    # ---- sanity_components
    san = pd.read_csv(d / 'sanity_components.csv', low_memory=False)
    san = san.drop(columns=[c for c in ('probe_fit_rows', 's_leak_probe_n_eval', 'probe_score_scope', 'model_tier', 'variant_role', 'run_purpose') if c in san.columns])
    san = san.merge(ref, on=K, how='left', validate='many_to_one')
    miss = int(san.probe_fit_rows.isna().sum())
    san['probe_fit_rows_source'] = 'REFERENCE_PROBE_FIT_SEED42_SAME_REAL_DATA'
    san['model_tier'] = TIER[model]
    san['variant_role'] = 'EXPLORATORY' if mantis else None
    san['run_purpose'] = 'EXPLORATORY_CACHE_VALIDATION' if mantis else 'PRIMARY_GRID'
    save(san, d, 'sanity_components')
    # ---- checkpoint_selection (labels on all 51 rows)
    ck = pd.read_csv(d / 'checkpoint_selection.csv', low_memory=False)
    ck = ck.drop(columns=[c for c in ('model_tier', 'variant_role', 'run_purpose') if c in ck.columns])
    ck['model_tier'] = TIER[model]
    ck['variant_role'] = 'EXPLORATORY' if mantis else None
    ck['run_purpose'] = 'EXPLORATORY_CACHE_VALIDATION' if mantis else 'PRIMARY_GRID'
    save(ck, d, 'checkpoint_selection')
    # ---- resource_per_run
    rs = pd.read_csv(d / 'resource_per_run.csv', low_memory=False)
    rs = rs.drop(columns=[c for c in ('resource_null_reason', 'runner_git_commit_basis') if c in rs.columns])
    ev = ev_cq if task == 'CQ' else ev_lo
    reason = []
    for _, r in rs.iterrows():
        parts = []
        if pd.isna(r.energy_gpu_estimated_kwh):
            parts.append(f'ENERGY_NOT_MEASURED: energy_measurement_type = {r.energy_measurement_type}, {int(r.energy_sample_count)} samples in {int(r.energy_sample_attempt_count)} attempts')
        reason.append('; '.join(parts) if parts else None)
    rs['resource_null_reason'] = reason
    if mantis:
        rs['runner_git_commit'] = ev['runner_earliest_matching_commit']
        rs['runner_git_commit_basis'] = 'CODE_TAR_FILE_BLOB_MATCH_RETROACTIVE'
    else:
        rs['runner_git_commit_basis'] = 'RUN_MANIFEST_WRITTEN_AT_RUN_TIME'
        assert (rs.runner_git_commit == COMMIT_F).all(), 'runner commit differs from the checked value'
    save(rs, d, 'resource_per_run')
    # ---- runner_commit_evidence.json and source_inventory.json
    if mantis:
        (d / 'runner_commit_evidence.json').write_text(json.dumps({**ev, 'applies_to': f'{task} MANTIS_V2 seed 43'}, indent=2) + '\n', encoding='utf-8')
        inv = [r for r in mant_inv if r['task'] == task]
        base = 'CQ/L1_runs/S3_model/staging_incoming/mantis_v2_seed43_exploratory_20261111' if task == 'CQ' else 'LO/L1_runs/S3_model/staging_incoming/mantis_v2_seed43_exploratory_20261113'
        archives = [{'drive_path': f"{base}/{r['pipeline']}/{r['file']}", 'bytes': r['bytes'], 'sha256': r['sha256'], 'drive_md5': r.get('drive_md5') or r['md5']} for r in sorted(inv, key=lambda r: r['file'])]
        scope = f'{task} Mantis seed 43 result tars'
    else:
        sub = cells[(cells.task == task) & (cells.model_name == model)]
        (d / 'runner_commit_evidence.json').write_text(json.dumps({'basis': 'RUN_MANIFEST_WRITTEN_AT_RUN_TIME', 'runner': 'tools/vastai_train_shared.py', 'commit': COMMIT_F, 'cells_checked': int(len(sub)),
                                                                  'cells_with_commit': int((sub.runner_git_commit == COMMIT_F).sum()), 'note': 'run_manifest.json of every cell carries runner_git_commit written by the runner at run time (not retroactive)',
                                                                  'applies_to': f'{task} {model} seed 43'}, indent=2) + '\n', encoding='utf-8')
        lst = listing[(task, 'F1' if kind == 'F1' else 'PT')]
        base = SRC[(task, 'F1' if kind == 'F1' else 'PT')]
        pick = [e for e in lst if e['Name'].endswith(('.tar', '.tar.gz')) and ((kind == 'PT') or e['Path'].startswith(model + '/'))]
        archives = [{'drive_path': f"{base}/{e['Path']}", 'bytes': e['Size'], 'drive_md5': (e.get('Hashes') or {}).get('md5')} for e in sorted(pick, key=lambda e: e['Path'])]
        scope = f'{task} {model} seed 43 result archives'
    (d / 'source_inventory.json').write_text(json.dumps({'scope': scope, 'n_archives': len(archives), 'archives': archives,
                                                         'note': 'sha256 is listed where it was computed while streaming (Mantis); the others carry the Drive MD5'}, indent=2) + '\n', encoding='utf-8')
    # ---- summary and README
    s['revision'] = 'r2'
    s['run_purpose'] = 'EXPLORATORY' if mantis else 'PRIMARY_GRID'
    s['r2_changes'] = ['sanity_components: probe_fit_rows, s_leak_probe_n_eval, probe_score_scope filled from the reference probe fit of the delivered seed-42 packages (same real data; column probe_fit_rows_source); model_tier, variant_role, run_purpose',
                       'checkpoint_selection: model_tier, variant_role, run_purpose on all 51 rows',
                       'resource_per_run: resource_null_reason, runner_git_commit_basis' + ('; runner_git_commit mapped retroactively (blob match)' if mantis else ''),
                       'added runner_commit_evidence.json and source_inventory.json']
    s['probe_columns_missing_rows'] = miss
    (d / 'summary.json').write_text(json.dumps(s, indent=2) + '\n', encoding='utf-8')
    rd = d / 'README.md'
    rd.write_text(rd.read_text(encoding='utf-8') + '\n## r2\n\nThe package follows the `_r2` format: ' + '; '.join(s['r2_changes']) + '. `s_leak` is copied from the reference table (audit mode COPY_REFERENCE, no probe refit); `probe_fit_rows` and `s_leak_probe_n_eval` are therefore taken from the reference fit and marked in `probe_fit_rows_source`.\n',
                  encoding='utf-8', newline='\n')
    files = sorted(p for p in d.rglob('*') if p.is_file() and p.name != 'sha256sums.txt')
    (d / 'sha256sums.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(d).as_posix()}\n' for p in files), encoding='utf-8', newline='\n')
    report.append((str(d.relative_to(F43)), miss, len(archives)))
    print(d.relative_to(F43).as_posix(), 'probe rows missing:', miss, 'archives:', len(archives), flush=True)
print('FINALIZE_DONE')
