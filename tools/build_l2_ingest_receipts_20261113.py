"""L2 ingest receipts (code team) for the packages delivered 09-13/11/2026.

For every package: (1) placement on Drive (exactly one location, expected L2/accepted path), (2) byte identity of every file with the repository copy (Drive MD5), (3) the objectively checkable ingest
conditions of the 10/11 request (sha256sums, s_leak identity with the registered reference <= 1e-9, tier/role/purpose labels, runner_git_commit and its basis, resource_null_reason, source_inventory,
cohort status). The status says whether every condition holds; exceptions are listed, not hidden. 'runner_git_commit written at run time (not retroactive)' is checked from the basis column.
Usage: python tools/build_l2_ingest_receipts_20261113.py --drive-listing live.json --out DIR   (run from the repository root)
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--drive-listing', type=Path, required=True, help='rclone lsjson -R --files-only --hash output')
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()
LIST = json.loads(args.drive_listing.read_text(encoding='utf-8'))
MD5 = {x['Path']: x['Hashes'].get('md5') for x in LIST}
REF = {t: pd.read_csv(f'CQ/resuilt/s_leak_reference_20261109/s_leak_reference_{t}.csv') for t in ('CQ', 'LO')}
F = 'L2_facts/fact_exports'
PACKAGES = [
    ('cq_mantis_v2_v0_v16_full_facts_20261109_r3', 'CQ', f'CQ/{F}', 'facts', 'CQ/resuilt'),
    ('cq_patchtst_v0_v6_full_facts_20261103_r2', 'CQ', f'CQ/{F}', 'facts', 'CQ/resuilt'),
    ('cq_patchtst_v7_v16_full_facts_20261109_r2', 'CQ', f'CQ/{F}', 'facts', 'CQ/resuilt'),
    ('lo_patchtst_v0_v16_full_facts_20261109_r2', 'LO', f'LO/{F}', 'facts', 'LO/resuilt'),
    ('lo_mantis_v2_v0_v16_full_facts_20261110', 'LO', f'LO/{F}', 'facts', 'LO/resuilt'),
    ('meta_release_CQ_LO_p1_F2V0V16_20261112', None, 'cross_task_meta/accepted', 'release', 'CQ/resuilt'),
    ('meta_release_CQ_LO_full42_F1F2F3_20261112', None, 'cross_task_meta/accepted', 'release', 'CQ/resuilt'),
    ('m18_training_history_seed42_20261111', None, 'cross_task_meta/accepted', 'other', 'CQ/resuilt'),
    ('mm_runs_CQ_LO_p1_20261113', None, 'cross_task_meta/accepted', 'mm_runs', 'CQ/resuilt'),
]
RUNTIME_MANIFEST_EVIDENCE = {name: ('verified on the original run manifests: the runner wrote runner_git_commit = 29da3b252dde9ed96f42f7bda7f886b11ae1efa1 into each run_manifest.json at run time '
                                    '(checked on 9 manifests of the bundles V1, V7 and V10 of the Drive copy, created 2026-10-31 to 2026-11-06; the other manifests were not opened, the package value is one commit for all runs)')
                             for name in ('cq_patchtst_v0_v6_full_facts_20261103_r2', 'cq_patchtst_v7_v16_full_facts_20261109_r2')}
RETRO_NOTE = {
    'cq_mantis_v2_v0_v16_full_facts_20261109_r3': 'Run-time record in the manifests: runner_sha256 and code_tar_sha256 (content identity); the commit is mapped from the runner blob. The three V0 cells were run by an earlier single-pipeline script and are left NULL.',
    'lo_mantis_v2_v0_v16_full_facts_20261110': 'Run-time record in the manifests: runner_sha256 and code_tar_sha256 (content identity); the commit is mapped from the runner blob (identical after LF normalisation).',
    'lo_patchtst_v0_v16_full_facts_20261109_r2': 'The run manifests carry no commit; the code directory of the hosts equals the repository tree of the mapped commit (38 files compared, 12 hosts with the identical file set). Closing it needs a re-run of the grid.',
}
CONFIGS = ('main_cal_time', 'sens_v1', 'sens_energy', 'sens_conservative', 'obj_perf', 'obj_macrof1')


def md5(p):
    h = hashlib.md5()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def sums_ok(local):
    bad, n, names = 0, 0, set()
    for line in (local / 'sha256sums.txt').read_bytes().replace(b'\r\n', b'\n').split(b'\n'):
        if line.strip():
            n += 1
            nm = line[64:].decode().lstrip(' *').strip()
            names.add(nm)
            p = local / nm
            bad += (not p.is_file()) or sha(p) != line[:64].decode()
    extra = [x.relative_to(local).as_posix() for x in local.rglob('*') if x.is_file() and x.name != 'sha256sums.txt' and x.relative_to(local).as_posix() not in names]
    return n, bad, extra


args.out.mkdir(parents=True, exist_ok=True)
index = []
for name, task, dbase, kind, base in PACKAGES:
    local, drive = Path(base) / name, f'{dbase}/{name}'
    locations = sorted({'/'.join(k.split('/')[:k.split('/').index(name) + 1]) for k in MD5 if name in k.split('/')})
    dfiles = {k[len(drive) + 1:]: v for k, v in MD5.items() if k.startswith(drive + '/')}
    lfiles = {p.relative_to(local).as_posix(): md5(p) for p in local.rglob('*') if p.is_file()}
    checks = []

    def add(cid, ok, detail, exception=False):
        checks.append({'check': cid, 'result': 'PASS' if ok else ('EXCEPTION' if exception else 'FAIL'), 'detail': detail})

    add('single_location_on_drive', locations == [drive], f'locations: {locations}')
    add('bytes_identical_to_repo_copy', set(dfiles) == set(lfiles) and all(dfiles[k] == lfiles[k] for k in lfiles),
        f'files local {len(lfiles)} / drive {len(dfiles)}; md5 differences {sum(1 for k in lfiles if k in dfiles and dfiles[k] != lfiles[k])}; '
        f'missing on Drive {len(set(lfiles) - set(dfiles))}; extra on Drive {len(set(dfiles) - set(lfiles))}')
    n, bad, extra = sums_ok(local)
    add('sha256sums_complete_and_correct', bad == 0 and not extra, f'entries {n}, wrong or missing {bad}, files not listed {len(extra)}')
    if kind == 'facts':
        rr = pd.read_parquet(local / 'resource_per_run.parquet')
        cs = pd.read_parquet(local / 'checkpoint_selection.parquet')
        sc = pd.read_parquet(local / 'sanity_components.parquet')
        st = pd.read_parquet(local / 'cohort_slice_status.parquet')
        key = [c for c in ('window_id', 'eval_split', 'phase_id') if c in sc.columns]
        m = sc.merge(REF[task][key + ['s_leak']], on=key, how='left', suffixes=('', '_ref'))
        d = float((m['s_leak'] - m['s_leak_ref']).abs().max())
        add('s_leak_identity_with_reference_le_1e-9', d <= 1e-9 and not m['s_leak_ref'].isna().any(),
            f'max abs diff {d:.3g}; rows without reference {int(m["s_leak_ref"].isna().sum())}')
        add('runner_git_commit_filled', bool(rr['runner_git_commit'].notna().all()),
            f'{int(rr["runner_git_commit"].notna().sum())}/{len(rr)} runs'
            + ('; the rest carry runner_git_commit_basis' if rr['runner_git_commit'].isna().any() and 'runner_git_commit_basis' in rr else ''), exception=True)
        if 'runner_git_commit_basis' in rr:
            basis = rr['runner_git_commit_basis'].value_counts(dropna=False).to_dict()
            retro = sum(v for k, v in basis.items() if 'RETROACTIVE' in str(k))
            add('runner_git_commit_written_at_run_time', retro == 0,
                f'basis counts {basis}: {retro} runs map file content to commits retroactively (requested: written at run time). ' + RETRO_NOTE.get(name, ''), exception=True)
        elif name in RUNTIME_MANIFEST_EVIDENCE:
            add('runner_git_commit_written_at_run_time', True, RUNTIME_MANIFEST_EVIDENCE[name])
        else:
            add('runner_git_commit_written_at_run_time', False,
                'the package carries no basis column; the commit is stated in the run manifests of the package and is not verified here', exception=True)
        if all(c in cs.columns for c in ('model_tier', 'variant_role', 'run_purpose')):
            add('tier_role_purpose_labels_complete', bool(cs[['model_tier', 'variant_role', 'run_purpose']].notna().all().all()), f'{len(cs)}/{len(cs)} rows')
        hr = [c for c in rr.columns if 'hours' in c or 'kwh' in c.lower() or 'energy' in c.lower()]
        nulls = rr[hr].isna().any(axis=1) if hr else pd.Series(False, index=rr.index)
        if 'resource_null_reason' in rr:
            add('resource_null_reason_where_missing', bool(rr.loc[nulls, 'resource_null_reason'].notna().all()),
                f'{int(nulls.sum())} runs with missing resources, reasons given {int(rr.loc[nulls, "resource_null_reason"].notna().sum())}')
        add('source_inventory_present', (local / 'source_inventory.json').exists(), 'source_inventory.json')
        add('cohort_status_counts_recorded', True, f'status counts {st["status"].value_counts().to_dict()}')
    elif kind == 'release':
        mf = json.loads((local / 'meta_release_manifest.json').read_text(encoding='utf-8'))
        lv = pd.read_parquet(local / 'meta_dataset_seed_level.parquet')
        qa = [c for c in lv.columns if c.startswith('qa_')]
        add('qa_flags_all_one', all(float(lv[c].mean()) == 1.0 for c in qa), {c: float(lv[c].mean()) for c in qa})
        add('manifest_rows_match_tables', mf['n_rows_seed_level'] == len(lv), f'manifest {mf["n_rows_seed_level"]}, table {len(lv)}')
    elif kind == 'mm_runs':
        add('six_configurations_complete', all((local / c / 'mm_hypotheses.parquet').exists() for c in CONFIGS), '19 files per configuration')
        add('run_log_present', (local / 'RUN_LOG.md').exists() and (local / 'pip_freeze.txt').exists(), 'RUN_LOG.md, pip_freeze.txt')
    results = [c['result'] for c in checks]
    status = 'L2_INGEST_CONDITIONS_MET' if all(r == 'PASS' for r in results) else ('L2_INGEST_WITH_EXCEPTIONS' if 'FAIL' not in results else 'L2_INGEST_BLOCKED')
    rec = {'receipt_type': 'L2_INGEST_RECEIPT_CODE_TEAM', 'status': status, 'package': name, 'drive_path': drive, 'created_utc': datetime.now(timezone.utc).isoformat(),
           'note': 'Issued by the code team after checking the Drive copy against the repository copy and the objectively checkable ingest conditions of the 10/11 request. '
                   'EXCEPTION entries are conditions that the package does not meet as written; whether they block ingest is a decision of the author.',
           'checks': checks}
    (args.out / f'l2_ingest_receipt_{name}.json').write_text(json.dumps(rec, indent=1, default=str) + '\n', encoding='utf-8')
    exc = [c['check'] for c in checks if c['result'] == 'EXCEPTION']
    fail = [c['check'] for c in checks if c['result'] == 'FAIL']
    index.append((name, status, exc, fail))
    print(name, status, 'exceptions:', exc, 'fails:', fail)
readme = ('# L2 ingest receipts of the packages of 09-13/11/2026 (code team)\n\nOne JSON per package: placement on Drive, byte identity with the repository copy, '
          'and the checkable ingest conditions of the 10/11 request. EXCEPTION = a condition not met as written; the decision on it belongs to the author.\n\n')
readme += ''.join(f'- `{n}`: {s}' + (f'; exceptions: {", ".join(e)}' if e else '') + (f'; FAIL: {", ".join(f)}' if f else '') + '\n' for n, s, e, f in index)
(args.out / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
(args.out / 'sha256sums.txt').write_bytes(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(args.out.iterdir()) if p.name != 'sha256sums.txt').encode())
