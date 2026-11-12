"""Runner/commit evidence of the Mantis CQ seed-43 cells (the cell manifests of this grid carry no runner commit).

The cells were run from the code tar `mantis_lo_code_20261109.tar` (identical sha256 on every host that ran a Mantis cell, checked by the caller and given with --host-tar-sha256).
For every file of the tar this script finds the git commits whose content equals the file (CRLF/LF normalised) and writes the mapping, plus an inventory of the result tars
(cell identity from their manifests, bytes, sha256, Drive MD5). The mapping is retroactive: the commits were made after the runs (blob identity, not a value written at run time).
Usage: python tools/build_mantis_seed43_runner_evidence_20261112.py --code-tar TAR --tars-dir DIR_OF_RESULT_TARS --out DIR --host-tar-sha256 SHA --hosts-checked N
"""
import argparse
import csv
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--code-tar', type=Path, required=True)
ap.add_argument('--tars-dir', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--host-tar-sha256', required=True)
ap.add_argument('--hosts-checked', type=int, required=True)
ap.add_argument('--since', default='2026-11-05')
args = ap.parse_args()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def norm(b):
    return sha(b.replace(b'\r\n', b'\n'))


def git(*a):
    return subprocess.run(['git', *a], capture_output=True)


tar_sha = sha(args.code_tar.read_bytes())
assert tar_sha == args.host_tar_sha256, 'local code tar differs from the sha256 found on the hosts'
files = {m.name: tarfile.open(args.code_tar).extractfile(m).read() for m in tarfile.open(args.code_tar).getmembers() if m.isfile()}
commits = [l.split() for l in git('log', '--format=%H %cI', f'--since={args.since}').stdout.decode().splitlines()]
rows = []
for name, data in sorted(files.items()):
    want = norm(data)
    hits = []
    for c, d in commits:
        r = git('show', f'{c}:{name}')
        if r.returncode == 0 and norm(r.stdout) == want:
            hits.append((c, d))
    rows.append({'file': name, 'sha256_lf': want, 'n_matching_commits': len(hits), 'earliest_matching_commit': hits[-1][0] if hits else '', 'earliest_commit_date': hits[-1][1] if hits else '',
                 'matches_head': bool(hits) and hits[0][0] == commits[0][0], 'in_repo_history': bool(hits)})
args.out.mkdir(parents=True, exist_ok=True)
with open(args.out / 'code_tar_file_to_commit.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
runner = 'tools/run_mantis_grid_zstd_20261109.py'
rr = next(r for r in rows if r['file'] == runner)
inv = []
for t in sorted(args.tars_dir.rglob('mantis_cq43_*_results.tar.gz')):
    with tarfile.open(t) as tf:
        man = next(m for m in tf.getmembers() if m.name.endswith('run_manifest.json'))
        d = json.loads(tf.extractfile(man).read())
    inv.append({'file': t.name, 'task': d['task'], 'window': d['window'], 'pipeline': d['pipeline'], 'parent': d.get('parent'), 'seed': d['seed'], 'bytes': t.stat().st_size,
                'sha256': sha(t.read_bytes()), 'md5': hashlib.md5(t.read_bytes()).hexdigest()})
evidence = {'basis': 'CODE_TAR_FILE_BLOB_MATCH_RETROACTIVE', 'runner': runner, 'runner_sha256_lf': rr['sha256_lf'], 'runner_earliest_matching_commit': rr['earliest_matching_commit'],
            'runner_matches_head': rr['matches_head'], 'code_tar': args.code_tar.name, 'code_tar_sha256': tar_sha, 'hosts_checked_with_identical_code_tar': args.hosts_checked,
            'files_in_code_tar': len(rows), 'files_found_in_repo_history': sum(r['in_repo_history'] for r in rows),
            'files_not_equal_to_any_commit': [r['file'] for r in rows if not r['in_repo_history']], 'cells_in_inventory': len(inv),
            'note': 'the commits were made after the runs (blob identity, retroactive); the cell manifests carry no runner commit'}
(args.out / 'runner_commit_evidence_cq_seed43.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
(args.out / 'source_inventory_cq_seed43.json').write_text(json.dumps({'scope': 'CQ Mantis seed 43 result tars', 'archives': inv}, indent=2) + '\n', encoding='utf-8')
(args.out / 'README.md').write_text(
    '# Runner commit evidence, Mantis CQ seed 43\n\nThe cell manifests of this grid carry no runner commit. `runner_commit_evidence_cq_seed43.json` maps the runner and every file of the code tar used for the runs '
    '(`mantis_lo_code_20261109.tar`, same sha256 on every host that ran a cell) to the git commits with identical content (`code_tar_file_to_commit.csv`). The mapping is retroactive: '
    'the commits were made after the runs. `source_inventory_cq_seed43.json` lists the result tars covered (cell identity, bytes, sha256, MD5).\n', encoding='utf-8')
lines = [f'{sha(p.read_bytes())}  {p.name}\n' for p in sorted(args.out.iterdir()) if p.name != 'sha256sums.txt']
(args.out / 'sha256sums.txt').write_bytes(''.join(lines).encode())
print(json.dumps(evidence, indent=1))
