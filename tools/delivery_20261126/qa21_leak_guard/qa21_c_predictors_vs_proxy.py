# -*- coding: utf-8 -*-
"""QA21 phan 5: imputer_predictors cua cac trang thai S1 (V9 extra_trees, V13 mice) co ten cot is_label_proxy = 1 hay khong.
Dau vao: c_out/<TASK>_<W>_<V>.json (do qa21_c_safe_inspect_joblib.py ghi: danh sach cot cua IterativeImputer, khong thuc thi ma)
         drive_dl/<...>/train_tail.bin (duoi parquet model_inputs/train.parquet: doi chieu ten cot)
         manifest S1 (qa5m/src) cho imputer_params cua V0/V1/V5.
Env: QA21_OUT, QA5M_SRC."""
import os, re, io, json, glob, struct, hashlib
import pyarrow as pa, pyarrow.parquet as pq

OUT = os.environ['QA21_OUT']; SRC = os.environ['QA5M_SRC']
FULL = {}  # kich thuoc train.parquet tu fetch.log
for line in open(f'{OUT}/drive_dl/fetch.log', encoding='utf-8'):
    m = re.match(r'(\w+) (W\d) (V\d+) \S+ size=(\d+) offset=(\d+)', line)
    if m: FULL[(m[1], m[2], m[3])] = int(m[4])

# ---- cac quy tac (sao nguyen, ghi nguon) ----
# LO: LO/registries.py LO_PROXY_CONTRACT['canonical_fields'] (19 ten)
LO_CANON = ['performance_score', 'video_weight', 'assignment_weight', 'exam_weight', 'course_weight_total', 'watched_videos', 'video_counts', 'watch_percent',
            'video_catalog_coverage', 'assignment_problem_catalog_count', 'exam_problem_catalog_count', 'assignment_best_correct_sum', 'exam_best_correct_sum',
            'assignment_ratio_catalog', 'exam_ratio_catalog', 'problem_catalog_coverage', 'problem_score_catalog_coverage',
            'tempo_legacy_unclipped_score', 'tempo_legacy_score_clipped']
# imputation_core/wide_imputation.py LO_LABEL_PROXY_COLUMNS (danh sach ma imputer thuc su loai tru, khop ten chinh xac)
LO_WIDE = ['label_threshold_set', 'video_weight', 'assignment_weight', 'exam_weight', 'course_weight_total', 'watched_videos', 'video_counts', 'watch_percent',
           'assignment_problem_catalog_count', 'exam_problem_catalog_count', 'assignment_best_correct_sum', 'exam_best_correct_sum',
           'assignment_problem_attempted_count', 'exam_problem_attempted_count', 'assignment_ratio_catalog', 'exam_ratio_catalog',
           'tempo_legacy_unclipped_score', 'tempo_legacy_score_clipped', 'assignment_ratio_used', 'total_correct_ratio_assignment', 'total_correct_ratio_exam',
           'average_correct_ratio_assignment', 'average_correct_ratio_exam', 'exam_attempt_count', 'assignment_attempt_count',
           'video_catalog_coverage', 'problem_catalog_coverage', 'problem_score_catalog_coverage']
# CQ: CQ/Feature_extraction/validation/audit_cq_label_proxy.py PROXY_PATTERNS (qua ban sao trong qa4/qa23.py)
CQ_AUDIT_PATTERNS = ((r"(?:catalog_)?coverage$|_coverage$"), (r"score_fraction|correct_ratio|watch_ratio"), (r"video_ratio|problem_ratio"),
                     (r"scaled_watch|watch_count_scaled|scaled_attempts"), (r"^(?:coelo|afelo|acelo|triad_distance)_"))
# CQ: imputation_core/wide_imputation.py CQ_LABEL_PROXY_RE (loai tru that su trong imputer)
CQ_WIDE_RE = re.compile(r"(?:^cq_label_|^(?:coelo|afelo|acelo|triad_distance)_|^cq_(?:distance|proximity|score_g)|(?:catalog_)?coverage$|_coverage$|score_fraction|correct_ratio|watch_ratio|"
                        r"video_ratio|problem_ratio|scaled_watch|watch_count_scaled|scaled_attempts)", re.I)
# CQ: tempo_fix/feature_dictionary.py PROXY_PATTERNS
CQ_TEMPO_PATTERNS = (r'catalog_coverage$', r'_coverage$', r'^score_fraction', r'^correct_ratio$', r'watch_ratio', r'video_ratio|problem_ratio',
                     r'^(coelo|afelo|acelo)', r'triad_distance|cq_proximity|cq_score_g', r'^aef($|_)', r'scaled_watch|watch_count_scaled|scaled_attempts')
# quyet dinh 21 (registries.py, id 21): 8 co so duoc mien co proxy ("prefix observed behaviour")
CQ_EXEMPT_8 = {'problem_count', 'exercise_count', 'problem_context_count', 'score_sum', 'correct_problem_count', 'attempts_sum',
               'problem_catalog_coverage', 'problem_score_catalog_coverage'}
SUF = re.compile(r'_P[1-4]$')
strip = lambda n: SUF.sub('', n)


def any_re(name, pats): return any(re.search(p, name.lower()) for p in pats)


def tail_names(state_dir, key):
    tail = open(f'{state_dir}/train_tail.bin', 'rb').read(); full = FULL[key]; off = full - len(tail)
    assert tail[-4:] == b'PAR1'

    class F(io.RawIOBase):
        def __init__(s): s.p = 0
        def seekable(s): return True
        def readable(s): return True
        def tell(s): return s.p
        def seek(s, o, w=0):
            s.p = o if w == 0 else (s.p + o if w == 1 else full + o); return s.p
        def readinto(s, b):
            n = len(b); st = s.p - off; assert st >= 0
            b[:n] = tail[st:st + n].ljust(n, b'\0'); s.p += n; return n
    return set(pq.ParquetFile(pa.PythonFile(F(), mode='r')).schema_arrow.names)


import pandas as pd
states, longrows = [], []
for task in ['CQ', 'LO']:
    for w in ['W1', 'W2', 'W3']:
        for v in ['V9', 'V13']:
            js = f'{OUT}/c_out/{task}_{w}_{v}.json'
            if not os.path.exists(js): continue
            d = json.load(open(js, encoding='utf-8'))
            I = {i['path']: i for i in d['items']}
            summ = {i['path']: i for i in d['items'] if i['kind'] == 'summary'}
            dyn = summ['dynamic_imputer']['feature_names_in_']; sta = summ['static_imputer']['feature_names_in_']
            assert sorted(dyn) == sorted(I['root.dynamic_active_columns']['values']) and sorted(sta) == sorted(I['root.static_active_columns']['values'])
            assert summ['dynamic_imputer']['neighbor_len_min'] == summ['dynamic_imputer']['neighbor_len_max'] == len(dyn) - 1
            assert summ['static_imputer']['neighbor_len_min'] == summ['static_imputer']['neighbor_len_max'] == len(sta) - 1
            jf = f'{OUT}/drive_dl/{task}_{w}_{v}/fitted_pipeline.joblib'
            hh = hashlib.sha256()
            with open(jf, 'rb') as fh:
                for blk in iter(lambda: fh.read(1 << 22), b''): hh.update(blk)
            drive_sha = json.load(open(f'{OUT}/drive_dl/{task}_{w}_{v}/sha256.json'))['fitted_pipeline.joblib'].split(':')[1]
            mfs = json.load(open(glob.glob(f'{SRC}/S1_{task}/{w}/{v}/*/run_manifest.json')[0], encoding='utf-8'))
            names = tail_names(f'{OUT}/drive_dl/{task}_{w}_{v}', (task, w, v))
            src_dyn = [f'{b}_P{k}' for b in dyn for k in (1, 2, 3, 4)]
            in_schema = sum(1 for c in src_dyn if c in names) + sum(1 for c in sta if c in names)
            src = src_dyn + list(sta)
            bases = list(dyn) + list(sta)  # ten co so (khong hau to) cua moi predictor
            st = dict(task=task, window=w, pipeline=v, imputer='MICE (BayesianRidge)' if v == 'V13' else 'ExtraTrees (IterativeImputer)',
                      n_dynamic_predictors_base=len(dyn), n_static_predictors=len(sta), n_source_columns_with_phase_suffix=len(src),
                      n_source_columns_found_in_train_model_input_schema=in_schema,
                      joblib_sha256=hh.hexdigest(), joblib_sha256_equals_drive_sha256_json=(hh.hexdigest() == drive_sha), joblib_sha256_equals_manifest_preprocessor_sha256=(mfs['preprocessor_sha256'].split(':')[1] == hh.hexdigest()), s1_attempt_id=mfs['attempt_id'],
                      each_target_regressed_on_all_other_columns=True,
                      predictor_list_sha256=hashlib.sha256('\n'.join(sorted(bases)).encode()).hexdigest())
            if task == 'LO':
                A = [c for c in src if c in LO_CANON]            # doc A: ten chinh xac, cot nguon co hau to (nhu code loai tru da ap dung)
                Bn = sorted({b for b in bases if b in LO_CANON})  # doc B: bo hau to _P1.._P4, khop 19 ten hop dong
                Cn = sorted({b for b in bases if b in LO_WIDE})   # doc C: bo hau to, khop danh sach 28 ten cua wide_imputation
                st.update(reading_A_exact_names_suffixed_source_columns=len(A), reading_A_names=';'.join(A),
                          reading_B_phase_suffix_stripped_contract19=len(Bn), reading_B_names=';'.join(Bn),
                          reading_C_phase_suffix_stripped_wide_imputation_list28=len(Cn), reading_C_names=';'.join(Cn))
            else:
                a1 = [c for c in src if any_re(c, CQ_AUDIT_PATTERNS)]                       # quy tac audit_cq_label_proxy, ten co hau to
                a2 = sorted({b for b in bases if any_re(b, CQ_AUDIT_PATTERNS)})              # bo hau to
                a3 = sorted(b for b in a2 if b not in CQ_EXEMPT_8)                           # bo hau to, tru 8 co so quyet dinh 21
                t1 = [c for c in src if any_re(c, CQ_TEMPO_PATTERNS)]                        # tempo_fix.feature_dictionary, ten co hau to
                t2 = sorted({b for b in bases if any_re(b, CQ_TEMPO_PATTERNS)})
                t3 = sorted(b for b in t2 if b not in CQ_EXEMPT_8)
                w1 = [c for c in src if CQ_WIDE_RE.search(c)]                                # regex that su trong imputer, ten co hau to
                st.update(rule_audit_suffixed_source_columns=len(a1), rule_audit_suffixed_names=';'.join(a1),
                          rule_audit_phase_suffix_stripped=len(a2), rule_audit_stripped_names=';'.join(a2),
                          rule_audit_stripped_minus_decision21_exempt8=len(a3), rule_audit_stripped_minus_exempt_names=';'.join(a3),
                          rule_tempo_fix_suffixed_source_columns=len(t1), rule_tempo_fix_phase_suffix_stripped=len(t2), rule_tempo_fix_stripped_names=';'.join(t2),
                          rule_tempo_fix_stripped_minus_decision21_exempt8=len(t3), rule_tempo_fix_stripped_minus_exempt_names=';'.join(t3),
                          rule_wide_imputation_regex_suffixed_source_columns=len(w1))
            states.append(st)
            for side, lst in (('dynamic_base', dyn), ('static', sta)):
                for b in lst:
                    r = dict(task=task, window=w, pipeline=v, side=side, predictor=b,
                             decision21_exempt_base=(b in CQ_EXEMPT_8) if task == 'CQ' else '')
                    if task == 'LO':
                        r.update(contract19_exact=(b in LO_CANON), wide_list28=(b in LO_WIDE))
                    else:
                        r.update(rule_audit_stripped=any_re(b, CQ_AUDIT_PATTERNS), rule_tempo_fix_stripped=any_re(b, CQ_TEMPO_PATTERNS))
                    longrows.append(r)
S = pd.DataFrame(states)
S.to_csv(f'{OUT}/qa21_c_imputer_predictors_by_state.csv', index=False)
pd.DataFrame(longrows).to_csv(f'{OUT}/qa21_c_predictor_list_long.csv', index=False)

# ---- bang 30 trang thai S1: loai imputer + co predictor khong ----
rows = []
for task in ['CQ', 'LO']:
    for w in ['W1', 'W2', 'W3']:
        for v in ['V0', 'V1', 'V5', 'V9', 'V13']:
            mf = glob.glob(f'{SRC}/S1_{task}/{w}/{v}/*/run_manifest.json')[0]
            m = json.load(open(mf, encoding='utf-8'))
            p = m.get('imputer_params', {})
            has = v in ('V9', 'V13')
            rows.append(dict(task=task, window=w, pipeline=v, variant=m.get('variant'), feature_regime=m.get('feature_regime'),
                             imputer_params_summary=(p.get('estimator') or p.get('strategy') or p.get('imputer') or ''),
                             uses_other_columns_as_predictors=has,
                             predictor_source=('fitted_pipeline.joblib (IterativeImputer.feature_names_in_; doc khong thuc thi ma)' if has else 'khong co: thong ke theo tung cot (median/mean) hoac hang so 0 (V0); theo imputer_params cua run_manifest.json va wide_imputation.py'),
                             n_predictors=(int(S[(S.task == task) & (S.window == w) & (S.pipeline == v)][['n_dynamic_predictors_base', 'n_static_predictors']].sum(axis=1).iloc[0]) if has and len(S[(S.task == task) & (S.window == w) & (S.pipeline == v)]) else (None if has else 0))))
pd.DataFrame(rows).to_csv(f'{OUT}/qa21_c_s1_states_overview.csv', index=False)

# ---- tong hop theo task ----
agg = []
for task in ['CQ', 'LO']:
    s = S[S.task == task]
    if not len(s): continue
    r = dict(task=task, n_states_with_predictors_read=len(s), n_states_total_S1=15)
    cols = [c for c in s.columns if re.match(r'(reading_|rule_)', c) and not c.endswith('names') and s[c].notna().any()]
    for c in cols:
        r[f'{c}__n_states_with_proxy'] = int((s[c] > 0).sum()); r[f'{c}__min'] = int(s[c].min()); r[f'{c}__max'] = int(s[c].max())
    agg.append(r)
pd.DataFrame(agg).to_csv(f'{OUT}/qa21_c_summary_by_task.csv', index=False)
print(S.drop(columns=[c for c in S.columns if c.endswith('names') or c == 'predictor_list_sha256' or c == 'joblib_sha256']).T.to_string())
