# -*- coding: utf-8 -*-
"""QA23 (kiem toan proxy nhan) cho release CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2.
Chay tempo_fix/feature_dictionary.audit_label_proxy + qa23 tren TRAIN cua phase view local (moi window, moi phase P1-P4).
CQ: target = CQ_proximity_final (diem G cuoi); tu dien = ban sao nguyen van classify() + REVIEWED_BEHAVIOURAL_PREFIX_BASES cua
CQ/Feature_extraction/validation/audit_cq_label_proxy.py (module goc import pyspark nen khong import duoc o day).
LO: target = performance_score; proxy = 19 truong canonical cua LO proxy contract v3 (registries) va bien the _P1.._P4.
Env: TEMPO_REPO_ROOT, QA4_OUT, TEMPO_FIX, QA23_WINDOWS (mac dinh W1,W2,W3), QA23_MAXROWS (mac dinh 500000), QA23_TASKS."""
import os, re, sys, glob, json, time, hashlib, importlib.util
import numpy as np, pandas as pd, pyarrow.parquet as pq

REPO = os.environ['TEMPO_REPO_ROOT']
OUT = os.environ['QA4_OUT']
FIX = os.environ['TEMPO_FIX']
WINDOWS = os.environ.get('QA23_WINDOWS', 'W1,W2,W3').split(',')
MAXROWS = int(os.environ.get('QA23_MAXROWS', '500000'))
TASKS = os.environ.get('QA23_TASKS', 'CQ,LO').split(',')
spec = importlib.util.spec_from_file_location('feature_dictionary', f'{FIX}/feature_dictionary.py')
fd = importlib.util.module_from_spec(spec); sys.modules['feature_dictionary'] = fd; spec.loader.exec_module(fd)
RAW = f'{REPO}/downloads/raw_views_20261108'
VIEW = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}
TARGET = {'CQ': 'CQ_proximity_final', 'LO': 'performance_score'}
REGIME = {'CQ': 'CQ_RAW_EARLY', 'LO': 'LO_FULL_EARLY'}

# ===== BEGIN ban sao nguyen van tu CQ/Feature_extraction/validation/audit_cq_label_proxy.py (khong dung Spark) =====
KEY_OR_CONTEXT = {"enrollment_id", "offering_id", "user_id", "course_id", "teacher_id", "school_id", "task", "window", "split", "split_id", "scenario", "temporal_block", "phase",
                  "timeline_source", "label_availability_time", "label_availability_source", "label_rule_version", "cq_exclusion_reason", "proxy_exclusion_reason"}
LABEL_PATTERNS = (r"^cq_label_", r"^(?:coelo|afelo|acelo)_final$", r"^triad_distance_final$", r"^cq_(?:distance|proximity|score_g)(?:_[a-z0-9]+)*_final$")
PROXY_PATTERNS = ((r"(?:catalog_)?coverage$|_coverage$", "coverage_of_catalog"), (r"score_fraction|correct_ratio|watch_ratio", "ratio_of_activity_or_score"),
                  (r"video_ratio|problem_ratio", "triad_component_ratio"), (r"scaled_watch|watch_count_scaled|scaled_attempts", "triad_scaled_input"),
                  (r"^(?:coelo|afelo|acelo|triad_distance)_", "partial_triad_component"))
EARLY_COMPONENT = re.compile(r"(?:coelo|afelo|acelo|triad_distance)_partial|(?:coelo|afelo|acelo)_p[1-4]", re.I)
REVIEWED_BEHAVIOURAL_PREFIX_BASES = {"problem_count", "exercise_count", "problem_context_count", "score_sum", "correct_problem_count", "attempts_sum",
                                     "problem_catalog_coverage", "problem_score_catalog_coverage"}


def reviewed_behavioural_prefix_note(name):
    base = re.sub(r"_P[1-4]$", "", name, flags=re.I).lower()
    return "reviewed_prefix_observed_behaviour__not_label_derived" if base in REVIEWED_BEHAVIOURAL_PREFIX_BASES else None


def classify(name, data_type):
    lower = name.lower()
    if lower in KEY_OR_CONTEXT or lower.endswith("_time") or lower.endswith("_date"):
        return "KEY_OR_CONTEXT", 0, "", ""
    if lower.endswith("_observed_mask") or "_observed_mask_" in lower or lower.startswith("missing__") or lower.startswith("phase_available"):
        return "MASK", 0, "", "CQ_RAW_EARLY|CQ_REDUCED_DIRECT|CQ_EARLY_COMPONENT"
    if any(re.search(p, lower) for p in LABEL_PATTERNS):
        return "LABEL", 1, "label_or_triad_component", ""
    for pattern, reason in PROXY_PATTERNS:
        if re.search(pattern, lower):
            return "FEATURE", 1, reason, ("CQ_EARLY_COMPONENT" if EARLY_COMPONENT.search(lower) else "CQ_REDUCED_DIRECT")
    if data_type in {"boolean", "tinyint", "smallint", "int", "bigint", "float", "double"} or data_type.startswith("decimal"):
        return "FEATURE", 0, "", "CQ_RAW_EARLY"
    return "NON_NUMERIC", 0, "", ""
# ===== END =====

LO_CANON = ['performance_score', 'video_weight', 'assignment_weight', 'exam_weight', 'course_weight_total', 'watched_videos', 'video_counts', 'watch_percent',
            'video_catalog_coverage', 'assignment_problem_catalog_count', 'exam_problem_catalog_count', 'assignment_best_correct_sum', 'exam_best_correct_sum',
            'assignment_ratio_catalog', 'exam_ratio_catalog', 'problem_catalog_coverage', 'problem_score_catalog_coverage',
            'tempo_legacy_unclipped_score', 'tempo_legacy_score_clipped']   # registries LO proxy contract v3, 19 truong
LO_GRADE_GROUP = ['score_sum', 'score_mean', 'score_std', 'score_fraction_mean', 'score_fraction_std', 'correct_problem_count',
                  'incorrect_problem_count', 'correct_ratio', 'correct_ratio_std']   # nhom current-grade cua LO (registries, LOCKED 2026-10-01)
TYPES = {'int64': 'bigint', 'int32': 'int', 'int16': 'smallint', 'int8': 'tinyint', 'double': 'double', 'float': 'float', 'bool': 'boolean'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def dict_for(task, schema):
    rows = []
    for f in schema:
        n = f.name
        role, prox, rule, reg = classify(n, TYPES.get(str(f.type), str(f.type)))
        if task == 'LO':
            base = re.sub(r'_P[1-4]$', '', n)
            if base in LO_CANON:
                role, prox, rule, reg = 'FEATURE', 1, 'lo_proxy_contract_v3', 'LO_CANONICAL_PROXY'
            elif role == 'FEATURE':   # LO: moi cot so con lai thuoc LO_FULL_EARLY, khong dung pattern CQ
                prox, rule, reg = 0, '', 'LO_FULL_EARLY'
        note = reviewed_behavioural_prefix_note(n) if task == 'CQ' else None
        rows.append(dict(column_name=n, role=role, is_label_proxy=prox, proxy_rule=rule, regimes_included=reg, proxy_review_note=note or ''))
    return pd.DataFrame(rows)


def visible(col, k):
    m = re.search(r'_P([1-4])$', col)
    return m is None or int(m.group(1)) <= k


def main():
    res_audit, res_sum, inputs = [], [], []
    for task in TASKS:
        vf = glob.glob(f'{RAW}/{VIEW[task]}/*.parquet'); assert len(vf) == 1
        inputs.append((f'phase_view[{task}]', vf[0].replace(REPO + '/', ''), sha(vf[0])))
        dic = dict_for(task, pq.ParquetFile(vf[0]).schema_arrow)
        key = pq.read_table(vf[0], columns=['window', 'split', TARGET[task]]).to_pandas()
        for w in WINDOWS:
            idx = np.flatnonzero(((key.window == w) & (key.split == 'train') & key[TARGET[task]].notna()).to_numpy())
            n_all = len(idx)
            if n_all > MAXROWS:
                idx = np.sort(np.random.default_rng(0).choice(idx, MAXROWS, replace=False))
            y = key[TARGET[task]].to_numpy(dtype=float)[idx]
            for k in (1, 2, 3, 4):
                ph = f'P{k}'; t0 = time.time()
                dv = dic[dic.column_name.map(lambda c: visible(c, k))]
                feats = [c for c, r in zip(dv.column_name, dv.role) if r == 'FEATURE' and c != TARGET[task]]
                parts = []
                for c in feats:
                    x = pq.read_table(vf[0], columns=[c]).column(0).to_numpy(zero_copy_only=False)[idx]
                    parts.append(fd.audit_label_proxy(pd.DataFrame({c: x, '_y': y}), [c], '_y', dictionary=dic, max_rows=10 ** 9))
                aud = pd.concat(parts, ignore_index=True)
                # qa23 cua repo tren tu dien gioi han o cot nhin thay duoc o phase nay
                dvis = dv[dv.role == 'FEATURE'].copy()
                pred = fd.imputer_predictor_columns(dvis.assign(role='FEATURE'), REGIME[task])
                ok, info = fd.qa23(aud, dvis, REGIME[task], imputer_predictors=pred)
                note = dict(zip(dic.column_name, dic.proxy_review_note))
                aud.insert(0, 'task', task); aud.insert(1, 'window_id', w); aud.insert(2, 'phase_id', ph)
                aud['proxy_review_note'] = aud.column_name.map(note)
                aud['reviewed_base_cq'] = aud.column_name.map(lambda n: re.sub(r'_P[1-4]$', '', n) in REVIEWED_BEHAVIOURAL_PREFIX_BASES) if task == 'CQ' else False
                aud['lo_grade_group'] = aud.column_name.map(lambda n: re.sub(r'_P[1-4]$', '', n) in LO_GRADE_GROUP) if task == 'LO' else False
                res_sum.append(dict(task=task, window_id=w, phase_id=ph, qa23_ok=bool(ok), n_train_rows_available=int(n_all), n_train_rows_used=int(len(idx)),
                                    n_features_audited=int(len(aud)), n_predictors_regime=len(pred), n_flagged_by_rule=int(aud.flagged_by_rule.sum()),
                                    n_needs_review=int(aud.needs_review.sum()), n_unreviewed=len(info['unreviewed']), unreviewed=';'.join(info['unreviewed']),
                                    n_missing_from_audit=len(info['missing_from_audit']), proxy_in_imputer_predictors=len(info['proxy_in_imputer_predictors']),
                                    max_abs_rho=float(aud.spearman_abs.max()), max_nmi=float(aud.nmi.max()), seconds=round(time.time() - t0, 1)))
                res_audit.append(aud); print(res_sum[-1], flush=True)
    pd.concat(res_audit, ignore_index=True).to_csv(f'{OUT}/qa23_audit_by_feature.csv', index=False)
    pd.DataFrame(res_sum).to_csv(f'{OUT}/qa23_summary_by_phase.csv', index=False)
    pd.DataFrame(inputs, columns=['input', 'path_relative_to_repo', 'sha256']).to_csv(f'{OUT}/qa23_inputs_sha256.csv', index=False)


if __name__ == '__main__':
    main()
