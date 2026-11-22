"""B.2: facts of the four seen/unseen subgroups for one unit (task x model x seed), computed from the stored sample-level predictions.

For every run (3 windows x 17 pipelines), split (VALIDATION, TEST) and phase (P1..P4): four rows, (LEARNER, SEEN), (LEARNER, UNSEEN), (COURSE, SEEN), (COURSE, UNSEEN).
Same function as the ALL/STRICT/OVERLAP slices (metrics_core.evaluation.classification_metrics), only the row mask changes.
Columns: a subgroup row carries the columns of the accepted ALL row of the unit: slice-level columns recomputed on the slice, run- and cell-level columns copied from the ALL row (s_leak, s_leak_probe_auc, s_eff, probe_* ...).
Self-checks (summary.json): the ALL row recomputed from the predictions against the accepted facts on every common numeric column (max abs difference per column; threshold 1e-12; log_loss and pr_auc_macro reported only),
SEEN + UNSEEN = ALL (confusion matrices), QA15, hash join, builder commit and sha256 of the builder files.
Nothing is retrained or re-inferred; the accepted fact packages are not modified.
"""
import argparse
import glob
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import REPO, WORK

sys.path.insert(0, REPO)
from metrics_core.evaluation import COMPOSITE_EPS, classification_metrics  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--task', required=True)
ap.add_argument('--model', required=True)
ap.add_argument('--seed', type=int, required=True)
ap.add_argument('--pred-glob', required=True, help='path template with {W} {V} {split} {P}')
ap.add_argument('--facts', required=True, nargs='+', help='accepted facts table(s) with the ALL rows of this unit (parquet or csv)')
ap.add_argument('--salt-files', required=True, nargs='+', help='candidate prediction-salt files; the salt of each prediction file is detected (runs of one unit can come from different packages)')
ap.add_argument('--flags', default=WORK + '/phaseB/seen_flags_{task}.parquet')
ap.add_argument('--out', required=True)
ap.add_argument('--pipelines', nargs='*')
args = ap.parse_args()

TASK = args.task
CLASSES = {'CQ': ('warning', 'average', 'good'), 'LO': ('I/D', 'G', 'E')}[TASK]
LABEL_COL = {'CQ': 'CQ_label_final', 'LO': 'LO_performance_label_3'}[TASK]
VIEW = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}[TASK]
REGIME = {'CQ': 'CQ_RAW_EARLY', 'LO': 'LO_FULL_EARLY'}[TASK]
COPY_COLS = ['parent_pipeline', 's_eff', 's_leak', 's_leak_probe_auc', 's_eff_definition_version', 's_eff_train_source', 's_eff_observed_rate', 's_eff_availability_rate', 's_leak_probe_fit_once',
             'probe_seed', 's_leak_source', 'probe_fit_scope', 'probe_fit_rows', 's_leak_probe_n_eval', 'probe_score_scope', 'probe_fit_rows_source', 'model_tier', 'variant_role', 'run_purpose']
REPORT_ONLY = {'log_loss', 'pr_auc_macro', 'top_label_ece_15', 'multiclass_nll', 'cross_entropy', 'multiclass_brier'}   # metrics whose accepted values come from an older implementation (probability clip 1e-7; older average-precision): difference reported, not an error
out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
SALTS = [(Path(f).name, Path(f).read_bytes().decode('utf-8').rstrip(chr(10))) for f in args.salt_files if Path(f).exists()]

view = pd.read_parquet(glob.glob(f'{REPO}/downloads/raw_views_20261108/{VIEW}/*.parquet')[0], columns=['window', 'split', LABEL_COL])
counts = {}
for w in ('W1', 'W2', 'W3'):
    ids = view[(view.window == w) & (view.split == 'train')][LABEL_COL].astype(str).map({c: i for i, c in enumerate(CLASSES)})
    counts[w] = np.bincount(ids.dropna().astype(int), minlength=3)
del view

parts = [pd.read_parquet(f) if f.endswith('parquet') else pd.read_csv(f) for f in args.facts]
facts = pd.concat(parts, ignore_index=True)
if 'task' in facts:
    facts = facts[facts.task == TASK]
facts = facts[(facts.model_name == args.model) & (facts.seed == args.seed)]
FACT_COLS = list(facts.columns)
LEGACY = 'f1_macro' in FACT_COLS      # facts of the first F1 runs (R4, static-v2) carry the older column names
COPY_COLS = list(dict.fromkeys(COPY_COLS + [c for c in FACT_COLS if c.startswith('probe_') or c.startswith('s_leak')] + [c for c in ('calibration_bins',) if c in FACT_COLS]))
fidx = {(r['window_id'], r['pipeline_id'], r['eval_split'], r['phase_id']): r for r in facts.to_dict('records')}
flags_all = pd.read_parquet(args.flags.format(task=TASK), columns=['window_id', 'split_name', 'phase_id', 'enrollment_id', 'seen_learner', 'seen_course', 'seen_offering'])   # only the columns needed (memory)
hash_cache = {}


def hkey(h):
    return int(h[:15], 16)        # 60-bit key of the sha256 (keeps the per-(window, split, phase) lookup small; uniqueness is checked)


def flags_for(si, w, split, phase):
    key = (si, w, split, phase)
    if key not in hash_cache:
        salt = SALTS[si][1]
        f = flags_all[(flags_all.window_id == w) & (flags_all.split_name == split) & (flags_all.phase_id == phase)]
        keys = np.fromiter((hkey(hashlib.sha256(f'{salt}|{v}'.encode()).hexdigest()) for v in f.enrollment_id.astype(str)), dtype=np.int64, count=len(f))
        if len(np.unique(keys)) != len(keys):
            raise RuntimeError(f'60-bit hash key collision in {key}')
        hash_cache[key] = pd.DataFrame({'seen_learner': f.seen_learner.to_numpy(), 'seen_course': f.seen_course.to_numpy(), 'seen_offering': f.seen_offering.to_numpy()}, index=keys)
    return hash_cache[key]


def detect_salt(prediction_hashes, w, split, phase):
    """index of the salt whose hashes of 300 sample enrollment ids of this (window, split, phase) are all in the prediction file; None if no salt matches"""
    ids = flags_all[(flags_all.window_id == w) & (flags_all.split_name == split) & (flags_all.phase_id == phase)].enrollment_id.astype(str).head(300).tolist()
    hs = set(prediction_hashes)
    for si, (_, salt) in enumerate(SALTS):
        if all(hashlib.sha256(f'{salt}|{v}'.encode()).hexdigest() in hs for v in ids):
            return si
    return None


def metric_row(y, probs, w, s_eff, s_leak):
    v = classification_metrics(y, probs, train_class_counts=counts[w], s_eff=s_eff, s_leak=s_leak)
    v['s_cal'] = max(0.0, 1.0 - float(v['ece']))
    v['s_san_plus_v2'] = float(np.prod(np.clip([v['s_nan'], v['s_maj_jsd'], v['s_cal'], v['s_drift'], v['s_eff'], v['s_leak']], COMPOSITE_EPS, 1.0)) ** (1 / 6))
    v['acctempo_m3'] = float((max(v['s_perf'], COMPOSITE_EPS) ** .6) * (max(v['s_san_plus'], COMPOSITE_EPS) ** .4))
    v['acctempo_m4'] = float((max(v['s_perf'], COMPOSITE_EPS) ** .6) * (max(v['s_san_plus_v2'], COMPOSITE_EPS) ** .4))
    return v


def legacy_cols(y, probs, vals, strict_flags, w):
    """columns of the older fact schema (accuracy, f1_weighted, per_class_*, roc_auc_macro_ovr, strict shares ...), recomputed on the rows given; only the columns the accepted ALL row carries are returned"""
    cm = np.array([list(x) for x in vals['confusion_matrix']], dtype=float)
    n = cm.sum(); d = np.diag(cm); sup = cm.sum(1); pred = cm.sum(0)
    prec = np.divide(d, pred, out=np.zeros(3), where=pred > 0)
    rec = np.divide(d, sup, out=np.zeros(3), where=sup > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros(3), where=(prec + rec) > 0)
    try:
        auc = float(roc_auc_score(y, probs, multi_class='ovr', average='macro', labels=[0, 1, 2]))
    except ValueError:
        auc = float('nan')
    ss = float(np.mean(strict_flags)) if len(strict_flags) else float('nan')
    out = {'accuracy': float(d.sum() / n), 'f1_weighted': float((f1 * sup).sum() / n), 'per_class_f1': f1, 'per_class_precision': prec, 'per_class_recall': rec, 'per_class_support': sup, 'n_rows': int(n),
           'roc_auc_macro_ovr': auc, 'top_label_ece_15': vals['ece'], 'balanced_accuracy': vals['balanced_acc'], 'cohen_kappa': vals['kappa'], 'gmean_recall': vals['gmean'], 'f1_macro': vals['macro_f1'],
           'multiclass_nll': vals['log_loss'], 'cross_entropy': vals['log_loss'], 'multiclass_brier': vals['brier'], 'strict_share': ss, 'w2_strict_share': ss if w == 'W2' else float('nan')}
    return {k: v for k, v in out.items() if k in FACT_COLS}


def git_commit():
    try:
        return subprocess.run(['git', '-C', REPO, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()[:12]
    except Exception:
        return None


rows = []
qa = {'task': TASK, 'model': args.model, 'seed': args.seed, 'runs': 0, 'files_missing': [], 'hash_unmatched': 0, 'qa15_violations': 0, 'partition_failures': [], 'all_row_mismatch': [],
      'all_row_max_abs_diff_by_column': {}, 'confusion_matrix_string_mismatch_ALL': 0, 'slice_status': {}, 'no_salt_match': [], 'salt_by_run': {}}
pipes = args.pipelines or [f'V{i}' for i in range(17)]
for w in ('W1', 'W2', 'W3'):
    hash_cache.clear()
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
                si = detect_salt(p.enrollment_id_hash, w, split, phase)
                if si is None:
                    qa['no_salt_match'].append([w, v_, split, phase]); continue
                qa['salt_by_run'].setdefault(f'{w}/{v_}', set()).add(SALTS[si][0])
                fl = flags_for(si, w, split, phase)
                pk = pd.Series(np.fromiter((hkey(h) for h in p.enrollment_id_hash), dtype=np.int64, count=len(p)))
                m = pk.map(fl.seen_learner)
                mc = pk.map(fl.seen_course)
                mo = pk.map(fl.seen_offering)
                if m.isna().any() or mc.isna().any():
                    qa['hash_unmatched'] += int(m.isna().sum()); continue
                qa['qa15_violations'] += int((mo != 0).sum())
                y = p.y_true.map({'c0': 0, 'c1': 1, 'c2': 2}).to_numpy()
                probs = p[['prob_c0', 'prob_c1', 'prob_c2']].to_numpy(float)
                s_eff, s_leak = float(fr['s_eff']), float(fr['s_leak'])
                allv = metric_row(y, probs, w, s_eff, s_leak)
                strict_all = p[f'temporal_strict_{phase}'].to_numpy(float) if f'temporal_strict_{phase}' in p else np.array([])
                if LEGACY:
                    allv.update(legacy_cols(y, probs, allv, strict_all, w))
                for c, x in allv.items():
                    if c in fr and isinstance(x, np.ndarray):
                        try:
                            d = float(np.max(np.abs(np.asarray(x, float) - np.asarray(fr[c], float))))
                        except (TypeError, ValueError):
                            continue
                        qa['all_row_max_abs_diff_by_column'][c] = max(qa['all_row_max_abs_diff_by_column'].get(c, 0.0), d)
                        if d > 1e-12 and c not in REPORT_ONLY:
                            qa['all_row_mismatch'].append([w, v_, split, phase, c, d])
                    elif c in fr and isinstance(x, (int, float, np.floating, np.integer)) and not isinstance(x, bool) and pd.notna(fr[c]):
                        try:
                            d = abs(float(x) - float(fr[c]))
                        except (TypeError, ValueError):
                            continue
                        qa['all_row_max_abs_diff_by_column'][c] = max(qa['all_row_max_abs_diff_by_column'].get(c, 0.0), d)
                        if d > 1e-12 and c not in REPORT_ONLY:
                            qa['all_row_mismatch'].append([w, v_, split, phase, c, d])
                if 'confusion_matrix' in fr and str(allv['confusion_matrix']) != str(fr['confusion_matrix']):
                    qa['confusion_matrix_string_mismatch_ALL'] += 1
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
                               'c0_support': int(support[0]), 'c1_support': int(support[1]), 'c2_support': int(support[2]),
                               'seen_rule_version': 'seen_v1_train_partition_only', 'seen_history_reference': 'TRAIN_PARTITION_ONLY'}
                        for c in COPY_COLS:           # run- and cell-level columns of the accepted ALL row
                            if c in fr:
                                row[c] = fr[c]
                        if status == 'OK':
                            vals = metric_row(yy, pp, w, s_eff, s_leak)
                            conf[(axis, val)] = np.asarray(vals['confusion_matrix'], dtype=np.int64)
                            row['confusion_matrix'] = str(vals['confusion_matrix'])
                            for k, x in vals.items():
                                if k != 'confusion_matrix' and not isinstance(x, (list, dict, np.ndarray)):
                                    row[k] = x
                            if LEGACY:
                                sl_strict = strict_all[sel] if len(strict_all) == len(sel) else np.array([])
                                for k, x in legacy_cols(yy, pp, vals, sl_strict, w).items():
                                    row[k] = x
                        else:
                            cm = np.zeros((3, 3), dtype=np.int64)
                            for t_, q_ in zip(yy, pp.argmax(axis=1) if len(yy) else []):
                                cm[t_, q_] += 1
                            conf[(axis, val)] = cm
                            row['confusion_matrix'] = None
                        qa['slice_status'][status] = qa['slice_status'].get(status, 0) + 1
                        rows.append(row)
                allcm = np.zeros((3, 3), dtype=np.int64)
                for t_, q_ in zip(y, probs.argmax(axis=1)):
                    allcm[t_, q_] += 1
                for axis in ('LEARNER', 'COURSE'):
                    if not np.array_equal(conf[(axis, 'SEEN')] + conf[(axis, 'UNSEEN')], allcm):
                        qa['partition_failures'].append([w, v_, split, phase, axis])
df = pd.DataFrame(rows)
df.to_csv(out / 'subgroup_components.csv', index=False, lineterminator='\n')
df.to_parquet(out / 'subgroup_components.parquet', index=False)
meta_cols = {'subgroup_axis', 'subgroup_value', 'slice_status', 'seen_rule_version', 'seen_history_reference'}
qa['columns_of_accepted_ALL_row_missing_in_subgroup_rows'] = sorted(c for c in FACT_COLS if c not in df.columns)
qa['rows'] = int(len(df)); qa['expected_rows'] = 3 * len(pipes) * 2 * 4 * 4
qa['two_class_cells'] = df[df.ev_n_classes_present == 2][['window_id', 'pipeline_id', 'eval_split', 'phase_id', 'subgroup_axis', 'subgroup_value', 'n_eval_samples']].drop_duplicates(['window_id', 'eval_split', 'phase_id', 'subgroup_axis', 'subgroup_value']).to_dict('records')
qa['log_loss_max_abs_diff_ALL_vs_accepted'] = qa['all_row_max_abs_diff_by_column'].get('log_loss')
qa['reported_only_max_abs_diff'] = {c: qa['all_row_max_abs_diff_by_column'].get(c) for c in sorted(REPORT_ONLY)}
bf = ['build_subgroup_facts.py', 'build_seen_flags.py', 'build_support_table.py']
qa['builder'] = {'repo_commit': git_commit(), 'sha256': {f: hashlib.sha256((Path(__file__).resolve().parent / f).read_bytes()).hexdigest() for f in bf}}
qa['salt_by_run'] = {k: sorted(v) for k, v in qa['salt_by_run'].items()}
qa['salt_families_used'] = sorted({x for v in qa['salt_by_run'].values() for x in v})
ok_ = (not qa['files_missing'] and not qa['no_salt_match'] and qa['hash_unmatched'] == 0 and qa['qa15_violations'] == 0 and not qa['partition_failures'] and not qa['all_row_mismatch'] and qa['rows'] == qa['expected_rows'])
qa['status'] = ('PASS' if not any((v or 0) > 1e-12 for v in qa['reported_only_max_abs_diff'].values()) else 'PASS_WITH_REPORTED_DIFFS') if ok_ else 'FAIL'
(out / 'summary.json').write_text(json.dumps(qa, indent=1, default=str), encoding='utf-8')
print(json.dumps({k: (v if not isinstance(v, (list, dict)) else len(v)) for k, v in qa.items()}, indent=1, default=str))
