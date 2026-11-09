"""C3 (request 2026-11-09): delivery receipts for the three facts packages of 09/11 (CQ PatchTST V7-V16, LO PatchTST r2, CQ Mantis r2).

A receipt records, for every file of the package: size, sha256 (from the package's sha256sums.txt, re-checked here), local MD5 and the MD5 that
Drive reports now. It is a byte-level delivery receipt written by the code team; it is NOT the official L2 ingest receipt (status field says so).
Usage: python tools/build_delivery_receipts_20261109.py --out DIR
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
PACKAGES = [
    ('cq_patchtst_v7_v16_full_facts_20261109', Path('CQ/resuilt/cq_patchtst_v7_v16_full_facts_20261109'), 'CQ/L2_facts/fact_exports/cq_patchtst_v7_v16_full_facts_20261109'),
    ('lo_patchtst_v0_v16_full_facts_20261109_r2', Path('LO/resuilt/lo_patchtst_v0_v16_full_facts_20261109_r2'), 'LO/L2_facts/fact_exports/lo_patchtst_v0_v16_full_facts_20261109_r2'),
    ('cq_mantis_v2_v0_v16_full_facts_20261109_r2', Path('CQ/resuilt/cq_mantis_v2_v0_v16_full_facts_20261109_r2'), 'CQ/L2_facts/fact_exports/cq_mantis_v2_v0_v16_full_facts_20261109_r2'),
]


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def md5(p):
    h = hashlib.md5()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


args.out.mkdir(parents=True, exist_ok=True)
index = []
for name, local, drive in PACKAGES:
    sums = {}
    for line in (local / 'sha256sums.txt').read_text(encoding='utf-8').splitlines():
        h, rel = line.split('  ', 1)
        sums[rel] = h
    drive_md5 = {}
    out = subprocess.run(RC + ['md5sum', f'gdrive:{drive}'], capture_output=True, text=True).stdout
    for line in out.splitlines():
        h, rel = line.split('  ', 1)
        drive_md5[rel.strip()] = h
    parent, leaf = drive.rsplit('/', 1)
    listing = json.loads(subprocess.run(RC + ['lsjson', f'gdrive:{parent}', '--dirs-only'], capture_output=True, text=True).stdout)
    folder_id = next((e['ID'] for e in listing if e['Name'] == leaf), None)
    files, problems = [], []
    for p in sorted(x for x in local.rglob('*') if x.is_file()):
        rel = p.relative_to(local).as_posix()
        m5 = md5(p)
        entry = {'path': rel, 'bytes': p.stat().st_size, 'sha256': sha(p), 'md5': m5, 'drive_md5': drive_md5.get(rel), 'drive_md5_matches': drive_md5.get(rel) == m5}
        if rel != 'sha256sums.txt':
            entry['sha256_matches_sha256sums'] = sums.get(rel) == entry['sha256']
            if not entry['sha256_matches_sha256sums']:
                problems.append(f'sha256 differs from sha256sums.txt: {rel}')
        if not entry['drive_md5_matches']:
            problems.append(f'Drive MD5 differs or file missing on Drive: {rel}')
        files.append(entry)
    summary = json.loads((local / 'summary.json').read_text(encoding='utf-8'))
    inv = local / 'source_inventory.json'
    runner = local / 'runner_commit_evidence.json'
    receipt = {
        'receipt_type': 'DELIVERY_RECEIPT_CODE_TEAM', 'status': 'DELIVERED_AND_BYTE_VERIFIED_NOT_L2_INGESTED' if not problems else 'PROBLEMS',
        'note': 'Written by the code team on 2026-11-10. It verifies the Drive copy byte for byte; it is not an official L2 ingest receipt.',
        'package': name, 'drive_path': drive, 'drive_folder_id': folder_id, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'n_files': len(files), 'total_bytes': sum(f['bytes'] for f in files), 'problems': problems,
        'summary': {k: summary[k] for k in ('task', 'model', 'seed', 'versions', 'sanity_cells', 'slice_rows', 'per_class_rows', 'bootstrap_rows', 'resource_runs',
                                           'cohort_status_rows', 'cohort_status', 'cohort_status_counts', 'cohort_partition_counts', 'revision', 'r2_changes') if k in summary},
        'source_inventory': ({'file': 'source_inventory.json', 'sha256': sha(inv)} if inv.exists() else 'see source_inventory.json of the package (CQ PatchTST V7-V16)'),
        'runner_evidence': ({'file': 'runner_commit_evidence.json', 'sha256': sha(runner), **json.loads(runner.read_text(encoding='utf-8'))} if runner.exists()
                            else 'runner_git_commit 29da3b2 is recorded in the run manifests of this package'),
        'files': files,
    }
    (args.out / f'delivery_receipt_{name}.json').write_text(json.dumps(receipt, indent=1) + '\n', encoding='utf-8')
    index.append({'package': name, 'files': len(files), 'problems': len(problems), 'status': receipt['status'], 'drive_folder_id': folder_id})
    print(name, len(files), 'files', 'problems', len(problems), 'folder', folder_id)
(args.out / 'README.md').write_text(
    '# Delivery receipts of the facts packages of 09/11/2026 (code team)\n\nOne JSON per package with size, sha256, MD5 (local and as reported by Drive), source inventory, runner evidence and counts. '
    'They verify the Drive copies byte for byte; they are not official L2 ingest receipts.\n\n' + ''.join(f"- `{i['package']}`: {i['files']} files, {i['problems']} problems, {i['status']}\n" for i in index), encoding='utf-8')
with open(args.out / 'sha256sums.txt', 'w', encoding='utf-8', newline='\n') as fh:
    for p in sorted(args.out.iterdir()):
        if p.name != 'sha256sums.txt':
            fh.write(f'{sha(p)}  {p.name}\n')
