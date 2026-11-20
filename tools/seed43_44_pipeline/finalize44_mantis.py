"""Seed-44 F1 facts packages -> `_r2` format (Mantis), then upload to Drive with md5 check and delete the local copy.
usage: finalize44_f1.py TASK        (packages in $TEMPO_A44_ROOT/facts44/<TASK>_f1_recurrent_v0_v16_seed44/<FAM>)"""
from tempo_paths import A44, REPO
import hashlib, json, subprocess, sys, shutil
from pathlib import Path
import pandas as pd
TASK = sys.argv[1]
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
ROOT = Path(f'{A44}/facts44/{TASK}_mantis_v2_v0_v16_seed44'); R = Path(f'{REPO}')
SRCDIR = {'CQ': 'CQ/L1_runs/S3_model/staging_incoming/mantis_v2_seed44_exploratory_20261116', 'LO': 'LO/L1_runs/S3_model/staging_incoming/mantis_v2_seed44_exploratory_20261118'}[TASK]
EVD = Path(f'{A44}/evidence44/runner_commit_evidence_{TASK.lower()}_seed44_20261119'); EV = json.loads((EVD / f'runner_commit_evidence_{TASK.lower()}_seed44.json').read_text())
INV = [r for r in json.loads(Path(f'{A44}/mantis44_inventory.json').read_text()) if r['task'] == TASK]; assert len(INV) == 51, len(INV)
DEST = f'gdrive:{TASK}/L2_facts/fact_exports/{TASK.lower()}_mantis_v2_v0_v16_full_facts_seed44_20261119'
TIER = 'F3_TS_FOUNDATION'
ref = []
for p in ('CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103_r2', 'CQ/resuilt/cq_patchtst_v7_v16_full_facts_20261109_r2', 'LO/resuilt/lo_patchtst_v0_v16_full_facts_20261109_r2'):
    ref.append(pd.read_csv(R / p / 'sanity_components.csv', usecols=['task', 'window_id', 'parent_pipeline', 'eval_split', 'phase_id', 'probe_fit_rows', 's_leak_probe_n_eval', 'probe_score_scope']))
ref = pd.concat(ref).drop_duplicates(); K = ['task', 'window_id', 'parent_pipeline', 'eval_split', 'phase_id']
assert not ref.duplicated(K).any()
def save(df, d, name):
    df.to_parquet(d / f'{name}.parquet', index=False); df.to_csv(d / f'{name}.csv', index=False, lineterminator='\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
for d in [ROOT]:
    FAM = 'MANTIS_V2'; s = json.loads((d / 'summary.json').read_text())
    if s.get('revision') == 'r2': print(FAM, 'already r2'); continue
    san = pd.read_csv(d / 'sanity_components.csv', low_memory=False)
    san = san.drop(columns=[c for c in ('probe_fit_rows', 's_leak_probe_n_eval', 'probe_score_scope', 'model_tier', 'variant_role', 'run_purpose') if c in san.columns])
    san = san.merge(ref, on=K, how='left', validate='many_to_one'); miss = int(san.probe_fit_rows.isna().sum())
    san['probe_fit_rows_source'] = 'REFERENCE_PROBE_FIT_SEED42_SAME_REAL_DATA'; san['model_tier'] = TIER; san['variant_role'] = 'EXPLORATORY'; san['run_purpose'] = 'EXPLORATORY_CACHE_VALIDATION'
    save(san, d, 'sanity_components')
    ck = pd.read_csv(d / 'checkpoint_selection.csv', low_memory=False)
    ck = ck.drop(columns=[c for c in ('model_tier', 'variant_role', 'run_purpose') if c in ck.columns]); ck['model_tier'] = TIER; ck['variant_role'] = 'EXPLORATORY'; ck['run_purpose'] = 'EXPLORATORY_CACHE_VALIDATION'
    save(ck, d, 'checkpoint_selection')
    rs = pd.read_csv(d / 'resource_per_run.csv', low_memory=False)
    rs = rs.drop(columns=[c for c in ('resource_null_reason', 'runner_git_commit_basis') if c in rs.columns])
    rs['resource_null_reason'] = [(f'ENERGY_NOT_MEASURED: energy_measurement_type = {r.energy_measurement_type}, {int(r.energy_sample_count)} samples in {int(r.energy_sample_attempt_count)} attempts' if pd.isna(r.energy_gpu_estimated_kwh) else None) for _, r in rs.iterrows()]
    rs['runner_git_commit'] = EV['runner_earliest_matching_commit']; rs['runner_git_commit_basis'] = 'CODE_TAR_FILE_BLOB_MATCH_RETROACTIVE'; save(rs, d, 'resource_per_run')
    commits = sorted(rs.runner_git_commit.dropna().unique())
    (d / 'runner_commit_evidence.json').write_text(json.dumps({**EV, 'applies_to': f'{TASK} MANTIS_V2 seed 44'}, indent=2) + '\n', encoding='utf-8')
    arch = [{'drive_path': r['drive_path'], 'bytes': r['bytes'], 'sha256': r['sha256'], 'drive_md5': r.get('drive_md5') or r['md5']} for r in sorted(INV, key=lambda r: r['drive_path'])]
    (d / 'source_inventory.json').write_text(json.dumps({'scope': f'{TASK} Mantis seed 44 result tars', 'n_archives': len(arch), 'archives': arch, 'note': 'sha256 is listed where it was computed while streaming (Mantis)'}, indent=2) + '\n', encoding='utf-8')
    s['revision'] = 'r2'; s['run_purpose'] = 'EXPLORATORY'
    s['r2_changes'] = ['sanity_components: probe_fit_rows, s_leak_probe_n_eval, probe_score_scope from the reference probe fit (same real data; column probe_fit_rows_source); model_tier, variant_role, run_purpose',
                       'checkpoint_selection: model_tier, variant_role, run_purpose on all 51 rows', 'resource_per_run: resource_null_reason, runner_git_commit_basis; runner_git_commit mapped retroactively (blob match)', 'added runner_commit_evidence.json and source_inventory.json']
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
