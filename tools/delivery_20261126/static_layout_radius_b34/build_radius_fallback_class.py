"""Build radius_fallback_class_<task>_seed<NN>.csv (task CQ/LO x seed 42/43/44) with the schema of the CQ seed-42 audit file.
Sources (nothing is recomputed, no balancer is run):
  seed 42 CQ : the existing audit file radius_fallback_class_seed42.csv (Modal post-hoc audit of 2026-11-03), copied byte for byte after checking
               against the S2 run manifests (parent run id, generated rows, total fallback rows).
  seed 42 LO : the 12 radius_fallback.parquet files of the LO post-hoc audit (vastai, 2026-10-14); identity columns taken from the S2 run manifests.
  seed 43/44 : algorithm_audit.fallback_by_class of the 36 S2 run_manifest.json per task (written by the sampler during the S2 run).
Usage: python build_radius_fallback_class.py WORK_DIR
"""
import glob, hashlib, json, os, sys
import pandas as pd

WORK = sys.argv[1]
SRC, OUT = os.path.join(WORK, 'src'), os.path.join(WORK, 'out')
os.makedirs(OUT, exist_ok=True)
COLS = ['task', 'feature_regime', 'window_id', 'parent_pipeline', 'balance_pipeline', 'seed_augmentation', 'release_id', 'data_release_parent_run_id',
        'source_layout', 'audit_replay', 'class_code', 'radius', 'radius_space', 'generated_rows', 'fallback_nearest_neighbour_rows', 'fallback_nearest_neighbour_rate']
REGIME = {'CQ': 'CQ_RAW_EARLY', 'LO': 'LO_FULL_EARLY'}
PARENT_OF = {'V4': 'V1', 'V8': 'V5', 'V12': 'V9', 'V16': 'V13'}
RADIUS_PIPES = list(PARENT_OF)


def load_manifests(task, seed):
    """-> {(window, pipeline): (manifest, sha256)} for the Radius cells of one task/seed."""
    res = {}
    if seed == 44:
        files = glob.glob(os.path.join(SRC, 'seed44', f'{task}_W*__*.json'))
    else:
        files = glob.glob(os.path.join(SRC, f'seed{seed}', task, '**', 'run_manifest.json'), recursive=True)
    for f in files:
        raw = open(f, 'rb').read(); m = json.loads(raw)
        if m['task'] != task or m['run_status'] != 'SUCCESS' or int(m['seed_augmentation']) != seed:
            continue
        key = (m['window_id'], m['balance_pipeline'])
        assert key not in res, f'duplicate manifest {task} {seed} {key}'
        res[key] = (m, hashlib.sha256(raw).hexdigest())
    return res


def check_cells(man, task, seed):
    allk = {(w, f'V{i}') for w in ('W1', 'W2', 'W3') for i in range(2, 17) if i not in (5, 9, 13)}
    if set(man) != allk:
        return f'{len(man)} of 36 manifests ({task} seed {seed})'
    return None


def write(df, name, extra):
    p = os.path.join(OUT, name)
    df.to_csv(p, index=False, lineterminator='\n')
    print(name, len(df), 'rows', extra)


report = {}
for task in ('CQ', 'LO'):
    for seed in (42, 43, 44):
        name = f'radius_fallback_class_{task}_seed{seed}.csv'
        man = load_manifests(task, seed)
        miss = check_cells(man, task, seed)
        rad = {k: v for k, v in man.items() if k[1] in RADIUS_PIPES}
        if miss:
            report[name] = f'NOT_AVAILABLE: {miss}'
            continue
        rows = []
        if seed == 42 and task == 'CQ':
            old = pd.read_csv(os.path.join(SRC, 'cq_radius42', 'radius_fallback_class_seed42.csv'))
            for x in old.itertuples():
                m, _ = rad[(x.window_id, x.balance_pipeline)]
                assert x.data_release_parent_run_id == m['parent_imputation_run_id'] and int(x.generated_rows) == int(m['algorithm_config']['sampling_plan']['synthetic_target_per_class'][x.class_code])
            for (w, p), (m, _) in rad.items():
                s = old[(old.window_id == w) & (old.balance_pipeline == p)].fallback_nearest_neighbour_rows.sum()
                assert s == m['algorithm_audit']['fallback_nearest_neighbour_rows'], (w, p, s)  # audit total equals the total recorded by the run itself
            df = old[COLS]
        elif seed == 42:  # LO audit parquet, identity from manifests
            au = pd.concat([pd.read_parquet(f) for f in glob.glob(os.path.join(SRC, 'lo_radius42', '**', '*.parquet'), recursive=True)], ignore_index=True)
            for (w, p), (m, _) in sorted(rad.items(), key=lambda kv: (kv[0][0], int(kv[0][1][1:]))):
                a = au[(au.window_id == w) & (au.parent_pipeline == PARENT_OF[p])]
                plan = m['algorithm_config']['sampling_plan']['synthetic_target_per_class']
                assert PARENT_OF[p] == m['parent_pipeline'] and len(a) == sum(1 for v in plan.values() if int(v) > 0)
                for x in a.itertuples():
                    assert int(x.generated_rows) == int(plan[x.class_code]) and int(x.seed_augmentation) == 42
                    rows.append([task, REGIME[task], w, m['parent_pipeline'], p, 42, m['release_id'], m['parent_imputation_run_id'], 'NOT_AVAILABLE', True,
                                 x.class_code, x.radius, x.radius_space, int(x.generated_rows), int(x.fallback_nearest_neighbour_rows), float(x.fallback_nearest_neighbour_rate)])
                assert sum(r[14] for r in rows if r[2] == w and r[4] == p) == m['algorithm_audit']['fallback_nearest_neighbour_rows']
            df = pd.DataFrame(rows, columns=COLS)
        else:  # seeds 43 / 44: per-class values recorded by the sampler in the run manifest
            for (w, p), (m, _) in sorted(rad.items(), key=lambda kv: (kv[0][0], int(kv[0][1][1:]))):
                au = m['algorithm_audit']; plan = m['algorithm_config']['sampling_plan']['synthetic_target_per_class']
                fb = au['fallback_by_class']
                for cls, v in fb.items():
                    assert int(v['generated_rows']) == int(plan[cls])
                    rows.append([task, REGIME[task], w, m['parent_pipeline'], p, seed, m['release_id'], m['parent_imputation_run_id'], 'NOT_RECORDED_IN_RUN_MANIFEST', False,
                                 cls, au['radius'], au['radius_space'], int(v['generated_rows']), int(v['fallback_nearest_neighbour_rows']), float(v['fallback_nearest_neighbour_rate'])])
                assert sum(r[14] for r in rows if r[2] == w and r[4] == p) == au['fallback_nearest_neighbour_rows']
            df = pd.DataFrame(rows, columns=COLS)
        assert len(df) == 24, (name, len(df))
        if seed == 42 and task == 'CQ':
            import shutil; shutil.copyfile(os.path.join(SRC, 'cq_radius42', 'radius_fallback_class_seed42.csv'), os.path.join(OUT, name)); print(name, len(df), 'rows (byte copy)')
        else:
            write(df, name, '')
        report[name] = 'OK'
json.dump(report, open(os.path.join(WORK, 'radius_fallback_status.json'), 'w'), indent=1)
print(report)
