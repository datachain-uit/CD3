"""B.2: facts of the four seen/unseen subgroups for one unit (task x model x seed), computed from the stored sample-level predictions.

For every run (3 windows x 17 pipelines), split (VALIDATION, TEST) and phase (P1..P4): four rows, (LEARNER, SEEN), (LEARNER, UNSEEN), (COURSE, SEEN), (COURSE, UNSEEN).
Same function as the ALL/STRICT/OVERLAP slices (metrics_core.evaluation.classification_metrics), only the row mask changes. s_eff and s_leak are inherited from the run's ALL row
of the accepted facts; train class counts come from the TRAIN partition of the window (checked: the ALL row is recomputed and must equal the accepted facts).
Nothing is retrained or re-inferred; the accepted fact packages are not modified.

usage: build_subgroup_facts.py --task CQ --model RNN --seed 42 --pred-root DIR --facts FACTS.parquet --salt-file FILE --out DIR [--model-dir-in-path]
pred-root layout: <pred-root>/<task>/<W>/<V>/seed=<seed>/predictions/{validation,test}_<P>.parquet   (or <pred-root>/<W>/<V>/<MODEL>/seed=.. with --pred-glob)
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import REPO, WORK
import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, f'{REPO}')
from metrics_core.evaluation import COMPOSITE_EPS, classification_metrics  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--task', required=True)
ap.add_argument('--model', required=True)
ap.add_argument('--seed', type=int, required=True)
ap.add_argument('--pred-glob', required=True, help='path template with {W} {V} {split} {P}')
ap.add_argument('--facts', required=True, help='accepted facts table with s_eff, s_leak, macro_f1 ... per (window, pipeline, split, phase) for this model and seed')
ap.add_argument('--salt-file', required=True)
ap.add_argument('--flags', default=WORK + '/phaseB/seen_flags_{task}.parquet')
ap.add_argument('--out', required=True)
ap.add_argument('--pipelines', nargs='*')
args = ap.parse_args()

TASK = args.task
CLASSES = {'CQ': ('warning', 'average', 'good'), 'LO': ('I/D', 'G', 'E')}[TASK]
LABEL_COL = {'CQ': 'CQ_label_final', 'LO': 'LO_performance_label_3'}[TASK]
VIEW = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}[TASK]
REGIME = {'CQ': 'CQ_RAW_EARLY', 'LO': 'LO_FULL_EARLY'}[TASK]
SUBGROUPS = [('LEARNER', 'SEEN'), ('LEARNER', 'UNSEEN'), ('COURSE', 'SEEN'), ('COURSE', 'UNSEEN')]
out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
salt = Path(args.salt_file).read_bytes().decode('utf-8').rstrip('\n')

# train class counts per window (TRAIN partition of the phase view)
view = pd.read_parquet(glob.glob(f'{REPO}/downloads/raw_views_20261108/{VIEW}/*.parquet')[0], columns=['window', 'split', LABEL_COL])
counts = {}
for w in ('W1', 'W2', 'W3'):
    ids = view[(view.window == w) & (view.split == 'train')][LABEL_COL].astype(str).map({c: i for i, c in enumerate(CLASSES)})
    counts[w] = np.bincount(ids.dropna().astype(int), minlength=3)
del view

facts = pd.read_parquet(args.facts) if args.facts.endswith('parquet') else pd.read_csv(args.facts)
facts = facts[(facts.model_name == args.model) & (facts.seed == args.seed) & (facts.task == TASK)] if 'task' in facts else facts[(facts.model_name == args.model) & (facts.seed == args.seed)]
fidx = {(r.window_id, r.pipeline_id, r.eval_split, r.phase_id): r for r in facts.itertuples()}
flags_all = pd.read_parquet(args.flags.format(task=TASK))
flags_all['hash'] = None

hash_cache = {}


def flags_for(w, split, phase):
    key = (w, split, phase)
    if key not in hash_cache:
        f = flags_all[(flags_all.window_id == w) & (flags_all.split_name == split) & (flags_all.phase_id == phase)].copy()
        f['enrollment_id_hash'] = [hashlib.sha256(f'{salt}|{v}'.encode()).hexdigest() for v in f.enrollment_id.astype(str)]
        hash_cache[key] = f.set_index('enrollment_id_hash')[['seen_learner', 'seen_course', 'seen_offering']]
    return hash_cache[key]


def metric_row(y, probs, w, s_eff, s_leak):
    v = classification_metrics(y, probs, train_class_counts=counts[w], s_eff=s_eff, s_leak=s_leak)
    v['s_cal'] = max(0.0, 1.0 - float(v['ece']))
    v['s_san_plus_v2'] = float(np.prod(np.clip([v['s_nan'], v['s_maj_jsd'], v['s_cal'], v['s_drift'], v['s_eff'], v['s_leak']], COMPOSITE_EPS, 1.0)) ** (1 / 6))
    v['acctempo_m3'] = float((max(v['s_perf'], COMPOSITE_EPS) ** .6) * (max(v['s_san_plus'], COMPOSITE_EPS) ** .4))
    v['acctempo_m4'] = float((max(v['s_perf'], COMPOSITE_EPS) ** .6) * (max(v['s_san_plus_v2'], COMPOSITE_EPS) ** .4))
    return v


rows, qa = [], {'task': TASK, 'model': args.model, 'seed': args.seed, 'runs': 0, 'files_missing': [], 'hash_unmatched': 0, 'qa15_violations': 0, 'partition_failures': [], 'all_row_mismatch': [], 'max_all_row_abs_diff': 0.0, 'slice_status': {}}
pipes = args.pipelines or [f'V{i}' for i in range(17)]
CHECK = ('macro_f1', 's_perf', 's_san_plus_v2', 's_drift', 's_nan', 's_maj_jsd', 's_cal', 'acctempo_m3')
for w in ('W1', 'W2', 'W3'):
    for v_ in pipes:
        qa['runs'] += 1
        for split in ('VALIDATION', 'TEST'):
            for phase in ('P1', 'P2', 'P3', 'P4'):
                path = args.pred_glob.format(W=w, V=v_, split=('validation' if split == 'VALIDATION' else 'test'), P=phase)
                if not Path(path).exists():
                    qa['files_missing'].append(path); continue
                p = pd.read_parquet(path)
                fr = fidx.get((w, v_, split, phase))
                if fr is None:
                    qa['files_missing'].append(f'facts row {w}/{v_}/{split}/{phase}'); continue
                fl = flags_for(w, split, phase)
                m = p.enrollment_id_hash.map(fl.seen_learner)
                mc = p.enrollment_id_hash.map(fl.seen_course)
                mo = p.enrollment_id_hash.map(fl.seen_offering)
                if m.isna().any() or mc.isna().any():
                    qa['hash_unmatched'] += int(m.isna().sum()); continue
                qa['qa15_violations'] += int((mo != 0).sum())
                y = p.y_true.map({'c0': 0, 'c1': 1, 'c2': 2}).to_numpy()
                probs = p[['prob_c0', 'prob_c1', 'prob_c2']].to_numpy(float)
                s_eff, s_leak = float(fr.s_eff), float(fr.s_leak)
                allv = metric_row(y, probs, w, s_eff, s_leak)
                for c in CHECK:
                    if c in facts.columns:
                        d = abs(float(allv[c]) - float(getattr(fr, c)))
                        qa['max_all_row_abs_diff'] = max(qa['max_all_row_abs_diff'], d)
                        if d > 1e-12:
                            qa['all_row_mismatch'].append([w, v_, split, phase, c, d])
                conf = {}
                for axis, col in (('LEARNER', m.to_numpy()), ('COURSE', mc.to_numpy())):
                    for val, flag in (('SEEN', 1), ('UNSEEN', 0)):
                        sel = col == flag
                        yy, pp = y[sel], probs[sel]
                        support = np.bincount(yy, minlength=3) if len(yy) else np.zeros(3, dtype=int)
                        present = int((support > 0).sum())
                        status = 'SLICE_EMPTY' if len(yy) == 0 else ('ONE_CLASS' if present == 1 else 'OK')
                        row = {'task': TASK, 'feature_regime': REGIME, 'window_id': w, 'pipeline_id': v_, 'model_name': args.model, 'seed': args.seed, 'eval_split': split, 'phase_id': phase,
                               'subgroup_axis': axis, 'subgroup_value': val, 'slice_status': status, 'n_eval_samples': int(len(yy)), 'ev_n_classes_present': present,
                               'c0_support': int(support[0]), 'c1_support': int(support[1]), 'c2_support': int(support[2]), 's_eff': s_eff, 's_leak': s_leak,
                               'seen_rule_version': 'seen_v1_train_partition_only', 'seen_history_reference': 'TRAIN_PARTITION_ONLY'}
                        if status == 'OK':
                            vals = metric_row(yy, pp, w, s_eff, s_leak)
                            conf[(axis, val)] = np.asarray(vals['confusion_matrix'], dtype=np.int64)
                            for k, x in vals.items():
                                if k not in ('confusion_matrix',) and not isinstance(x, (list, dict, np.ndarray)):
                                    row[k] = x
                        elif status == 'ONE_CLASS':
                            cm = np.zeros((3, 3), dtype=np.int64); pred = pp.argmax(axis=1)
                            for t_, q_ in zip(yy, pred): cm[t_, q_] += 1
                            conf[(axis, val)] = cm
                        else:
                            conf[(axis, val)] = np.zeros((3, 3), dtype=np.int64)
                        qa['slice_status'][status] = qa['slice_status'].get(status, 0) + 1
                        rows.append(row)
                # partition check: SEEN + UNSEEN = ALL for each axis (confusion by argmax)
                allcm = np.zeros((3, 3), dtype=np.int64)
                for t_, q_ in zip(y, probs.argmax(axis=1)): allcm[t_, q_] += 1
                for axis in ('LEARNER', 'COURSE'):
                    if not np.array_equal(conf[(axis, 'SEEN')] + conf[(axis, 'UNSEEN')], allcm):
                        qa['partition_failures'].append([w, v_, split, phase, axis])
df = pd.DataFrame(rows)
df.to_csv(out / 'subgroup_components.csv', index=False, lineterminator='\n')
df.to_parquet(out / 'subgroup_components.parquet', index=False)
qa['rows'] = int(len(df)); qa['expected_rows'] = 3 * len(pipes) * 2 * 4 * 4
qa['status'] = 'PASS' if (not qa['files_missing'] and qa['hash_unmatched'] == 0 and qa['qa15_violations'] == 0 and not qa['partition_failures'] and not qa['all_row_mismatch'] and qa['rows'] == qa['expected_rows']) else 'FAIL'
(out / 'summary.json').write_text(json.dumps(qa, indent=1), encoding='utf-8')
print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in qa.items()}, indent=1))
