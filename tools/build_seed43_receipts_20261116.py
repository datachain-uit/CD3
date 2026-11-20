"""Delivery receipts (byte level) and L2 ingest receipts (code team) for the seed-43 deliverables uploaded on 2026-11-16: the six facts packages (12 sub-packages), M-18 seed 43,
the Mantis LO runner-commit evidence and the runner-commit check.  Same conditions as tools/build_l2_ingest_receipts_20261113.py and tools/build_delivery_receipts_20261112.py.
The receipts are issued by the code team; they are NOT an independent verification by the writing side (the status says so).
Usage: python tools/build_seed43_receipts_20261116.py --out DIR   (run from the repository root; needs rclone and $TEMPO_A43_ROOT)"""
from tempo_paths import A43
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--local-root', type=Path, default=Path(f'{A43}'))
args = ap.parse_args()
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
L = args.local_root
STAMP = '20261116'
REF = {t: pd.read_csv(f'CQ/resuilt/s_leak_reference_20261109/s_leak_reference_{t}.csv') for t in ('CQ', 'LO')}
PKGS = []   # (name, task, drive base, local dir, kind, family)
for t in ('CQ', 'LO'):
    base = f'{t}/L2_facts/fact_exports'      # official branch (convention of the delivered seed-42 packages); staging_incoming keeps an identical backup
    tl = t.lower()
    PKGS.append((f'{tl}_mantis_v2_v0_v16_full_facts_seed43_{STAMP}', t, base, L / f'facts43/{t}_mantis_v2_v0_v16_seed43', 'facts', 'MANTIS_V2'))
    PKGS.append((f'{tl}_patchtst_v0_v16_full_facts_seed43_{STAMP}', t, base, L / f'facts43/{t}_patchtst_v0_v16_seed43', 'facts', 'PATCHTST'))
    for fam in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
        PKGS.append((f'{tl}_f1_recurrent_v0_v16_full_facts_seed43_{STAMP}/{fam}', t, base, L / f'facts43/{t}_f1_recurrent_v0_v16_seed43/{fam}', 'facts', fam))
PKGS.append((f'm18_training_history_seed43_{STAMP}', None, 'cross_task_meta/work_in_progress', L / 'm18_43/m18_training_history_seed43_20261116', 'm18', None))
PKGS.append((f'runner_commit_check_seed43_{STAMP}', None, 'cross_task_meta/work_in_progress', L / 'upload43/runner_commit_check_seed43_20261116', 'commit_check', None))
PKGS.append((f'runner_commit_evidence_{STAMP}', 'LO', 'LO/L1_runs/S3_model/staging_incoming/mantis_v2_seed43_exploratory_20261113', L / 'evidence43/runner_commit_evidence_lo_seed43_20261116', 'evidence', None))
Q32 = ('handled under decision Q-32 (a) of 2026-11-13: the author accepted basis *_RETROACTIVE with its label for the Mantis CQ r3, Mantis LO and PatchTST LO r2 (seed 42) packages, and item 7 of the 13/11 request '
       'says the Mantis seed-43 cells run from the code tar are handled together with Q-32. The decision text names the seed-42 packages, so the acceptance of these seed-43 packages by the reviewer is still PENDING; '
       'the Mantis manifests carry runner_sha256 and code_tar_sha256 written at run time')


def digest(p, algo):
    h = hashlib.new(algo)
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def listing(top):
    out = subprocess.run(RC + ['lsjson', '-R', '--files-only', '--hash', f'gdrive:{top}'], capture_output=True, text=True).stdout
    return {f"{top}/{e['Path']}": (e.get('Hashes') or {}).get('md5') for e in json.loads(out)}


MD5 = {}
for top in ('CQ/L2_facts/fact_exports', 'LO/L2_facts/fact_exports', 'CQ/L2_facts/staging_incoming', 'LO/L2_facts/staging_incoming', 'cross_task_meta/work_in_progress', 'LO/L1_runs/S3_model/staging_incoming/mantis_v2_seed43_exploratory_20261113'):
    MD5.update(listing(top))
args.out.mkdir(parents=True, exist_ok=True)
deliv, ingest = args.out / 'delivery', args.out / 'l2_ingest'
deliv.mkdir(exist_ok=True)
ingest.mkdir(exist_ok=True)
idx_d, idx_i = [], []
for name, task, dbase, local, kind, fam in PKGS:
    drive = f'{dbase}/{name}'
    dfiles = {k[len(drive) + 1:]: v for k, v in MD5.items() if k.startswith(drive + '/')}
    lfiles = {p.relative_to(local).as_posix(): p for p in local.rglob('*') if p.is_file()}
    loc = sorted({'/'.join(k.split('/')[:-1]) for k in MD5 if k.startswith(drive + '/')} and {drive})
    same_name = sorted({k.split('/' + name.split('/')[0] + '/')[0] + '/' + name.split('/')[0] for k in MD5 if ('/' + name.split('/')[0] + '/') in k})
    sums = {}
    for line in (local / 'sha256sums.txt').read_bytes().replace(b'\r\n', b'\n').split(b'\n'):
        if line.strip():
            sums[line[64:].decode().lstrip(' *').strip()] = line[:64].decode()
    files, problems = [], []
    for rel, p in sorted(lfiles.items()):
        m5, s2 = digest(p, 'md5'), digest(p, 'sha256')
        e = {'path': rel, 'bytes': p.stat().st_size, 'sha256': s2, 'md5': m5, 'drive_md5': dfiles.get(rel), 'drive_md5_matches': dfiles.get(rel) == m5}
        if rel != 'sha256sums.txt':
            e['sha256_matches_sha256sums'] = sums.get(rel) == s2
            if not e['sha256_matches_sha256sums']:
                problems.append(f'sha256 differs from sha256sums.txt: {rel}')
        if not e['drive_md5_matches']:
            problems.append(f'Drive MD5 differs or file missing on Drive: {rel}')
        files.append(e)
    extra_drive = sorted(set(dfiles) - set(lfiles))
    if extra_drive:
        problems.append(f'files on Drive that are not in the local copy: {extra_drive[:5]}')
    rec_d = {'receipt_type': 'DELIVERY_RECEIPT_CODE_TEAM', 'status': 'DELIVERED_AND_BYTE_VERIFIED_NOT_L2_INGESTED' if not problems else 'PROBLEMS',
             'note': 'Written by the code team on 2026-11-16. It verifies the Drive copy byte for byte; it is not an official L2 ingest receipt and not an independent verification.',
             'package': name, 'drive_path': drive, 'created_utc': datetime.now(timezone.utc).isoformat(), 'n_files': len(files), 'total_bytes': sum(f['bytes'] for f in files), 'problems': problems, 'files': files}
    safe = name.replace('/', '__')
    (deliv / f'delivery_receipt_{safe}.json').write_text(json.dumps(rec_d, indent=1) + '\n', encoding='utf-8')
    idx_d.append((name, len(files), len(problems), rec_d['status']))
    # ---- ingest conditions
    checks = []

    def add(cid, ok, detail, q32=False):
        if not ok and q32:
            checks.append({'check': cid, 'result': 'ACCEPTED_UNDER_Q32_REVIEW_PENDING_FOR_SEED43', 'detail': detail + ' | ' + Q32})
        else:
            checks.append({'check': cid, 'result': 'PASS' if ok else 'FAIL', 'detail': detail})

    if kind == 'facts':
        stg = f'{task}/L2_facts/staging_incoming/{name}'
        sfiles = {k[len(stg) + 1:]: v for k, v in MD5.items() if k.startswith(stg + '/')}
        add('official_location_fact_exports', bool(dfiles) and drive.startswith(f'{task}/L2_facts/fact_exports/'), f'{len(dfiles)} files under {drive}')
        add('staging_backup_identical_not_to_be_read_together', set(sfiles) == set(dfiles) and all(sfiles[k] == dfiles[k] for k in dfiles),
            f'staging copy {len(sfiles)} files, official copy {len(dfiles)} files, md5 differences {sum(1 for k in dfiles if k in sfiles and sfiles[k] != dfiles[k])}; the staging copy is a backup: assemble from the official path only')
    else:
        add('single_location_on_drive', len({k.rsplit('/' + name.split('/')[-1], 1)[0] for k in MD5 if k.startswith(drive + '/')}) <= 1 and bool(dfiles), f'{len(dfiles)} files under {drive}')
    add('bytes_identical_to_local_copy', set(dfiles) == set(lfiles) and all(dfiles[k] == digest(lfiles[k], 'md5') for k in lfiles), f'files local {len(lfiles)} / drive {len(dfiles)}; problems {len(problems)}')
    bad = sum(1 for rel, h in sums.items() if rel not in lfiles or digest(lfiles[rel], 'sha256') != h)
    extra = [r for r in lfiles if r != 'sha256sums.txt' and r not in sums]
    add('sha256sums_complete_and_correct', bad == 0 and not extra, f'entries {len(sums)}, wrong or missing {bad}, files not listed {len(extra)}')
    if kind == 'facts':
        rr = pd.read_csv(local / 'resource_per_run.csv', low_memory=False)
        cs = pd.read_csv(local / 'checkpoint_selection.csv', low_memory=False)
        sc = pd.read_csv(local / 'sanity_components.csv', low_memory=False)
        st = pd.read_csv(local / 'cohort_slice_status.csv', low_memory=False)
        key = ['window_id', 'eval_split', 'phase_id']
        m = sc.merge(REF[task][key + ['s_leak']], on=key, how='left', suffixes=('', '_ref'))
        d = float((m['s_leak'] - m['s_leak_ref']).abs().max())
        add('s_leak_identity_with_reference_le_1e-9', d <= 1e-9 and not m['s_leak_ref'].isna().any(), f'max abs diff {d:.3g}; rows without reference {int(m["s_leak_ref"].isna().sum())}; {len(sc)} sanity rows')
        add('runner_git_commit_filled', bool(rr['runner_git_commit'].notna().all()), f'{int(rr["runner_git_commit"].notna().sum())}/{len(rr)} runs')
        retro = int(rr['runner_git_commit_basis'].astype(str).str.contains('RETROACTIVE').sum())
        add('runner_git_commit_written_at_run_time', retro == 0, f'basis counts {rr["runner_git_commit_basis"].value_counts().to_dict()}: {retro} runs map file content to a commit retroactively', q32=(fam == 'MANTIS_V2'))
        lab = ['model_tier', 'run_purpose'] + (['variant_role'] if fam == 'MANTIS_V2' else [])
        add('tier_role_purpose_labels_complete', bool(cs[lab].notna().all().all()) and bool(sc[lab].notna().all().all()),
            f'{len(cs)}/{len(cs)} checkpoint rows carry {lab}' + ('' if fam == 'MANTIS_V2' else '; variant_role is not recorded for F1/F2 runs (empty by design, as in the delivered F2 packages)'))
        nulls = rr['energy_gpu_estimated_kwh'].isna()
        add('resource_null_reason_where_missing', bool(rr.loc[nulls, 'resource_null_reason'].notna().all()), f'{int(nulls.sum())} runs with missing energy, reasons given {int(rr.loc[nulls, "resource_null_reason"].notna().sum())}')
        add('source_inventory_present', (local / 'source_inventory.json').exists() and (local / 'runner_commit_evidence.json').exists(), 'source_inventory.json and runner_commit_evidence.json')
        add('cohort_status_complete', len(st) == 1632, f'{len(st)} rows; status counts {st["status"].value_counts().to_dict()}')
        add('cell_coverage_51', sc[['window_id', 'pipeline_id']].drop_duplicates().shape[0] == 51 and len(sc) == 408, f'{sc[["window_id", "pipeline_id"]].drop_duplicates().shape[0]} cells, {len(sc)} sanity rows')
    elif kind == 'm18':
        sm = pd.read_csv(local / 'm18_training_history_cell_summary_seed43.csv')
        hs = pd.read_csv(local / 'm18_training_history_seed43.csv')
        add('twelve_families_51_cells', len(sm) == 612 and (sm.groupby(['task', 'model_name']).size() == 51).all(), f'{len(sm)} cells; rows per task/model {sm.groupby(["task", "model_name"]).size().unique().tolist()}')
        add('epoch_rows_match_summary', int(sm.epochs_logged.sum()) == len(hs), f'summary epochs {int(sm.epochs_logged.sum())}, table rows {len(hs)}')
    elif kind == 'commit_check':
        cc = pd.read_csv(local / 'runner_commit_check_seed43_cells.csv', keep_default_na=False)
        add('all_f1_patchtst_cells_have_commit', int((cc.runner_git_commit != 'NULL').sum()) == 510 and cc[cc.runner_git_commit != 'NULL'].runner_git_commit.nunique() == 1,
            f'{int((cc.runner_git_commit != "NULL").sum())} cells with a commit: {cc[cc.runner_git_commit != "NULL"].runner_git_commit.unique().tolist()}; NULL (Mantis) {int((cc.runner_git_commit == "NULL").sum())}')
    elif kind == 'evidence':
        ev = json.loads((local / 'runner_commit_evidence_lo_seed43.json').read_text(encoding='utf-8'))
        inv = json.loads((local / 'source_inventory_lo_seed43.json').read_text(encoding='utf-8'))['archives']
        add('all_code_tar_files_in_git_history', ev['files_in_code_tar'] == ev['files_found_in_repo_history'] and not ev['files_not_equal_to_any_commit'], f"{ev['files_found_in_repo_history']}/{ev['files_in_code_tar']} files; runner matches HEAD {ev['runner_matches_head']}")
        add('inventory_md5_matches_drive', len(inv) == 51 and all(r['md5'] == r['drive_md5'] for r in inv), f'{sum(1 for r in inv if r["md5"] == r["drive_md5"])}/{len(inv)} archives')
    results = [c['result'] for c in checks]
    status = 'L2_INGEST_BLOCKED' if 'FAIL' in results else ('L2_INGEST_CONDITIONS_MET_WITH_LABEL' if 'ACCEPTED_UNDER_Q32_REVIEW_PENDING_FOR_SEED43' in results else 'L2_INGEST_CONDITIONS_MET')
    rec_i = {'receipt_type': 'L2_INGEST_RECEIPT_CODE_TEAM', 'status': status, 'package': name, 'drive_path': drive, 'created_utc': datetime.now(timezone.utc).isoformat(),
             'note': 'Issued by the code team (2026-11-16) after checking the Drive copy against the local copy and the checkable ingest conditions of the 10/11 request and item 7 of the 13/11 request. It is not an independent verification by the writing side.', 'checks': checks}
    (ingest / f'l2_ingest_receipt_{safe}.json').write_text(json.dumps(rec_i, indent=1, default=str) + '\n', encoding='utf-8')
    idx_i.append((name, status, [c['check'] for c in checks if c['result'] == 'FAIL']))
    print(name, '| delivery problems', len(problems), '|', status, [c['check'] for c in checks if c['result'] == 'FAIL'], flush=True)
(deliv / 'README.md').write_text('# Delivery receipts of the seed-43 packages (2026-11-16, code team)\n\nByte-level verification of the Drive copies. They are not L2 ingest receipts and not an independent verification.\n\n'
                                 + ''.join(f'- `{n}`: {f} files, {p} problems, {s}\n' for n, f, p, s in idx_d), encoding='utf-8', newline='\n')
(ingest / 'README.md').write_text('# L2 ingest receipts of the seed-43 packages (2026-11-16, code team)\n\nChecks: official location in L2_facts/fact_exports with an identical staging backup (other packages: single location on Drive), byte identity, sha256sums, s_leak identity with the reference table (<= 1e-9), commit written at run time (Mantis: handled under Q-32 with label, reviewer acceptance of seed 43 pending), labels, resource_null_reason, source inventory, cohort status.\n\n'
                                  + ''.join(f'- `{n}`: {s}' + (f'; FAIL: {", ".join(f)}' if f else '') + '\n' for n, s, f in idx_i), encoding='utf-8', newline='\n')
for d in (deliv, ingest):
    (d / 'sha256sums.txt').write_bytes(''.join(f'{digest(p, "sha256")}  {p.name}\n' for p in sorted(d.iterdir()) if p.name != 'sha256sums.txt').encode())
print('RECEIPTS_DONE', len(PKGS))
