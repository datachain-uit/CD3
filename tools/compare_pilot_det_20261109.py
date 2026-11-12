"""Determinism pilot (check 37 (d)): compare two fresh runs A and B of one cell (pilot_hashes.json written by pilot_det.sh) and,
if given, the original run. Reports per artefact class whether the sha256 values are identical.
Usage: python tools/compare_pilot_det_20261109.py --task CQ --a A/pilot_hashes.json --b B/pilot_hashes.json [--env-a F --env-b F]
       [--orig-probs-dir DIR(with validation_probabilities.npy, test_probabilities.npy)] --a-probs DIR --out report.json
"""
import argparse
import hashlib
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--task', required=True)
ap.add_argument('--a', type=Path, required=True)
ap.add_argument('--b', type=Path, required=True)
ap.add_argument('--env-a', type=Path)
ap.add_argument('--env-b', type=Path)
ap.add_argument('--cell-a', type=Path, help='pilot_cell_record.json of A')
ap.add_argument('--cell-b', type=Path)
ap.add_argument('--orig-probs-dir', type=Path)
ap.add_argument('--a-probs-dir', type=Path)
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()
A, B = json.loads(args.a.read_text()), json.loads(args.b.read_text())


def cls(path):
    n = path.rsplit('/', 1)[-1]
    if n == 'manifest.json' and '/split=' in path:
        return None  # cache manifests carry created_at_utc (creation time): not part of the determinism claim
    if n.startswith('channel_adapter'):
        return 'adapter'
    if '/split=REAL_TRAIN/' in path or '/split=VALIDATION/' in path or '/split=TEST/' in path:
        return 'level_A_embeddings_' + ('frames' if n == 'frames.bin' else 'index_rowids_manifest')
    if n.endswith('_probabilities.npy'):
        return 'probabilities'
    if n == 'probe_head.pt':
        return 'probe_head'
    if path.startswith('runs/W1/V0/predictions/'):
        return 'predictions_parquet_file'
    return None  # timing/metadata files are not part of the determinism claim


groups = {}
for p in sorted(set(A) | set(B)):
    c = cls(p)
    if c is None:
        continue
    g = groups.setdefault(c, {'files': 0, 'identical': 0, 'differing': [], 'only_one_side': []})
    g['files'] += 1
    if p not in A or p not in B:
        g['only_one_side'].append(p)
    elif A[p]['sha256'] == B[p]['sha256']:
        g['identical'] += 1
    else:
        g['differing'].append(p)
out = {'excluded_from_claim': ['cache split manifest.json (created_at_utc)', 'timing and metadata files'], 'task': args.task, 'cell': f'{args.task}/W1/V0/seed42', 'groups': {k: {kk: (vv if not isinstance(vv, list) else vv[:6]) for kk, vv in v.items()} for k, v in groups.items()}}
for name, pa, pb in (('env', args.env_a, args.env_b), ('cell_record', args.cell_a, args.cell_b)):
    if pa and pb:
        ta, tb = pa.read_text().strip(), pb.read_text().strip()
        if name == 'cell_record':
            ja, jb = json.loads(ta), json.loads(tb)
            out['cell_record'] = {k: ja.get(k) == jb.get(k) for k in ('spec_digest', 'encoder_digest', 'real_train_input_sha256', 'best_epoch', 'epochs_trained', 'train_rows_real', 'train_rows_synthetic')}
            out['cell_record']['adapter_digest_equal'] = ja.get('adapter', {}).get('digest') == jb.get('adapter', {}).get('digest')
            out['cell_record']['adapter_digests'] = [ja.get('adapter', {}).get('digest'), jb.get('adapter', {}).get('digest')]
        else:
            out['library_versions'] = {'a': ta, 'b': tb, 'identical': ta == tb}
if args.orig_probs_dir and args.a_probs_dir:
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    out['vs_original'] = {s: sha(args.orig_probs_dir / f'{s}_probabilities.npy') == sha(args.a_probs_dir / f'{s}_probabilities.npy') for s in ('validation', 'test')}
strict = [k for k in groups if k != 'predictions_parquet_file']
out['all_identical_except_parquet_file_bytes'] = all(not groups[k]['differing'] and not groups[k]['only_one_side'] for k in strict)
out['verdict'] = 'PASS' if out['all_identical_except_parquet_file_bytes'] else 'DIFFERENCES'
args.out.write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
print(json.dumps({k: out[k] for k in ('cell', 'verdict')} | {'groups': {k: f"{v['identical']}/{v['files']}" for k, v in groups.items()}}, indent=1))
