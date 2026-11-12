"""C3 (request 2026-11-09): runner commit, source inventory and delivery receipts for the LO PatchTST and CQ Mantis facts packages (r2).

runner_git_commit is recorded for the 102 runs whose manifests carry none:
  LO PatchTST (51 runs): the code directory used on the hosts (lo_patchtst_seed42_code, 37 files, identical on all 12 hosts after
      line-ending normalisation) is byte-equal to the repository at the commit found by `git`; the earliest such commit is recorded,
      the later commits with the same content are listed in runner_commit_evidence.json.
  CQ Mantis (48 runs V1-V16): tools/run_mantis_cq_grid_zstd_20261108.py (sha256 2cc8e3f8...) is the blob of commit 6a69b7f; the code tar
      (sha256 a8a9a10f...) is checked by the launch scripts; its model/* files equal commit 5872cac. The 3 V0 runs came from the earlier
      single-pipeline script and stay NULL.
The mapping is retroactive: the commits were made after the runs (blob identity, not a value written at run time).
Usage: python tools/build_c3_runner_commit_inventory_20261109.py --source-hashes TSV --host-hashes FILE
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--source-hashes', type=Path, required=True, help='TSV: drive path, bytes, sha256, md5')
ap.add_argument('--host-hashes', type=Path, required=True, nargs='+', help='one file per host: sha256 (LF-normalised) and relative path of the files of lo_patchtst_seed42_code; the first file is the reference for the commit match')
args = ap.parse_args()
LO = Path('LO/resuilt/lo_patchtst_v0_v16_full_facts_20261109_r2')
MT = Path('CQ/resuilt/cq_mantis_v2_v0_v16_full_facts_20261109_r2')


def git(*a):
    return subprocess.run(['git', *a], capture_output=True)


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write_sums(d):
    files = sorted(p for p in d.rglob('*') if p.is_file() and p.name != 'sha256sums.txt')
    with open(d / 'sha256sums.txt', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(''.join(f'{sha(p)}  {p.relative_to(d).as_posix()}\n' for p in files))


# ---- LO PatchTST: tree match of the host code directory against the repository history
def read_host(path):
    out = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            h, p = line.strip().split(' ', 1)
            out[(p.strip()[2:] if p.strip().startswith('./') else p.strip())] = h
    return out


host_maps = [read_host(p) for p in args.host_hashes]
host = host_maps[0]
common = set.intersection(*(set(m) for m in host_maps))
n_identical_hosts = sum(1 for m in host_maps if {p: m[p] for p in common} == {p: host_maps[0][p] for p in common})
matches = []
for entry in git('log', '--since=2026-10-10', '--format=%H %ad', '--date=short').stdout.decode().splitlines():
    c = entry.split()[0]
    mism = absent = equal = 0
    for path, h in host.items():
        r = git('show', f'{c}:{path}')
        if r.returncode:
            absent += 1
        elif hashlib.sha256(r.stdout.replace(b'\r\n', b'\n')).hexdigest() == h:
            equal += 1
        else:
            mism += 1
    if mism == 0:
        matches.append({'commit': c, 'date': entry.split()[1], 'files_equal': equal, 'files_not_in_commit': absent})
if not matches:
    raise SystemExit('no repository commit matches the host code directory')
lo_commit = matches[-1]['commit']          # git log is newest first: the last element is the earliest matching commit
lo_evidence = {'basis': 'CODE_DIR_TREE_MATCH', 'runner': 'tools/vastai_train_shared.py', 'host_code_dir': 'lo_patchtst_seed42_code',
               'files_compared': len(host), 'line_endings': 'CRLF/LF normalised', 'hosts_compared': len(host_maps), 'files_present_on_every_host': len(common), 'hosts_with_identical_common_file_set': n_identical_hosts,
               'earliest_matching_commit': lo_commit, 'all_matching_commits': matches,
               'note': 'files that exist in the code dir of some hosts only (for example check_gpu.py) are not part of the common set and are not in the repository; the other files are equal. The commit mapping is retroactive.'}
lo = pd.read_parquet(LO / 'resource_per_run.parquet')
lo['runner_git_commit'] = lo_commit
lo['runner_git_commit_basis'] = 'CODE_DIR_TREE_MATCH_RETROACTIVE'
lo.to_parquet(LO / 'resource_per_run.parquet', index=False)
lo.to_csv(LO / 'resource_per_run.csv', index=False)

# ---- CQ Mantis: runner blob and code tar
runner = 'tools/run_mantis_cq_grid_zstd_20261108.py'
runner_sha = '2cc8e3f8b48d002ca4be3f1938007c1d75b50a8854b9282d8b307d7112b1d595'
code_tar_sha = 'a8a9a10fc89488a862e7e73d300215d1274b633576eb737fec19477e284cdb1c'
log = git('log', '--format=%H %ad', '--date=short', '--', runner).stdout.decode().strip().splitlines()
mt_commit = None
for entry in log:
    c = entry.split()[0]
    if hashlib.sha256(git('show', f'{c}:{runner}').stdout).hexdigest() == runner_sha:
        mt_commit = c
if mt_commit is None:
    raise SystemExit('Mantis runner blob not found in git history')
mt_evidence = {'basis': 'RUNNER_BLOB_SHA256_MATCH', 'runner': runner, 'runner_sha256': runner_sha, 'commit': mt_commit,
               'code_tar': 'mantis_grid_code_20261108.tar', 'code_tar_sha256': code_tar_sha,
               'code_tar_note': 'the launch scripts of the child cells check this sha256 before running; the standardised manifests carry runner_sha256 and code_tar_sha256',
               'tar_model_files_equal_commit': '5872cac (model/architectures.py, model/config.py, model/metrics.py; later commits changed them)',
               'v0_cells': {'runner_git_commit': None,
                            'decision': 'left NULL (writing-side recommendation Q-32 (a), applied 2026-11-10, author ratification pending): the runner hash was not recorded and no copy used for the runs exists',
                            'runner': 'tools/run_mantis_v0_cq_zstd_20261107.py (started by tools/mantis_v0_cq_full_20261107.sh), not the grid runner',
                            'indirect_evidence_not_a_hash_match': {
                                'git_versions_of_the_runner_file': 1, 'only_commit': '6a69b7f (made after the runs)',
                                'file_last_modified': '2026-11-07 09:18 (UTC+7), before the first V0 cell finished',
                                'v0_cells_completed': {'W1': '2026-11-08 02:44', 'W2': '2026-11-08 05:45', 'W3': '2026-11-08 11:15'},
                                'code_tar_of_the_runs': 'mantis_v0_code_20261107.tar.gz does not contain the runner file; no host keeps a copy'}},
               'note': 'the commit was made after the runs (blob identity, retroactive)'}
mt = pd.read_parquet(MT / 'resource_per_run.parquet')
is_v0 = mt.pipeline_id == 'V0'
mt['runner_git_commit'] = None
mt.loc[~is_v0, 'runner_git_commit'] = mt_commit
mt['runner_git_commit_basis'] = None
mt.loc[~is_v0, 'runner_git_commit_basis'] = 'RUNNER_BLOB_SHA256_MATCH_RETROACTIVE'
mt.loc[is_v0, 'runner_git_commit_basis'] = 'NOT_RECORDED_V0_EARLIER_SCRIPT'
mt.to_parquet(MT / 'resource_per_run.parquet', index=False)
mt.to_csv(MT / 'resource_per_run.csv', index=False)

# ---- source inventories
rows = [l.rstrip('\n').split('\t') for l in args.source_hashes.read_text(encoding='utf-8').splitlines() if l.strip()]
inv = {'LO': [], 'MT': []}
for path, size, h, md5 in rows:
    entry = {'drive_path': path, 'bytes': int(size), 'sha256': h, 'drive_md5': md5}
    if path.startswith('LO/'):
        inv['LO'].append(entry)
    else:
        inv['MT'].append(entry)
for key, pkg, evid, scope in (('LO', LO, lo_evidence, 'LO PatchTST V1-V16 result bundles; V0 is a run tree under LO/L1_runs/S3_model/primary/family=PATCHTST/lo_patchtst_v0_seed42_20261107 (no archive)'),
                              ('MT', MT, mt_evidence, 'CQ Mantis result tars V0-V16')):
    (pkg / 'source_inventory.json').write_text(json.dumps({'scope': scope, 'archives': sorted(inv[key], key=lambda e: e['drive_path']), 'runner': evid}, indent=2) + '\n', encoding='utf-8')
    (pkg / 'runner_commit_evidence.json').write_text(json.dumps(evid, indent=2) + '\n', encoding='utf-8')
    summary = json.loads((pkg / 'summary.json').read_text(encoding='utf-8'))
    summary.setdefault('r2_changes', []).append(f'runner_git_commit filled ({evid["basis"]}); source_inventory.json and runner_commit_evidence.json added')
    (pkg / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    readme = (pkg / 'README.md').read_text(encoding='utf-8')
    (pkg / 'README.md').write_text(readme + '\n## Revision r2b (10/11/2026): runner commit and source inventory\n\n`resource_per_run.runner_git_commit` is now filled with the basis in '
                                   '`runner_git_commit_basis` (see `runner_commit_evidence.json`); the mapping from file content to commit is retroactive, the commits were made after '
                                   'the runs. `source_inventory.json` lists every source archive with bytes, sha256 and Drive MD5.\n', encoding='utf-8')
    write_sums(pkg)
print(json.dumps({'lo_commit': lo_commit, 'lo_matching_commits': [m['commit'][:7] for m in matches], 'mantis_commit': mt_commit,
                  'lo_rows_filled': int(lo.runner_git_commit.notna().sum()), 'mantis_rows_filled': int(mt.runner_git_commit.notna().sum()),
                  'archives': {k: len(v) for k, v in inv.items()}}, indent=1))
