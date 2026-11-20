"""Seed-44 F1 facts packages -> `_r2` format (port of finalize_facts43.py, F1 only), then upload to Drive with md5 check and delete the local copy.
usage: finalize44_f1.py TASK        (packages in $TEMPO_A44_ROOT/facts44/<TASK>_f1_recurrent_v0_v16_seed44/<FAM>)"""
from tempo_paths import A44, REPO
import hashlib, json, subprocess, sys, shutil
from pathlib import Path
import pandas as pd
TASK = sys.argv[1]
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
ROOT = Path(f'{A44}/facts44/{TASK}_patchtst_v0_v16_seed44'); R = Path(f'{REPO}')
SRCDIR = {'CQ': 'CQ/L1_runs/S3_model/staging_incoming/patchtst_seed44_cells_20261116', 'LO': 'LO/L1_runs/S3_model/staging_incoming/patchtst_seed44_20261117'}[TASK]
DEST = f'gdrive:{TASK}/L2_facts/fact_exports/{TASK.lower()}_patchtst_v0_v16_full_facts_seed44_20261119'
TIER = 'F2_TS_TRANSFORMER'
ref = []
for p in ('CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103_r2', 'CQ/resuilt/cq_patchtst_v7_v16_full_facts_20261109_r2', 'LO/resuilt/lo_patchtst_v0_v16_full_facts_20261109_r2'):
    ref.append(pd.read_csv(R / p / 'sanity_components.csv', usecols=['task', 'window_id', 'parent_pipeline', 'eval_split', 'phase_id', 'probe_fit_rows', 's_leak_probe_n_eval', 'probe_score_scope']))
ref = pd.concat(ref).drop_duplicates(); K = ['task', 'window_id', 'parent_pipeline', 'eval_split', 'phase_id']
assert not ref.duplicated(K).any()
def save(df, d, name):
    df.to_parquet(d / f'{name}.parquet', index=False); df.to_csv(d / f'{name}.csv', index=False, lineterminator='\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
for d in [ROOT]:
    FAM = 'PATCHTST'; s = json.loads((d / 'summary.json').read_text())
    if s.get('revision') == 'r2': print(FAM, 'already r2'); continue
    san = pd.read_csv(d / 'sanity_components.csv', low_memory=False)
    san = san.drop(columns=[c for c in ('probe_fit_rows', 's_leak_probe_n_eval', 'probe_score_scope', 'model_tier', 'variant_role', 'run_purpose') if c in san.columns])
    san = san.merge(ref, on=K, how='left', validate='many_to_one'); miss = int(san.probe_fit_rows.isna().sum())
    san['probe_fit_rows_source'] = 'REFERENCE_PROBE_FIT_SEED42_SAME_REAL_DATA'; san['model_tier'] = TIER; san['variant_role'] = None; san['run_purpose'] = 'PRIMARY_GRID'
    save(san, d, 'sanity_components')
    ck = pd.read_csv(d / 'checkpoint_selection.csv', low_memory=False)
    ck = ck.drop(columns=[c for c in ('model_tier', 'variant_role', 'run_purpose') if c in ck.columns]); ck['model_tier'] = TIER; ck['variant_role'] = None; ck['run_purpose'] = 'PRIMARY_GRID'
    save(ck, d, 'checkpoint_selection')
    rs = pd.read_csv(d / 'resource_per_run.csv', low_memory=False)
    rs = rs.drop(columns=[c for c in ('resource_null_reason', 'runner_git_commit_basis') if c in rs.columns])
    rs['resource_null_reason'] = [(f'ENERGY_NOT_MEASURED: energy_measurement_type = {r.energy_measurement_type}, {int(r.energy_sample_count)} samples in {int(r.energy_sample_attempt_count)} attempts' if pd.isna(r.energy_gpu_estimated_kwh) else None) for _, r in rs.iterrows()]
    rs['runner_git_commit_basis'] = 'RUN_MANIFEST_WRITTEN_AT_RUN_TIME'; save(rs, d, 'resource_per_run')
    commits = sorted(rs.runner_git_commit.dropna().unique())
    (d / 'runner_commit_evidence.json').write_text(json.dumps({'basis': 'RUN_MANIFEST_WRITTEN_AT_RUN_TIME', 'runner': 'tools/vastai_train_shared.py', 'commits': commits, 'cells': int(len(rs)), 'cells_with_commit': int(rs.runner_git_commit.notna().sum()),
        'note': 'run_manifest.json of every cell carries runner_git_commit written by the runner at run time (not retroactive)', 'applies_to': f'{TASK} {FAM} seed 44'}, indent=2) + '\n', encoding='utf-8')
    lst = json.loads(subprocess.run(RC + ['lsjson', '--files-only', '--hash', f'gdrive:{SRCDIR}'], capture_output=True, text=True).stdout)
    arch = [{'drive_path': f"{SRCDIR}/{e['Path']}", 'bytes': e['Size'], 'drive_md5': (e.get('Hashes') or {}).get('md5')} for e in sorted(lst, key=lambda e: e['Path']) if e['Path'].endswith('.tar')]
    (d / 'source_inventory.json').write_text(json.dumps({'scope': f'{TASK} {FAM} seed 44 result archives', 'n_archives': len(arch), 'archives': arch, 'note': 'the archives carry the Drive MD5'}, indent=2) + '\n', encoding='utf-8')
    s['revision'] = 'r2'; s['run_purpose'] = 'PRIMARY_GRID'
    s['r2_changes'] = ['sanity_components: probe_fit_rows, s_leak_probe_n_eval, probe_score_scope from the reference probe fit (same real data; column probe_fit_rows_source); model_tier, variant_role, run_purpose',
                       'checkpoint_selection: model_tier, variant_role, run_purpose on every row', 'resource_per_run: resource_null_reason, runner_git_commit_basis', 'added runner_commit_evidence.json and source_inventory.json']
    s['probe_columns_missing_rows'] = miss; (d / 'summary.json').write_text(json.dumps(s, indent=2) + '\n', encoding='utf-8')
    rd = d / 'README.md'
    rd.write_text(rd.read_text(encoding='utf-8') + '\n## r2\n\nThe package follows the `_r2` format: ' + '; '.join(s['r2_changes']) + '. `s_leak` is copied from the reference table (audit mode COPY_REFERENCE, no probe refit); `probe_fit_rows` and `s_leak_probe_n_eval` come from the reference fit and are marked in `probe_fit_rows_source`.\n', encoding='utf-8', newline='\n')
    files = sorted(p for p in d.rglob('*') if p.is_file() and p.name != 'sha256sums.txt')
    (d / 'sha256sums.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(d).as_posix()}\n' for p in files), encoding='utf-8', newline='\n')
    print(FAM, 'r2 done; commits', commits, 'probe rows missing', miss, flush=True)
# upload + verify + delete local
subprocess.run(RC + ['copy', str(ROOT), DEST, '--transfers', '4', '-q'], check=True)
chk = subprocess.run(RC + ['check', str(ROOT), DEST, '--one-way', '--download'] if False else RC + ['check', str(ROOT), DEST, '--one-way'], capture_output=True, text=True)
print('rclone check rc', chk.returncode, (chk.stderr or chk.stdout)[-300:])
if chk.returncode == 0:
    shutil.rmtree(ROOT); print('uploaded and local copy removed ->', DEST)
else:
    print('NOT removing local: check failed')
