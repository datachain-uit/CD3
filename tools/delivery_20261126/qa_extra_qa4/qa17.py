# -*- coding: utf-8 -*-
"""QA17 (don vi) cho release CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2.
Env: TEMPO_REPO_ROOT, QA4_OUT. Doc 2 bang (seed-level, seed_agg); khong ghi ra ngoai QA4_OUT."""
import os, re, json, sys
import numpy as np, pandas as pd, pyarrow.parquet as pq
REPO = os.environ['TEMPO_REPO_ROOT']
OUT = os.environ['QA4_OUT']
REL = f'{REPO}/CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2'
SRC_NAMING = "Mo_ta_meta-dataset.docx, bang 'Quy uoc dat ten': _s giay, _mb MB, _kwh kWh, _g gram CO2e, _w W, _usd USD; muc 'Don vi': s, MB, W, kWh, gCO2e, USD"
SRC_ENERGY = "tempo_fix/energy_nvml.py: E_kWh = (counter_end_mJ - counter_start_mJ)/3.6e9 hoac tich phan P(W)*dt(s)/3.6e6; truong energy_gpu_{stage}_kwh"
SRC_TIME = "Mo_ta_meta-dataset.docx muc 8 bang cot COST: time_*_s = thoi gian theo giai doan (giay); registries decision 15 (train_seconds)"
UNIT_RANGE = {'s': (0, 7 * 86400), 'kWh': (0, 10.0), '1': (0, 100.0)}  # (loai tru 0 neu >0 bat buoc, tran)
PAT = re.compile(r'^(time_[a-z_]+?_s|energy_[a-z_]+?_kwh)_(after|before|ratio|delta)(?:_(mean|sd|median|min|max|p90|p95))?$')
PAT_AGG_SUFFIX = re.compile(r'^(time_[a-z_]+?_s|energy_[a-z_]+?_kwh)_(after|before|ratio|delta)_(mean|sd|median|min|max|p90|p95)$')

def classify(col):
    m = PAT.match(col)
    if not m: return None
    base, kind, stat = m.groups()
    bu = 's' if base.endswith('_s') else 'kWh'
    if kind == 'ratio': unit = '1'
    else: unit = bu
    src = (SRC_TIME if bu == 's' else SRC_ENERGY) + ' | ' + SRC_NAMING
    return base, kind, stat, bu, unit, src

def main():
    rows, checks = [], []
    # cot toan cuc: tim moi cot co hau to don vi khac trong release (khong co -> ghi nhan)
    other_unit_cols = {}
    tabs = {}
    for t in ['meta_dataset_seed_level', 'meta_dataset_seed_agg']:
        names = pq.ParquetFile(f'{REL}/{t}.parquet').schema.names
        other_unit_cols[t] = [c for c in names if re.search(r'(_mb|_w|_usd|_g|co2|gco2|cost_usd|peak_|_ram|gpu_mem|power|watt)(_|$)', c)]
        cost = [c for c in names if classify(c)]
        # co cost nhung ten la thi khong khop pattern
        stray = [c for c in names if re.match(r'^(time_|energy_(?!measurement))', c) and not classify(c)]
        tabs[t] = (names, cost, stray)
    dd = pd.read_parquet(f'{REL}/meta_dataset_seed_level.parquet', columns=tabs['meta_dataset_seed_level'][1] + ['run_id_after', 'task', 'energy_measurement_type'])
    da = pd.read_parquet(f'{REL}/meta_dataset_seed_agg.parquet', columns=tabs['meta_dataset_seed_agg'][1])
    for t, df in [('meta_dataset_seed_level', dd), ('meta_dataset_seed_agg', da)]:
        for c in tabs[t][1]:
            base, kind, stat, bu, unit, src = classify(c)
            v = pd.to_numeric(df[c], errors='coerce').dropna()
            fin = bool(np.isfinite(v).all())
            n = len(v)
            lo, hi = (float(v.min()), float(v.max())) if n else (np.nan, np.nan)
            cap = UNIT_RANGE[unit][1]
            if kind == 'delta':
                ok = fin and abs(lo) <= cap and abs(hi) <= cap
            elif stat == 'sd':
                ok = fin and lo >= 0 and hi <= cap
            else:
                ok = fin and lo > 0 and hi <= cap
            rows.append(dict(table=t, column=c, declared_unit=unit, base_unit=bu, source_of_definition=src,
                             n_nonnull=n, n_rows=len(df), min=lo, max=hi, range_rule=('|x|<=%g' % cap if kind == 'delta' else ('0<=x<=%g' % cap if stat == 'sd' else '0<x<=%g' % cap)),
                             status='PASS' if (ok and n > 0) else 'FAIL'))
    tbl = pd.DataFrame(rows)
    # --- kiem tra bo sung ---
    r = dd.drop_duplicates('run_id_after').copy()
    pw = r['energy_gpu_run_kwh_after'] * 3.6e6 / r['time_run_total_s_after']
    pw = pw.dropna()
    P_LO, P_HI = 10.0, 100.0  # W: GPU L4 TDP 72 W; ngan sach rong
    n_pw_ok = int(((pw >= P_LO) & (pw <= P_HI)).sum())
    checks.append(dict(check='implied_mean_power_W = kWh*3.6e6/s per run in [10,100] W', n=int(len(pw)), n_pass=n_pw_ok, n_fail=int(len(pw) - n_pw_ok),
                       min=float(pw.min()), max=float(pw.max()), median=float(pw.median())))
    tt = (dd['time_train_s_after'] <= dd['time_run_total_s_after'] + 1e-9)[dd['time_run_total_s_after'].notna()]
    checks.append(dict(check='time_train_s_after <= time_run_total_s_after (rows with both)', n=int(len(tt)), n_pass=int(tt.sum()), n_fail=int((~tt).sum())))
    for b in ['time_train_s', 'time_run_total_s', 'energy_gpu_run_kwh']:
        a, bf, rt, de = dd[b + '_after'], dd[b + '_before'], dd[b + '_ratio'], dd[b + '_delta']
        m = a.notna() & bf.notna() & rt.notna()
        ok = ((a / bf - rt).abs() <= 1e-9 * rt.abs().clip(lower=1))[m]
        checks.append(dict(check=f'{b}_ratio = after/before (1e-9 rel)', n=int(m.sum()), n_pass=int(ok.sum()), n_fail=int((~ok).sum())))
        m2 = a.notna() & bf.notna() & de.notna()
        ok2 = ((a - bf - de).abs() <= 1e-9 * (a.abs() + bf.abs()).clip(lower=1))[m2]
        checks.append(dict(check=f'{b}_delta = after-before (1e-9 rel)', n=int(m2.sum()), n_pass=int(ok2.sum()), n_fail=int((~ok2).sum())))
    ck = pd.DataFrame(checks)
    # dictionary: cot COST khong co truong don vi
    dic = pd.read_csv(f'{REL}/meta_column_dictionary.csv')
    dict_cost = dic[dic.role == 'COST'].column_name.tolist()
    not_covered = sorted(set(dict_cost) - set(tabs['meta_dataset_seed_level'][1]))
    tbl.to_csv(f'{OUT}/qa17_unit_table.csv', index=False, encoding='utf-8')
    ck.to_csv(f'{OUT}/qa17_checks.csv', index=False, encoding='utf-8')
    n_cols = len(tbl); n_fail_cols = int((tbl.status == 'FAIL').sum())
    n_fail_chk = int(ck.n_fail.sum())
    summ = dict(n_cost_columns_seed_level=int((tbl.table == 'meta_dataset_seed_level').sum()), n_cost_columns_seed_agg=int((tbl.table == 'meta_dataset_seed_agg').sum()),
                dictionary_has_unit_field=bool('unit' in dic.columns), dictionary_cost_cols=len(dict_cost), dictionary_cost_not_covered=not_covered,
                stray_time_energy_cols={t: tabs[t][2] for t in tabs}, other_unit_cols_found=other_unit_cols,
                n_cols_fail=n_fail_cols, n_checks_fail=n_fail_chk)
    json.dump(summ, open(f'{OUT}/qa17_summary.json', 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(summ, indent=1)); print(tbl.groupby(['table', 'status']).size()); print(ck.to_string())
    print(tbl[tbl.table == 'meta_dataset_seed_level'][['column', 'declared_unit', 'n_nonnull', 'min', 'max', 'status']].to_string())
if __name__ == '__main__':
    main()
