# -*- coding: utf-8 -*-
"""QA22 cho release CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2: tempo_fix/split_v2.qa22 chay tren
(A) bang split registry da luu (CQ V2.2, LO V3.1) va (B) tinh lai tu phase view local (TRAIN/VALIDATION/TEST cua tung window).
Env: TEMPO_REPO_ROOT, QA4_OUT, TEMPO_FIX (thu muc tempo_fix cua ban giao)."""
import os, sys, glob, json, hashlib, importlib.util
import numpy as np, pandas as pd
REPO = os.environ['TEMPO_REPO_ROOT']
OUT = os.environ['QA4_OUT']
FIX = os.environ['TEMPO_FIX']
spec = importlib.util.spec_from_file_location('split_v2', f'{FIX}/split_v2.py'); sv = importlib.util.module_from_spec(spec); sys.modules['split_v2'] = sv; spec.loader.exec_module(sv)
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): h.update(b)
    return h.hexdigest()
RAW = f'{REPO}/downloads/raw_views_20261108'
REG = {'CQ': f'{REPO}/CQ/resuilt/m07_split_evidence_received_20261107/split_registry.csv',
       'LO': f'{REPO}/LO/resuilt/lo_split_evidence_20261106/split_registry_source.csv'}
VIEW = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}
TEST = {'CQ': 'CQ_test/P4', 'LO': 'LO_test/P4'}
COLS = ['enrollment_id', 'window', 'split', 'offering_id', 'cutoff_time_P4', 'window_end_exclusive']
ROLE = {'train': 'TRAIN', 'validation': 'VALIDATION', 'test': 'TEST'}
inputs, A_rows, B_rows, B_detail = [], [], [], []
for task in ['CQ', 'LO']:
    # ---- (A) registry da luu ----
    reg = pd.read_csv(REG[task]); inputs.append((f'split_registry[{task}]', REG[task].replace(REPO + '/', ''), sha(REG[task])))
    a = reg.copy()
    a['n_enrollments_val'] = a['n_enrollments_validation']
    a['end_order_ok_recomputed'] = pd.to_datetime(a['tau_w']) <= pd.to_datetime(a['min_evaluation_end_utc'])
    assert (a['end_order_ok_recomputed'] == a['end_order_ok']).all(), 'co dau end_order_ok khac gia tri tinh lai tu tau_w <= min_evaluation_end_utc'
    ok, t = sv.qa22(a)
    for r in t.itertuples():
        A_rows.append(dict(task=task, source='split_registry (luu san)', window_id=r.window_id, tau_w=r.tau_w, min_eval_end=r.min_evaluation_end_utc,
                           end_order_ok=bool(r.end_order_ok), n_val=int(r.n_enrollments_val), n_test=int(r.n_enrollments_test), qa22_ok=bool(r.qa22_ok), split_version=r.split_version))
    # ---- (B) tinh lai tu view ----
    vf = glob.glob(f'{RAW}/{VIEW[task]}/*.parquet'); tf = glob.glob(f'{RAW}/{TEST[task]}/*.parquet')
    assert len(vf) == 1 and len(tf) == 1
    inputs += [(f'phase_view[{task}] TRAIN+VALIDATION', vf[0].replace(REPO + '/', ''), sha(vf[0])), (f'phase_view[{task}] TEST P4', tf[0].replace(REPO + '/', ''), sha(tf[0]))]
    v = pd.concat([pd.read_parquet(vf[0], columns=COLS), pd.read_parquet(tf[0], columns=COLS)], ignore_index=True)
    v = v[v.split.isin(ROLE)]
    et = pd.to_datetime(v.enrollment_id.str.split('::').str[2])
    # REPORT: P4 = 0.90 cua doan [enroll, ket thuc]; lam tron phut (nhieu float ~1 s); khop window_end_exclusive (moc cuoi, loai tru)
    v['offering_end_date'] = (et + (pd.to_datetime(v.cutoff_time_P4) - et) / 0.90).dt.round('min')
    v['offering_start_date'] = et
    for w in sorted(v.window.unique()):
        vw = v[v.window == w]
        # an toan: TRAIN lay moc cuoi lon nhat cua offering, VALIDATION/TEST lay moc nho nhat (co offering mang 2 moc cuoi khac nhau)
        g = vw.groupby(['split', 'offering_id']).agg(offering_start_date=('offering_start_date', 'min'), e_max=('offering_end_date', 'max'),
                                                     e_min=('offering_end_date', 'min'), n_enrollments=('enrollment_id', 'size')).reset_index()
        g['offering_end_date'] = np.where(g['split'] == 'train', g['e_max'], g['e_min'])
        g['end_spread_s'] = (g['e_max'] - g['e_min']).dt.total_seconds()
        n_multi_end = int((g['end_spread_s'] > 0).sum())
        g = g.drop(columns=['e_max', 'e_min'])
        g['block'] = g['split'].map(ROLE)
        wins = {w: {'TRAIN': ['TRAIN'], 'VALIDATION': ['VALIDATION'], 'TEST': ['TEST']}}
        audit = sv.audit_temporal_overlap(g.drop(columns='split'), windows=wins)
        ok, t = sv.qa22(audit)
        r = t.iloc[0]
        reg_row = reg[reg.window_id == w].iloc[0]
        B_rows.append(dict(task=task, source='phase_view (tinh lai)', window_id=w, tau_w=str(r['tau_w'])[:19], min_eval_end=str(min(r['val_min_end'], r['test_min_end']))[:19],
                           end_order_ok=bool(r['end_order_ok']), n_val=int(r['n_enrollments_val']), n_test=int(r['n_enrollments_test']), qa22_ok=bool(r['qa22_ok']),
                           registry_n_val=int(reg_row['n_enrollments_validation']), registry_n_test=int(reg_row['n_enrollments_test']),
                           counts_match_registry=bool(r['n_enrollments_val'] == reg_row['n_enrollments_validation'] and r['n_enrollments_test'] == reg_row['n_enrollments_test']),
                           registry_tau_w=reg_row['tau_w'], n_offerings=int(len(g)), n_offerings_with_two_end_values=n_multi_end, max_offering_end_spread_s=float(g.end_spread_s.max()),
                           tau_exclusive_minus_1day_equals_registry_tau=bool((r['tau_w'] - pd.Timedelta(days=1)).strftime('%Y-%m-%d') == str(reg_row['tau_w'])[:10]), margin_days=float((min(r['val_min_end'], r['test_min_end']) - r['tau_w']).total_seconds() / 86400)))
A = pd.DataFrame(A_rows); B = pd.DataFrame(B_rows)
A.to_csv(f'{OUT}/qa22_registry_check.csv', index=False); B.to_csv(f'{OUT}/qa22_recomputed_from_views.csv', index=False)
pd.DataFrame(inputs, columns=['input', 'path_relative_to_repo', 'sha256']).to_csv(f'{OUT}/qa22_inputs_sha256.csv', index=False)
print(A.to_string()); print(B.to_string())
