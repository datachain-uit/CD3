"""Delivery receipts (code team) of the packages delivered 10-12/11/2026: facts packages (CQ Mantis r3, CQ PatchTST r2 x2, LO PatchTST r2, LO Mantis), the revised meta releases and the M-18 training-history package.

For every file of a package: size, sha256 (re-checked against the package's sha256sums.txt), local MD5 and the MD5 Drive reports now. It is a byte-level delivery receipt;
it is NOT an official L2 ingest receipt (the status field says so).
Usage: python tools/build_delivery_receipts_20261112.py --out DIR
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--root-id', default='1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn')
args = ap.parse_args()
RC = ['rclone', '--drive-root-folder-id', args.root_id]
F = 'L2_facts/fact_exports'
PACKAGES = [
    ('cq_mantis_v2_v0_v16_full_facts_20261109_r3', 'CQ/resuilt', f'CQ/{F}', 'facts'),
    ('cq_patchtst_v0_v6_full_facts_20261103_r2', 'CQ/resuilt', f'CQ/{F}', 'facts'),
    ('cq_patchtst_v7_v16_full_facts_20261109_r2', 'CQ/resuilt', f'CQ/{F}', 'facts'),
    ('lo_patchtst_v0_v16_full_facts_20261109_r2', 'LO/resuilt', f'LO/{F}', 'facts'),
    ('lo_mantis_v2_v0_v16_full_facts_20261110', 'LO/resuilt', f'LO/{F}', 'facts'),
    ('meta_release_CQ_LO_p1_F2V0V16_20261112', 'CQ/resuilt', 'cross_task_meta/accepted', 'release'),
    ('meta_release_CQ_LO_full42_F1F2F3_20261112', 'CQ/resuilt', 'cross_task_meta/accepted', 'release'),
    ('m18_training_history_seed42_20261111', 'CQ/resuilt', 'cross_task_meta/accepted', 'other'),
    ('mm_runs_CQ_LO_p1_20261113', 'CQ/resuilt', 'cross_task_meta/accepted', 'other'),
    ('mm_runs_CQ_LO_full42_20261113', 'CQ/resuilt', 'cross_task_meta/accepted', 'other'),
]


def digest(p, algo):
    h = hashlib.new(algo)
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


args.out.mkdir(parents=True, exist_ok=True)
index = []
for name, base, dbase, kind in PACKAGES:
    local, drive = Path(base) / name, f'{dbase}/{name}'
    sums = {}
    for line in (local / 'sha256sums.txt').read_text(encoding='utf-8').splitlines():
        if line.strip():
            h, rel = line[:64], line[64:]
            sums[rel[2:].strip() if rel[:2] in ('  ', ' *') else rel.strip()] = h  # '<hash>  name' or '<hash> *name'
    drive_md5 = {}
    for line in subprocess.run(RC + ['md5sum', f'gdrive:{drive}'], capture_output=True, text=True).stdout.splitlines():
        if '  ' not in line:
            continue  # an empty file is listed without a hash
        h, rel = line.split('  ', 1)
        drive_md5[rel.strip()] = h
    parent, leaf = drive.rsplit('/', 1)
    listing = json.loads(subprocess.run(RC + ['lsjson', f'gdrive:{parent}', '--dirs-only'], capture_output=True, text=True).stdout)
    folder_id = next((e['ID'] for e in listing if e['Name'] == leaf), None)
    files, problems = [], []
    for p in sorted(x for x in local.rglob('*') if x.is_file()):
        rel = p.relative_to(local).as_posix()
        m5 = digest(p, 'md5')
        e = {'path': rel, 'bytes': p.stat().st_size, 'sha256': digest(p, 'sha256'), 'md5': m5, 'drive_md5': drive_md5.get(rel), 'drive_md5_matches': drive_md5.get(rel) == m5}
        if rel != 'sha256sums.txt':
            e['sha256_matches_sha256sums'] = sums.get(rel) == e['sha256']
            if not e['sha256_matches_sha256sums']:
                problems.append(f'sha256 differs from sha256sums.txt: {rel}')
        if not e['drive_md5_matches']:
            problems.append(f'Drive MD5 differs or file missing on Drive: {rel}')
        files.append(e)
    extra = {}
    if kind == 'facts':
        s = json.loads((local / 'summary.json').read_text(encoding='utf-8'))
        extra['summary'] = {k: s[k] for k in ('task', 'model', 'seed', 'versions', 'sanity_cells', 'slice_rows', 'per_class_rows', 'bootstrap_rows', 'resource_runs',
                                              'cohort_status_rows', 'cohort_status', 'cohort_status_counts', 'r2_changes') if k in s}
        for fn in ('source_inventory.json', 'runner_commit_evidence.json', 'audit_manifest.json'):
            if (local / fn).exists():
                extra[fn] = {'file': fn, 'sha256': digest(local / fn, 'sha256')}
    elif kind == 'release':
        m = json.loads((local / 'meta_release_manifest.json').read_text(encoding='utf-8'))
        extra['manifest_keys_checked'] = {k: m[k] for k in m if k in ('release_id', 'n_rows_seed_level', 'n_rows_seed_agg', 'registry_revision', 'f2_scope', 'created_utc') or k.startswith('n_')}
    receipt = {'receipt_type': 'DELIVERY_RECEIPT_CODE_TEAM', 'status': 'DELIVERED_AND_BYTE_VERIFIED_NOT_L2_INGESTED' if not problems else 'PROBLEMS',
               'note': 'Written by the code team on 2026-11-12. It verifies the Drive copy byte for byte; it is not an official L2 ingest receipt.',
               'package': name, 'drive_path': drive, 'drive_folder_id': folder_id, 'created_utc': datetime.now(timezone.utc).isoformat(), 'n_files': len(files),
               'total_bytes': sum(f['bytes'] for f in files), 'problems': problems, **extra, 'files': files}
    (args.out / f'delivery_receipt_{name}.json').write_text(json.dumps(receipt, indent=1) + '\n', encoding='utf-8')
    index.append({'package': name, 'files': len(files), 'problems': len(problems), 'status': receipt['status']})
    print(name, len(files), 'files', 'problems', len(problems), flush=True)
(args.out / 'README.md').write_text('# Delivery receipts of the packages of 10-12/11/2026 (code team)\n\nOne JSON per package with size, sha256, MD5 (local and as reported by Drive) and counts. They verify the Drive copies byte for byte; '
                                    'they are not official L2 ingest receipts.\n\n' + ''.join(f"- `{i['package']}`: {i['files']} files, {i['problems']} problems, {i['status']}\n" for i in index), encoding='utf-8', newline='\n')
with open(args.out / 'sha256sums.txt', 'w', encoding='utf-8', newline='\n') as fh:
    for p in sorted(args.out.iterdir()):
        if p.name != 'sha256sums.txt':
            fh.write(f'{digest(p, "sha256")}  {p.name}\n')
