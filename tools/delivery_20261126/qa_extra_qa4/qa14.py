# -*- coding: utf-8 -*-
"""QA14: tim ket qua 6 sanity test (Kich ban 3.5 = phase-builder: prefix nesting, label identity, split identity, future perturbation,
cutoff equality, cardinality) gan voi release; ghi lai noi da tim + chay cac kiem tra cau truc re tren phase view local.
Cac kiem tra o day KHONG phai 6 test (3 test can su kien tho / chay lai phase builder); chi la bang chung bo sung.
Env: TEMPO_REPO_ROOT, QA4_OUT."""
import os, glob, json, re
import numpy as np, pandas as pd, pyarrow.parquet as pq

REPO = os.environ['TEMPO_REPO_ROOT']
OUT = os.environ['QA4_OUT']
REL = f'{REPO}/CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2'
RAW = f'{REPO}/downloads/raw_views_20261108'
VIEW = {'CQ': ('CQ/phase_views_v2_2', 'CQ_test', 'CQ_label_final'), 'LO': ('LO/phase_views_v3_1_scored_signal_excluded', 'LO_test', 'LO_performance_label_3')}
rows = []


def add(test, scope, n, n_bad, note):
    rows.append(dict(item=test, scope=scope, n_checked=int(n), n_violations=int(n_bad), result='PASS' if n_bad == 0 else 'FAIL', note=note))


# ---- 1) tim kiem ket qua 6 test gan voi release (manifest) ----
man = json.load(open(f'{REL}/meta_release_manifest.json', encoding='utf-8'))
txt = json.dumps(man).lower()
add('search: release manifest chua ket qua 6 sanity test', 'meta_release_manifest.json', 1, 0 if any(k in txt for k in ('sanity_tests', 'prefix_nesting', 'future_perturbation', 'cutoff_equality')) else 1,
    'khoa nhu sanity_tests / prefix_nesting / future_perturbation / cutoff_equality khong co; chi co duong dan sanity_components.csv (thanh phan diem S_san+, khong phai 6 test)')
cols = [c for c in pq.ParquetFile(f'{REL}/meta_dataset_seed_level.parquet').schema.names if re.search(r'sanity_test|qa_sanity', c)]
add('search: cot qa_sanity_tests_ok trong bang release', 'meta_dataset_seed_level', 1, 0 if cols else 1, f'cot tim thay: {cols}')
rm = glob.glob(f'{REPO}/CQ/resuilt/cq_patchtst_v3_seed42_20261101/checkpoint_download/CQ/W1/V3/PATCHTST/seed=42/run_manifest.json')
keys = [k for k in json.load(open(rm[0])) if re.search(r'sanity|pre_run|check', k, re.I)] if rm else []
add('search: run_manifest (mau PatchTST seed 42) co khoa sanity/pre_run/check', 'run_manifest.json', 1, 0 if keys else 1, f'khoa tim thay: {keys}')

# ---- 2) kiem tra cau truc re tren phase view (khong phai 6 test) ----
for task, (vdir, tdir, lab) in VIEW.items():
    vf = glob.glob(f'{RAW}/{vdir}/*.parquet')[0]
    cut = [f'cutoff_time_P{k}' for k in range(1, 5)]
    v = pq.read_table(vf, columns=['enrollment_id', 'window', 'split'] + cut).to_pandas()
    tf = {k: pq.read_table(glob.glob(f'{RAW}/{tdir}/P{k}/*.parquet')[0], columns=['enrollment_id', 'window', 'split'] + cut).to_pandas() for k in range(1, 5)}
    t = tf[4]
    allv = pd.concat([v, t], ignore_index=True)
    for c in cut:
        allv[c] = pd.to_datetime(allv[c])
    # cardinality: moi (window, enrollment) dung 1 dong; moi enrollment co du 4 moc cutoff (neu phase kha dung)
    dup = allv.duplicated(['window', 'enrollment_id']).sum()
    add('cardinality (mot dong/enrollment/window, view rong 4 phase)', f'{task} view TRAIN+VALIDATION+TEST(P4)', len(allv), dup, 'thay the mot phan test 6; khong kiem so view/enrollment cua LO risk-set')
    # split identity: mot enrollment thuoc dung mot partition trong moi window
    nsp = allv.groupby(['window', 'enrollment_id']).split.nunique()
    add('split identity (enrollment trong dung 1 partition/window)', f'{task}', len(nsp), int((nsp > 1).sum()), 'tren cac window; khong kiem cac prefix P1-P4 cua view TEST: xem dong sau')
    # test P1..P4 cung tap enrollment
    base = set(zip(tf[1].window, tf[1].enrollment_id))
    bad = sum(len(base ^ set(zip(tf[k].window, tf[k].enrollment_id))) for k in (2, 3, 4))
    add('split identity (TEST P1..P4 cung tap enrollment)', f'{task}_test', len(base), bad, 'so enrollment khac nhau giua P1 va P2/P3/P4')
    # cutoff don dieu P1<=P2<=P3<=P4 (muc moc thoi gian; khong phai prefix nesting cua su kien)
    cc = allv[cut].dropna()
    mono = ((cc.cutoff_time_P1 <= cc.cutoff_time_P2) & (cc.cutoff_time_P2 <= cc.cutoff_time_P3) & (cc.cutoff_time_P3 <= cc.cutoff_time_P4))
    add('cutoff don dieu P1<=P2<=P3<=P4 (moc thoi gian)', f'{task}', len(cc), int((~mono).sum()), 'chi la moc cutoff; prefix nesting cua su kien can du lieu su kien tho')
    # label identity: nhan duy nhat/enrollment (view rong -> cot nhan mot gia tri; kiem enrollment_id lap voi nhan khac nhau giua cac window)
    lv = pq.read_table(vf, columns=['enrollment_id', lab]).to_pandas()
    g = lv.dropna().groupby('enrollment_id')[lab].nunique()
    add('label identity (1 nhan/enrollment qua cac window cua view TRAIN+VALIDATION)', f'{task} cot {lab}', len(g), int((g > 1).sum()), 'khong gom TEST (view TEST khong doc o day)')
for r in rows:
    if r['item'].startswith('search'):
        r['result'] = 'NOT_FOUND' if r['n_violations'] else 'FOUND'
pd.DataFrame(rows).to_csv(f'{OUT}/qa14_evidence.csv', index=False, encoding='utf-8')
print(pd.DataFrame(rows).drop(columns='note').to_string())
