"""S2 artefacts of one master seed (request 2026-11-10 7.1): plan.json, run_summary.csv, ledger inventory, per-class sampling summary with
kappa_reached and Radius fallback, taken from the 72 run manifests written by tools/vastai_run_s2_augmentation.py.

kappa_reached = max_class_n_after / n_after_class (an imbalance ratio, not Cohen's kappa; definition of 2026-11-07).
Radius fallback per class comes from the run manifest itself (algorithm_audit.fallback_by_class); no replay is needed.
Usage: python tools/build_s2_sampling_artefacts_20261110.py --manifests DIR --ledger-sums FILE --seed 43 --out DIR
  --ledger-sums: lines "sha256  bytes  run_id" for every synthetic_ledger.parquet (computed on the hosts that hold them)
"""
import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--manifests', type=Path, required=True)
ap.add_argument('--ledger-sums', type=Path, required=True)
ap.add_argument('--seed', type=int, required=True)
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()

PRE = chr(92) * 2 + '?' + chr(92) if os.name == 'nt' else ''
PIPES = {'CDSMOTE': ['V2', 'V6', 'V10', 'V14'], 'SASMOTE': ['V3', 'V7', 'V11', 'V15'], 'RADIUS_SMOTE': ['V4', 'V8', 'V12', 'V16']}
PARENT = {'V2': 'V1', 'V3': 'V1', 'V4': 'V1', 'V6': 'V5', 'V7': 'V5', 'V8': 'V5', 'V10': 'V9', 'V11': 'V9', 'V12': 'V9',
          'V14': 'V13', 'V15': 'V13', 'V16': 'V13'}
METHOD = {p: m for m, ps in PIPES.items() for p in ps}


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(PRE + str(p.resolve()) if PRE else p, 'rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


ledgers = {}
for line in args.ledger_sums.read_text(encoding='utf-8').splitlines():
    if line.strip():
        sha, size, run_id = line.split()[:3]
        ledgers[run_id] = (sha, int(size))

manifests = []
root = (PRE + str(args.manifests.resolve())) if PRE else str(args.manifests)
for dp, dn, fn in os.walk(root):
    if 'run_manifest.json' in fn and f'BALANCED_TRAIN_ONLY{os.sep}seed={args.seed}{os.sep}' in dp:
        path = os.path.join(dp, 'run_manifest.json')
        raw = open(path, 'rb').read()
        manifests.append((json.loads(raw.decode('utf-8')), sha_bytes(raw), os.path.join(dp, 's2_environment.json')))
if len(manifests) != 72:
    raise SystemExit(f'expected 72 manifests for seed {args.seed}, found {len(manifests)}')

for task in ('CQ', 'LO'):
    mine = [x for x in manifests if x[0]['task'] == task]
    if len(mine) != 36:
        raise SystemExit(f'{task}: {len(mine)} manifests')
    rows, inv, summ, plan = [], [], [], []
    for m, msha, envp in sorted(mine, key=lambda x: (x[0]['window_id'], int(x[0]['balance_pipeline'][1:]))):
        w, pipe = m['window_id'], m['balance_pipeline']
        if (m['run_status'], int(m['seed_augmentation']), m['parent_pipeline'], m['phase_id']) != ('SUCCESS', args.seed, PARENT[pipe], 'P4'):
            raise SystemExit(f'identity mismatch {task}/{w}/{pipe}')
        if m['validation_test_touched']:
            raise SystemExit(f'validation/test touched {task}/{w}/{pipe}')
        if m['run_id'] not in ledgers:
            raise SystemExit(f'no ledger hash for {task}/{w}/{pipe}')
        lsha, lbytes = ledgers[m['run_id']]
        before, after = m['class_counts_before'], m['class_counts_after']
        plan_t = m['algorithm_config']['sampling_plan']['synthetic_target_per_class']
        audit = m.get('algorithm_audit') or {}
        fb = audit.get('fallback_by_class', {}) if METHOD[pipe] == 'RADIUS_SMOTE' else {}
        if sum(map(int, before.values())) != int(m['rows_original']) or sum(map(int, after.values())) != int(m['rows_balanced']):
            raise SystemExit(f'count mismatch {task}/{w}/{pipe}')
        majority_before, majority_after = max(map(int, before.values())), max(map(int, after.values()))
        order = {'warning': 0, 'average': 1, 'good': 2} if task == 'CQ' else {'E': 0, 'G': 1, 'I/D': 2}  # class order of the seed-42 exports
        if set(before) != set(order):
            raise SystemExit(f'unexpected class codes {sorted(before)}')
        for label, idx in sorted(order.items(), key=lambda kv: kv[1]):
            n, z = int(before[label]), int(after[label])
            gen = z - n
            if gen != int(plan_t[label]):
                raise SystemExit(f'sampling mismatch {task}/{w}/{pipe}/{label}')
            target = min(max(n, math.ceil(majority_before / 10)), 10 * n)
            f = fb.get(label)
            rows.append({'task': task, 'window_id': w, 'pipeline_id': pipe, 'balancer': METHOD[pipe], 'class_index': idx, 'class_code': label,
                         'n_train_before': n, 'n_target': target, 'n_generated': gen, 'n_after': z,
                         'achieved_expansion_ratio': z / n if n else None, 'achieved_majority_to_class_ratio': majority_after / z if z else None,
                         'kappa_reached': majority_after / z if z else None, 'kappa_status': 'DEFINED_MAJORITY_AFTER_OVER_CLASS_AFTER',
                         'ir_target': 10, 'ir_target_met': bool(z and majority_after <= 10 * z), 'expansion_cap': 10,
                         'expansion_cap_reached': bool(z == 10 * n and n < majority_before),
                         'expansion_cap_bound': bool(math.ceil(majority_before / 10) > 10 * n),
                         'fallback_count': (int(f['fallback_nearest_neighbour_rows']) if f else None),
                         'fallback_rate': (float(f['fallback_nearest_neighbour_rate']) if f else None),
                         'fallback_class_status': ('FROM_RUN_MANIFEST_ALGORITHM_AUDIT' if f else 'NOT_APPLICABLE'),
                         'sampling_seed': args.seed, 'run_manifest_sha256': msha,
                         'warning_flags': 'RADIUS_FALLBACK_GT_0_50' if f and float(f['fallback_nearest_neighbour_rate']) > 0.5 else ''})
        rs = m['resource_summary']
        summ.append({'task': task, 'window_id': w, 'pipeline_id': pipe, 'parent_pipeline': m['parent_pipeline'], 'balancer': METHOD[pipe],
                     'seed_augmentation': args.seed, 'run_status': m['run_status'], 'run_id': m['run_id'], 'attempt_id': m['attempt_id'],
                     'rows_original': m['rows_original'], 'rows_synthetic': m['rows_synthetic'], 'rows_balanced': m['rows_balanced'],
                     'time_run_total_s': rs.get('time_run_total_s'), 'peak_ram_mb': rs.get('peak_ram_mb'),
                     'parent_imputation_run_id': m['parent_imputation_run_id'], 'run_manifest_sha256': msha, 'ledger_sha256': lsha})
        inv.append({'window_id': w, 'pipeline_id': pipe, 'manifest_relative_path': f'{w}/{pipe}/run_manifest.json', 'manifest_sha256': msha,
                    'ledger_relative_path': f'{w}/{pipe}/synthetic_ledger.parquet', 'ledger_sha256': lsha, 'ledger_bytes': lbytes,
                    'ledger_hash_status': 'COMPUTED_ON_HOST_AT_CREATION'})
        plan.append({'task': task, 'window': w, 'parent_pipeline': m['parent_pipeline'], 'method': METHOD[pipe], 'seed': args.seed,
                     'release_id': m['release_id'], 'balance_pipeline': pipe})
    df = pd.DataFrame(rows)
    if task == 'LO':  # column names of the seed-42 LO export
        df['parent_pipeline'] = df.pipeline_id.map(PARENT)
        df = df.rename(columns={'n_train_before': 'n_before', 'achieved_majority_to_class_ratio': 'majority_to_class_ratio',
                                'fallback_class_status': 'fallback_status'}).drop(columns=['class_index', 'achieved_expansion_ratio'])
        df['radius_warning'] = df.warning_flags
        df = df.drop(columns=['warning_flags'])
    out = args.out / task
    out.mkdir(parents=True, exist_ok=True)
    name = f's2_sampling_summary_{task.lower()}_seed{args.seed}'
    df.to_csv(out / f'{name}.csv', index=False)
    df.to_parquet(out / f'{name}.parquet', index=False)
    pd.DataFrame(summ).to_csv(out / 'run_summary.csv', index=False)
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    (out / 'ledger_inventory.json').write_text(json.dumps({'entries': inv}, indent=2) + '\n', encoding='utf-8')
    definition = {'name': 'kappa_reached', 'definition': 'max_class_n_after / n_after_class', 'target_criterion': 'max_class_n_after <= 10 * n_after_class',
                  'cap_bound_criterion': 'ceil(max_class_n_before / 10) > 10 * n_before_class', 'zero_support': 'undefined; fail closed in this export',
                  'not_cohens_kappa': True, 'approved_in_conversation': '2026-11-07'}
    (out / 'METRIC_DEF_kappa_reached.json').write_text(json.dumps(definition, indent=2) + '\n', encoding='utf-8')
    fb_rows = df[df.fallback_count.notna()]
    summary = {'task': task, 'seed': args.seed, 'created_at_utc': datetime.now(timezone.utc).isoformat(), 'runs': len(inv), 'sampling_summary_rows': len(df),
               'radius_fallback_rows': len(fb_rows), 'radius_fallback_gt_0_50_rows': int((fb_rows.fallback_rate > 0.5).sum()),
               'kappa_defined_rows': int(df.kappa_reached.notna().sum()), 'ir_target_not_met_rows': int((~df.ir_target_met).sum()),
               'expansion_cap_bound_rows': int(df.expansion_cap_bound.sum()), 'target_rule_and_generated_counts': 'PASS',
               'fallback_source': 'algorithm_audit of each Radius run manifest (no replay)', 'executed_outside_modal': True,
               'runner': 'tools/vastai_run_s2_augmentation.py'}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (out / 'README.md').write_text(
        f'# S2 {task} seed {args.seed}\n\nOne row per (window, pipeline, class) from the 36 successful run manifests (`run_summary.csv`: one row per run, '
        f'`plan.json`: the 36 planned cells, `ledger_inventory.json`: sha256 of every manifest and ledger). `kappa_reached` = max post-augmentation class support / '
        'post-augmentation support of the class (imbalance ratio, not Cohen\'s kappa); `ir_target_met` when <= 10. Radius fallback counts are the per-class values '
        'of the run manifests. The S2 cells of this seed were executed with the same `run_augmentation` code as seed 42 (executed outside Modal; library versions '
        'in each `s2_environment.json`).\n', encoding='utf-8')
    for p in [out]:
        files = sorted(x for x in p.iterdir() if x.is_file() and x.name != 'sha256sums.txt')
        (p / 'sha256sums.txt').write_text(''.join(f'{hashlib.sha256(x.read_bytes()).hexdigest()}  {x.name}\n' for x in files), encoding='utf-8')
    print(task, summary)
