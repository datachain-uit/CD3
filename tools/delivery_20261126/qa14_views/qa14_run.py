# -*- coding: utf-8 -*-
"""QA14: chay tren phase view local cac kiem tra co the chay cua 6 sanity test (Kich ban 3.5 / AGENT_READY guide muc 3).
Dau vao: TEMPO_REPO_ROOT (views), QA14_OUT. Khong ghi o dau khac. Stream parquet bang pyarrow.
Ghi: qa14_results.csv, qa14_input_views.csv, qa14_detail_*.csv"""
import os, glob, re, json, hashlib, sys
import numpy as np, pandas as pd
import pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc

REPO = os.environ['TEMPO_REPO_ROOT']
OUT = os.environ.get('QA14_OUT', os.path.dirname(os.path.abspath(__file__)))
RAW = f'{REPO}/downloads/raw_views_20261108'
TASKS = {
    'CQ': dict(main='CQ/phase_views_v2_2', test='CQ_test', labels=['CQ_label_final']),
    'LO': dict(main='LO/phase_views_v3_1_scored_signal_excluded', test='LO_test', labels=['LO_performance_label_3', 'LO_performance_label_5']),
}
WINDOWS = ['W1', 'W2', 'W3']
PH = [1, 2, 3, 4]
rows = []
detail = []


def sha_md5(path):
    s = hashlib.sha256(); m = hashlib.md5()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            s.update(b); m.update(b)
    return s.hexdigest(), m.hexdigest()


def pq_file(d):
    return glob.glob(f'{d}/*.parquet')[0]


# ---------- identity of the input views ----------
ident = []
view_files = {}
for t, c in TASKS.items():
    view_files[(t, 'main')] = pq_file(f'{RAW}/{c["main"]}')
    for k in PH:
        view_files[(t, f'P{k}')] = pq_file(f'{RAW}/{c["test"]}/P{k}')
ident_path = f'{OUT}/qa14_input_views.csv'
if os.path.exists(ident_path):
    idf = pd.read_csv(ident_path)
else:
    for (t, v), f in view_files.items():
        s, m = sha_md5(f)
        ident.append(dict(task=t, view=v, file_name=os.path.basename(f), bytes=os.path.getsize(f), sha256=s, md5=m))
    idf = pd.DataFrame(ident)
    # doi chieu MD5 voi inventory Drive
    inv = pd.read_parquet(os.environ['TEMPO_WORK_ROOT'] + '/tree/inventory_all.parquet', columns=['root', 'path', 'md5', 'size'])
    idf['drive_md5_match_inventory'] = [bool(((inv.md5 == m) & (inv['size'] == b)).any()) for m, b in zip(idf.md5, idf.bytes)]
    idf.to_csv(ident_path, index=False)
VIEW_SHA = {}
for t in TASKS:
    sub = idf[idf.task == t].sort_values('view')
    VIEW_SHA[t] = hashlib.sha256('\n'.join(f'{r.view}:{r.sha256}' for r in sub.itertuples()).encode()).hexdigest()


def add(test, sub, task, window, status, n, nf, reason):
    rows.append(dict(test=test, sub_check=sub, task=task, window=window, status=status, n_checked=int(n), n_fail=int(nf),
                     evidence_sha256_of_input_views=VIEW_SHA[task], reason=reason))


def norm(a):
    """chuan hoa NaN -> null cho so thuc"""
    if pa.types.is_floating(a.type):
        return pc.if_else(pc.is_nan(a), pa.scalar(None, a.type), a)
    return a


def same(a, b):
    """bool array: bang nhau (null==null)"""
    a = norm(a); b = norm(b)
    if pa.types.is_list(a.type) or pa.types.is_large_list(a.type):
        la = a.to_pylist(); lb = b.to_pylist()
        return np.array([x == y for x, y in zip(la, lb)])
    eq = pc.fill_null(pc.equal(a, b), False)
    bn = pc.and_(pc.is_null(a), pc.is_null(b))
    return pc.or_(eq, bn).to_numpy(zero_copy_only=False)


def chunked(t, name):
    return t.column(name).combine_chunks()


# ---------- loaders ----------
def load_test(task):
    """tra ve dict k -> (ParquetFile, key array, window codes) da canh theo thu tu cua P4"""
    pfs = {k: pq.ParquetFile(view_files[(task, f'P{k}')]) for k in PH}
    keys = {}
    for k in PH:
        t = pfs[k].read(columns=['window', 'enrollment_id'])
        keys[k] = (pc.binary_join_element_wise(chunked(t, 'window'), chunked(t, 'enrollment_id'), '|')).to_pandas()
    return pfs, keys


def window_counts(win, mask_fail):
    out = {}
    for w in WINDOWS:
        sel = (win == w)
        out[w] = (int(sel.sum()), int((mask_fail & sel).sum()))
    out['ALL'] = (len(win), int(mask_fail.sum()))
    return out


def emit(test, sub, task, status_ok, status_bad, wc, reason):
    for w, (n, nf) in wc.items():
        add(test, sub, task, w, status_ok if nf == 0 else status_bad, n, nf, reason)


for task, cfg in TASKS.items():
    print('=== task', task, flush=True)
    pfs, keys = load_test(task)
    labels = cfg['labels']
    main_pf = pq.ParquetFile(view_files[(task, 'main')])
    names = main_pf.schema_arrow.names
    pcols = [c for c in names if re.search(r'_P[1-4]$', c)]
    bases = sorted({re.sub(r'_P[1-4]$', '', c) for c in pcols})
    static_cols = [c for c in pfs[4].schema_arrow.names if not re.search(r'_P[1-4]$', c) and c != 'prediction_phase']
    static_cols = list(dict.fromkeys(static_cols))  # CQ co cot 'element' lap

    # ======================= CARDINALITY (test views) =======================
    n_rows = {k: pfs[k].metadata.num_rows for k in PH}
    dup = {k: int(keys[k].duplicated().sum()) for k in PH}
    k4 = keys[4]
    win4 = k4.str.split('|').str[0].to_numpy()
    base_set = set(k4)
    diffs = {k: len(base_set ^ set(keys[k])) for k in (1, 2, 3)}
    dup_mask = k4.duplicated().to_numpy()
    emit('cardinality', 'test_views_one_row_per_window_enrollment', task, 'PASS', 'FAIL', window_counts(win4, dup_mask),
         f'Moi view test P1..P4 co dung mot dong cho moi (window, enrollment_id): dong lap P1..P4 = {[dup[k] for k in PH]}; so dong = {[n_rows[k] for k in PH]}.')
    sym = np.zeros(len(k4), dtype=bool)
    for k in (1, 2, 3):
        sym |= ~k4.isin(set(keys[k])).to_numpy()
    emit('cardinality', 'test_views_same_enrollment_set_P1_P4', task, 'PASS', 'FAIL', window_counts(win4, sym),
         f'Tap (window, enrollment_id) cua P1, P2, P3 trung P4: ky hieu chenh lech = {[diffs[k] for k in (1, 2, 3)]}. Moi enrollment co dung 4 view prefix (<= 4).')

    # ======================= doc cac cot can thiet cua test views =======================
    def read_test_cols(k, cols):
        t = pfs[k].read(columns=cols)
        return t

    # canh hang theo P4
    idx = {}
    pos4 = pd.Series(np.arange(len(k4)), index=k4.to_numpy())
    for k in PH:
        idx[k] = pos4.reindex(keys[k].to_numpy()).to_numpy()  # vi tri trong P4 cua dong k
    inv_idx = {}
    for k in PH:
        # take cho view k de co thu tu P4
        order = np.empty(len(k4), dtype=np.int64)
        order[idx[k].astype(np.int64)] = np.arange(len(keys[k]))
        inv_idx[k] = order
    aligned = all(diffs[k] == 0 for k in (1, 2, 3)) and all(dup[k] == 0 for k in PH)
    assert aligned, 'view test khong canh duoc'

    def col(k, c):
        return pc.take(chunked(read_test_cols(k, [c]), c), pa.array(inv_idx[k]))

    # ======================= SPLIT IDENTITY =======================
    sp_bad = np.zeros(len(k4), dtype=bool)
    sp4 = col(4, 'split').to_numpy(zero_copy_only=False)
    sp_bad |= (sp4 != 'test')
    for k in (1, 2, 3):
        sp_bad |= (col(k, 'split').to_numpy(zero_copy_only=False) != sp4)
    emit('split_identity', 'test_prefixes_same_partition', task, 'PASS', 'FAIL', window_counts(win4, sp_bad),
         'Moi prefix P1..P4 cua mot (window, enrollment) trong view test deu co split = test (cung partition).')

    # main view: duy nhat theo (window, enrollment); roi nhau voi test
    mt = main_pf.read(columns=['window', 'enrollment_id', 'split'])
    mkey = pc.binary_join_element_wise(chunked(mt, 'window'), chunked(mt, 'enrollment_id'), '|')
    mdup = pc.count(mkey).as_py() - pc.count_distinct(mkey).as_py()
    inter = pc.is_in(pa.array(k4.to_numpy()), value_set=mkey).to_numpy(zero_copy_only=False)
    msp = pc.unique(chunked(mt, 'split')).to_pylist()
    wins_main = chunked(mt, 'window').to_pandas()
    mdup_mask = pd.Series(mkey.to_pandas()).duplicated(keep=False).to_numpy()
    n_main = len(mkey)
    emit('split_identity', 'main_view_unique_window_enrollment_one_partition', task, 'PASS', 'FAIL',
         window_counts(wins_main.to_numpy(), mdup_mask),
         f'View TRAIN+VALIDATION: moi (window, enrollment_id) xuat hien dung mot lan, tuc o dung mot partition (train hoac validation); split gom {sorted(msp)}.')
    emit('split_identity', 'test_disjoint_from_train_validation_per_window', task, 'PASS', 'FAIL', window_counts(win4, inter),
         'Khong (window, enrollment_id) nao cua view test cung xuat hien trong view TRAIN+VALIDATION cua cung window.')
    del mt, mkey, mdup_mask

    # ======================= LABEL IDENTITY =======================
    lab_cols = labels + ['label_availability_time']
    parts = [main_pf.read(columns=['enrollment_id'] + lab_cols)]
    for k in PH:
        parts.append(pfs[k].read(columns=['enrollment_id'] + lab_cols))
    allt = pa.concat_tables(parts)
    for lc in lab_cols:
        g = allt.group_by('enrollment_id').aggregate([(lc, 'count_distinct', pc.CountOptions(mode='only_valid')), (lc, 'count', pc.CountOptions(mode='only_valid'))])
        cd = g.column(f'{lc}_count_distinct').to_numpy(); cn = g.column(f'{lc}_count').to_numpy()
        multi = int((cd > 1).sum()); nolab = int((cn == 0).sum()); ne = g.num_rows
        add('label_identity', f'one_value_per_enrollment_across_all_views:{lc}', task, 'ALL', ('NOT_RUN' if nolab == ne else ('PASS' if multi == 0 else 'FAIL')), ne, multi,
            f'Gop view TRAIN+VALIDATION va 4 view test, {allt.num_rows} dong: so enrollment co >1 gia tri {lc} = {multi}; so enrollment khong co gia tri (null o moi dong) = {nolab}. Pham vi: enrollment co mat trong view. Neu so enrollment khong co gia tri = tong so enrollment thi cot toan null va khong co gi de kiem (NOT_RUN).')
    # nhan giong nhau giua P1..P4 view test
    lbad = np.zeros(len(k4), dtype=bool)
    for lc in labels + ['label_availability_time']:
        a4 = col(4, lc)
        for k in (1, 2, 3):
            lbad |= ~same(col(k, lc), a4)
    emit('label_identity', 'test_P1_P4_label_columns_equal', task, 'PASS', 'FAIL', window_counts(win4, lbad),
         f'Cac cot {lab_cols} giong nhau giua P1..P4 cua tung enrollment trong view test.')
    del allt, parts

    # ======================= PREFIX NESTING proxy: gia tri X_Pj va mat na tuong lai =======================
    n_cells = 0; n_bad_eq = 0; n_fut = 0; n_fut_bad = 0
    bad_eq_rows = np.zeros(len(k4), dtype=bool); bad_fut_rows = np.zeros(len(k4), dtype=bool)
    det = []
    for b in bases:
        full = {j: chunked(read_test_cols(4, [f'{b}_P{j}']), f'{b}_P{j}') for j in PH}
        for k in (1, 2, 3):
            tk = read_test_cols(k, [f'{b}_P{j}' for j in PH])
            for j in PH:
                a = pc.take(chunked(tk, f'{b}_P{j}'), pa.array(inv_idx[k]))
                if j <= k:
                    ok = same(a, full[j])
                    n_cells += len(ok); nb = int((~ok).sum()); n_bad_eq += nb
                    bad_eq_rows |= ~ok
                    if nb: det.append((task, 'value_equal_to_P4_view', b, j, k, nb))
                else:
                    if b == 'phase_available':
                        ok = (a.to_numpy(zero_copy_only=False) == 0)
                    else:
                        ok = pc.is_null(norm(a)).to_numpy(zero_copy_only=False)
                    n_fut += len(ok); nb = int((~ok).sum()); n_fut_bad += nb
                    bad_fut_rows |= ~ok
                    if nb: det.append((task, 'future_slot_not_null', b, j, k, nb))
    pd.DataFrame(det, columns=['task', 'check', 'base_column', 'slot_Pj', 'view_Pk', 'n_bad']).to_csv(f'{OUT}/qa14_detail_nesting_{task}.csv', index=False)
    emit('prefix_nesting', 'view_value_equality_Pj_in_Pk_view_vs_P4_view', task, 'PROXY_PASS', 'PROXY_FAIL', window_counts(win4, bad_eq_rows),
         f'PROXY_ON_VIEWS: gia tri cot X_Pj (j<=k) trong view test Pk bang gia tri cung enrollment trong view P4, tren {len(bases)} cot goc x cac cap (j,k); so o so sanh = {n_cells}, o lech = {n_bad_eq}. Dau vao that: su kien tho tung phase, events(P1) subset events(P2) subset ...')
    emit('prefix_nesting', 'future_slots_masked_in_Pk_view', task, 'PROXY_PASS', 'PROXY_FAIL', window_counts(win4, bad_fut_rows),
         f'PROXY_ON_VIEWS: cac slot P_j (j>k) cua view Pk rong (null; phase_available = 0); so o = {n_fut}, o khong rong = {n_fut_bad}.')
    # future perturbation proxy dung lai mat na: P1 khong mang thong tin X2-X4
    emit('future_perturbation', 'P1_view_carries_no_X2_X4_values', task, 'PROXY_PASS', 'PROXY_FAIL',
         window_counts(win4, bad_fut_rows),
         'PROXY_ON_VIEWS: view P1 co moi cot P2..P4 deu null (phase_available=0) nen sua X2-X4 khong the doi cot cua view; KHONG chung minh cac cot P1/static khong tinh tu su kien tuong lai. Test that can su kien tho + phase builder + ban nhieu loan X2-X4.')

    # ======================= CUTOFF EQUALITY proxy tren view test =======================
    cut_bad = np.zeros(len(k4), dtype=bool)
    for j in PH:
        cj = chunked(read_test_cols(4, [f'cutoff_time_P{j}']), f'cutoff_time_P{j}')
        for k in range(j, 4):
            if k == 4: continue
            a = pc.take(chunked(read_test_cols(k, [f'cutoff_time_P{j}']), f'cutoff_time_P{j}'), pa.array(inv_idx[k]))
            cut_bad |= ~same(a, cj)
    emit('cutoff_equality', 'cutoff_time_Pj_equal_across_test_views', task, 'PROXY_PASS', 'PROXY_FAIL', window_counts(win4, cut_bad),
         'PROXY_ON_VIEWS: cutoff_time_Pj cua mot enrollment bang nhau o moi view test Pk (k>=j). Test that: khong su kien nao co availability_time > cutoff cua phase (can bang su kien tho / log conformance cua phase builder).')

    # ======================= MAIN VIEW: stream theo row group =======================
    cum_cols = ['comment_count', 'problem_count', 'segment_count', 'unique_video_count', 'video_active_day_count', 'correct_problem_count',
                'incorrect_problem_count', 'attempts_sum', 'score_sum', 'positive_comment_count', 'negative_comment_count', 'neutral_comment_count',
                'unique_commented_resource_count', 'last_video_day_from_enroll', 'last_submit_day_from_enroll', 'last_comment_day_from_enroll']
    cum_cols = [c for c in cum_cols if f'{c}_P1' in names]
    need = (['window', 'enrollment_id', 'label_availability_time', 'primary_risk_set'] if 'primary_risk_set' in names else ['window', 'enrollment_id', 'label_availability_time'])
    need += [f'cutoff_time_P{k}' for k in PH] + [f'phase_available_P{k}' for k in PH] + [f'label_available_by_cutoff_P{k}' for k in PH]
    need += [f'{c}_P{k}' for c in cum_cols for k in PH]
    acc = {w: dict(sc_n=0, sc_bad=0, n=0, mono_bad=0, lab_before_cut_bad=0, risk_bad=0, phase_av_bad=0, lbc_bad=0, card_bad=0, cum_bad=0, cum_n=0, cum_cells_bad=0, cum_cells_n=0) for w in WINDOWS}
    cum_by_col = {c: [0, 0] for c in cum_cols}
    for rg in range(main_pf.num_row_groups):
        t = main_pf.read_row_group(rg, columns=need)
        df = t.to_pandas()
        for w, g in df.groupby('window'):
            a = acc[w]; a['n'] += len(g)
            cuts = [g[f'cutoff_time_P{k}'] for k in PH]
            mono = (cuts[0] <= cuts[1]) & (cuts[1] <= cuts[2]) & (cuts[2] <= cuts[3])
            a['mono_bad'] += int((~mono).sum())
            la = g['label_availability_time']
            a['lab_before_cut_bad'] += int((~(la > cuts[3])).sum())
            if 'primary_risk_set' in g: a['risk_bad'] += int((g['primary_risk_set'] != 1).sum())
            pa_sum = sum(g[f'phase_available_P{k}'] for k in PH)
            n_before = sum((cuts[k - 1] < la).astype(int) for k in PH)
            a['phase_av_bad'] += int((~(pa_sum == 4)).sum())
            a['card_bad'] += int((~(pa_sum == n_before)).sum())
            lbc = sum(g[f'label_available_by_cutoff_P{k}'].fillna(0) for k in PH)
            a['lbc_bad'] += int((lbc != 0).sum())
            for c in cum_cols:
                for k in (1, 2, 3):
                    x = g[f'{c}_P{k}']; y = g[f'{c}_P{k + 1}']
                    both = x.notna() & y.notna()
                    bad = both & (y < x)
                    if c == 'score_sum':
                        a['sc_n'] += int(both.sum()); a['sc_bad'] += int(bad.sum())
                    else:
                        a['cum_cells_n'] += int(both.sum()); a['cum_cells_bad'] += int(bad.sum())
                    cum_by_col[c][0] += int(both.sum()); cum_by_col[c][1] += int(bad.sum())
        print('  row group', rg, flush=True)
    pd.DataFrame([(c, v[0], v[1]) for c, v in cum_by_col.items()], columns=['column', 'n_pairs_checked', 'n_decrease']).to_csv(f'{OUT}/qa14_detail_cumulative_monotone_{task}.csv', index=False)

    def mk(field):
        d = {w: (acc[w]['n'], acc[w][field]) for w in WINDOWS}
        d['ALL'] = (sum(acc[w]['n'] for w in WINDOWS), sum(acc[w][field] for w in WINDOWS))
        return d

    emit('cutoff_equality', 'main_view_cutoff_P1_le_P2_le_P3_le_P4', task, 'PROXY_PASS', 'PROXY_FAIL', mk('mono_bad'),
         'PROXY_ON_VIEWS: tren view TRAIN+VALIDATION, cutoff_time_P1 <= P2 <= P3 <= P4 (dieu kien can cua prefix long nhau). Khong thay the kiem tra availability_time cua su kien.')
    emit('cutoff_equality', 'main_view_label_availability_after_cutoff_P4', task, 'PROXY_PASS', 'PROXY_FAIL', mk('lab_before_cut_bad'),
         'PROXY_ON_VIEWS: label_availability_time > cutoff_time_P4 va label_available_by_cutoff_Pk = 0 o moi phase (nhan chua kha dung tai cutoff); tong lbc!=0 lech = ' + str(sum(acc[w]['lbc_bad'] for w in WINDOWS)) + '.')
    cwin = {w: (acc[w]['cum_cells_n'], acc[w]['cum_cells_bad']) for w in WINDOWS}
    cwin['ALL'] = (sum(v[0] for v in cwin.values()), sum(v[1] for v in cwin.values()))
    emit('prefix_nesting', 'main_view_cumulative_features_nondecreasing_P1_to_P4', task, 'PROXY_PASS', 'PROXY_FAIL', cwin,
         f'PROXY_ON_VIEWS: cac cot dem/ngay-cuoi ({len(cum_cols) - 1} cot, khong gom score_sum: ' + ', '.join(c for c in cum_cols if c != 'score_sum') + ') khong giam tu Pk sang Pk+1 trong view TRAIN+VALIDATION (he qua cua events(Pk) subset events(Pk+1)); chi tiet trong qa14_detail_cumulative_monotone_' + task + '.csv. Cot khong tich luy khong duoc kiem tra.')
    swin = {w: (acc[w]['sc_n'], acc[w]['sc_bad']) for w in WINDOWS}
    swin['ALL'] = (sum(v[0] for v in swin.values()), sum(v[1] for v in swin.values()))
    emit('prefix_nesting', 'main_view_score_sum_nondecreasing_P1_to_P4', task, 'PROXY_PASS', 'PROXY_FAIL', swin,
         'PROXY_ON_VIEWS: score_sum_Pk <= score_sum_Pk+1 trong view TRAIN+VALIDATION. score_sum giam o mot so cap: chua ket luan day la vi pham long nhau vi dinh nghia score_sum (diem tot nhat/diem moi nhat theo bai) chua duoc xac nhan; can su kien tho de phan xu.')
    emit('cardinality', 'main_view_four_phase_slots_phase_available', task, 'PASS', 'FAIL', mk('phase_av_bad'),
         'Moi enrollment trong view TRAIN+VALIDATION co dung 4 slot phase (phase_available_P1..P4 deu 1), tuc <= 4 view/enrollment.')
    if task == 'LO':
        emit('cardinality', 'LO_phases_equal_phases_before_outcome_availability', task, 'PASS', 'FAIL', mk('card_bad'),
             'So phase kha dung = so phase co cutoff_time_Pk < label_availability_time (outcome availability) o view TRAIN+VALIDATION; pham vi: enrollment co mat trong view, view test co 4 phase moi enrollment cung dieu kien (xem dong cardinality view test).')
        # test views: phase count equal and cutoff_P4 < label availability
        a4 = chunked(read_test_cols(4, ['label_availability_time']), 'label_availability_time')
        c4 = chunked(read_test_cols(4, ['cutoff_time_P4']), 'cutoff_time_P4')
        bad = ~pc.fill_null(pc.less(c4, a4), False).to_numpy(zero_copy_only=False)
        emit('cardinality', 'LO_test_views_four_phases_before_outcome_availability', task, 'PASS', 'FAIL', window_counts(win4, bad),
             'Moi enrollment co mat o 4 view test va cutoff_time_P4 < label_availability_time, tuc so phase truoc outcome = 4 = so view.')
    else:
        a4 = chunked(read_test_cols(4, ['label_availability_time']), 'label_availability_time')
        c4 = chunked(read_test_cols(4, ['cutoff_time_P4']), 'cutoff_time_P4')
        bad = ~pc.fill_null(pc.less(c4, a4), False).to_numpy(zero_copy_only=False)
        emit('cutoff_equality', 'test_views_label_availability_after_cutoff_P4', task, 'PROXY_PASS', 'PROXY_FAIL', window_counts(win4, bad),
             'PROXY_ON_VIEWS: label_availability_time > cutoff_time_P4 o view test.')
    print(task, 'done', flush=True)

# ---------- cac dong NOT_RUN cho phan khong chay duoc ----------
NOT_RUN = {
    'prefix_nesting': 'NOT_RUN: events(P1) subset ... subset events(P4) can su kien tho (video/problem/comment) theo enrollment hoac chay lai phase builder voi log conformance; cac dong PROXY_ON_VIEWS chi kiem gia tri/mat na tren view rong.',
    'future_perturbation': 'NOT_RUN: can su kien tho + phase builder + bo nhieu loan X2-X4 roi so artifact P1 byte-by-byte; view rong khong cho phep.',
    'cutoff_equality': 'NOT_RUN: can availability_time cua tung su kien tho de dem su kien co availability_time > cutoff (log conformance *_cutoff_equality cua phase builder buoc build_scenario_phase_features.py khong co tren Drive/local).',
}
for task in TASKS:
    for tname, why in NOT_RUN.items():
        add(tname, 'EXACT_DEFINITION', task, 'ALL', 'NOT_RUN', 0, 0, why)

df = pd.DataFrame(rows)
df.to_csv(f'{OUT}/qa14_results.csv', index=False, encoding='utf-8')
print(df.drop(columns=['reason', 'evidence_sha256_of_input_views']).to_string())
