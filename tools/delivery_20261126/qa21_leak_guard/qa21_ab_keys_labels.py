# -*- coding: utf-8 -*-
"""QA21 phan 1 (TRAIN: khoa khong trung giua partition) va phan 2 (nhan TRAIN khong kha dung sau tau_w - embargo).
Env: TEMPO_REPO_ROOT, QA21_OUT. Chay: python -I qa21_ab_keys_labels.py"""
import os, glob, hashlib, itertools
import numpy as np, pandas as pd, pyarrow.parquet as pq
REPO = os.environ['TEMPO_REPO_ROOT']; OUT = os.environ['QA21_OUT']
RAW = f'{REPO}/downloads/raw_views_20261108'
MAIN = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}
TESTD = {'CQ': 'CQ_test', 'LO': 'LO_test'}
REG = {'CQ': f'{REPO}/CQ/resuilt/m07_split_evidence_received_20261107/split_registry.csv',
       'LO': f'{REPO}/LO/resuilt/lo_split_evidence_20261106/split_registry_source.csv'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def hs(s):  # hash 64 bit cua id; noi goi kiem tra va cham
    return pd.util.hash_pandas_object(s, index=False).to_numpy()


COLS = ['enrollment_id', 'window', 'split', 'offering_id', 'timeline_source', 'user_id', 'course_id', 'window_end_exclusive']
ROLE = {'train': 'TRAIN', 'validation': 'VALIDATION', 'test': 'TEST'}
inputs, keyrows, infrows, labrows, testcons = [], [], [], [], []
for task in ['CQ', 'LO']:
    mf = glob.glob(f'{RAW}/{MAIN[task]}/*.parquet'); assert len(mf) == 1
    inputs.append((f'{task} TRAIN+VALIDATION', mf[0].replace(REPO + '/', ''), sha(mf[0]), pq.ParquetFile(mf[0]).metadata.num_rows))
    main = pq.read_table(mf[0], columns=COLS).to_pandas()
    tests = {}
    for P in ['P1', 'P2', 'P3', 'P4']:
        tf = glob.glob(f'{RAW}/{TESTD[task]}/{P}/*.parquet'); assert len(tf) == 1
        inputs.append((f'{task} TEST {P}', tf[0].replace(REPO + '/', ''), sha(tf[0]), pq.ParquetFile(tf[0]).metadata.num_rows))
        tests[P] = pq.read_table(tf[0], columns=COLS).to_pandas()
    for w in sorted(tests['P4'].window.unique()):
        ref = set(tests['P4'].loc[tests['P4'].window == w, 'enrollment_id'])
        for P in ['P1', 'P2', 'P3']:
            cur = set(tests[P].loc[tests[P].window == w, 'enrollment_id'])
            testcons.append(dict(task=task, window=w, phase=P, n_P4=len(ref), n_phase=len(cur), same_set_as_P4=(ref == cur)))
    v = pd.concat([main, tests['P4']], ignore_index=True)
    assert set(v.split.unique()) == set(ROLE), v.split.unique()
    v['role'] = v.split.map(ROLE)
    reg = pd.read_csv(REG[task]).set_index('window_id')
    for w in sorted(v.window.unique()):
        vw = v[v.window == w]
        S = {}
        for key in ['enrollment_id', 'offering_id', 'user_id', 'course_id']:
            S[key] = {}
            for r in ROLE.values():
                x = vw.loc[vw.role == r, key].dropna().astype(str)
                u = x.drop_duplicates(); h = hs(u)
                assert len(np.unique(h)) == len(u), 'va cham hash'
                S[key][r] = (h, len(x), len(u))
            for a, b in itertools.combinations(['TRAIN', 'VALIDATION', 'TEST'], 2):
                ov = len(np.intersect1d(S[key][a][0], S[key][b][0]))
                row = dict(task=task, window=w, key=key, pair=f'{a} vs {b}', n_rows_a=S[key][a][1], n_distinct_a=S[key][a][2],
                           n_rows_b=S[key][b][1], n_distinct_b=S[key][b][2], n_overlap=ov,
                           share_of_smaller=round(ov / max(1, min(S[key][a][2], S[key][b][2])), 6))
                if key in ('enrollment_id', 'offering_id'):
                    row['role_of_key'] = 'registered key (SPLIT_REGISTRY.unit = offering_id x timeline_source; an enrollment belongs to exactly one block)'
                    row['result'] = 'PASS' if ov == 0 else 'FAIL'
                else:
                    row['role_of_key'] = 'information only (split by offering; shared learners/courses expected)'
                    row['result'] = 'INFO'
                keyrows.append(row)
        vw2 = vw.assign(unit=vw.offering_id.astype(str) + '|' + vw.timeline_source.astype(str))
        per_unit = vw2.groupby('unit').role.nunique()
        per_off = vw2.groupby('offering_id').role.nunique()
        per_enr = vw2.groupby('enrollment_id').role.nunique()
        infrows.append(dict(task=task, window=w, n_rows=len(vw2), n_enrollments=vw2.enrollment_id.nunique(),
                            dup_enrollment_rows_in_window=int(vw2.enrollment_id.duplicated().sum()),
                            n_units=len(per_unit), n_units_in_more_than_one_partition=int((per_unit > 1).sum()),
                            n_offerings=len(per_off), n_offerings_in_more_than_one_partition=int((per_off > 1).sum()),
                            n_enrollments_in_more_than_one_partition=int((per_enr > 1).sum())))
        # ---- phan 2 ----
        r = reg.loc[w]; tau = pd.Timestamp(r['tau_w']); emb = int(r['embargo_gap_days'])
        label_end = vw.window_end_exclusive - pd.Timedelta(days=1)  # window_end_exclusive = offering_end_date + 1 ngay
        lim = tau - pd.Timedelta(days=emb)
        minend = pd.Timestamp(r['min_evaluation_end_utc'])
        for role in ['TRAIN', 'VALIDATION', 'TEST']:
            m = (vw.role == role).to_numpy(); le = label_end[m]
            e = dict(task=task, window=w, role=role, n_enrollments=int(m.sum()), n_offerings=int(vw.loc[m, 'offering_id'].nunique()),
                     label_end_min=str(le.min().date()), label_end_max=str(le.max().date()),
                     registry_tau_w=str(tau.date()), registered_embargo_gap_days=emb, limit_date=str(lim.date()),
                     registry_min_evaluation_end_utc=str(minend.date()))
            if role == 'TRAIN':
                e['n_labels_after_limit'] = int((le > lim).sum())
                e['max_train_end_equals_registry_tau'] = bool(le.max() == tau)
                e['result'] = 'PASS' if e['n_labels_after_limit'] == 0 else 'FAIL'
            else:
                e['n_labels_after_limit'] = int((le < tau).sum())  # nhan eval ket thuc truoc tau (dieu kien QA22 bi vi pham neu > 0)
                e['max_train_end_equals_registry_tau'] = ''
                e['result'] = 'INFO' if e['n_labels_after_limit'] == 0 else 'CHECK'
            labrows.append(e)
pd.DataFrame(keyrows).to_csv(f'{OUT}/qa21_a_key_overlap_by_window.csv', index=False)
pd.DataFrame(infrows).to_csv(f'{OUT}/qa21_a_partition_unit_check.csv', index=False)
pd.DataFrame(testcons).to_csv(f'{OUT}/qa21_a_test_phase_consistency.csv', index=False)
pd.DataFrame(labrows).to_csv(f'{OUT}/qa21_b_train_label_end_vs_tau.csv', index=False)
pd.DataFrame(inputs, columns=['input', 'path_relative_to_repo', 'sha256', 'n_rows']).to_csv(f'{OUT}/qa21_inputs_sha256.csv', index=False)
for f in ['qa21_a_key_overlap_by_window', 'qa21_a_partition_unit_check', 'qa21_a_test_phase_consistency', 'qa21_b_train_label_end_vs_tau']:
    print(f); print(pd.read_csv(f'{OUT}/{f}.csv').drop(columns=['role_of_key'], errors='ignore').to_string())
