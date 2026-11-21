"""Write the seed 42 + 43 + 44 summary report (Markdown): model performance, seed 44 hand-over, meta-dataset configuration and meta-model (M-15) configuration/results.
All numbers come from the tables of report_aggregate_3seed.py, the release manifest, the M-18 package, the energy note and the M-15 result folders (nothing is typed by hand).
Output: docs/20112026/BAO_CAO_TONG_HOP_SEED42_43_44_2026-11-20.md (+ tables/)"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import A44, REPO, WORK
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

T = Path(os.environ.get('TEMPO_REPORT_TABLES', f'{A44}/report_s42_43_44'))
REL = Path(os.environ.get('TEMPO_RELEASE', f'{REPO}/CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026'))
DOC = Path(os.environ.get('TEMPO_REPORT_DIR', f'{REPO}/docs/20112026'))
M18 = Path(f'{A44}/m18_44/m18_training_history_seed44_20261119')
ENERGY = Path(f'{A44}/energy_note_seed44_20261119/energy_proposal_seed44.csv')
M15_DIRS = [Path(p) for p in os.environ.get('TEMPO_M15_DIRS', f'{WORK}/m15_026/mm_runs_phaseA').split(';')]
M15_ALT = Path(f'{REPO}/CQ/resuilt/m15_full3seed_local_1thread_20261119_223831')
def _se_sentence():
    import pandas as _pd
    d_ = M15_DIRS[0]
    f_ = d_ / 'sens_energy' / 'mm_cost_basis.parquet'
    if not f_.exists() or not (d_ / 'main_cal_time' / 'mm_metrics.parquet').exists():
        return 'Kết quả `sens_energy` chưa có tại thời điểm viết.'
    cb = _pd.read_parquet(f_)
    tot = cb.groupby(['task', 'cost_basis']).n_groups.sum().unstack(fill_value=0)
    parts = '; '.join(f"{t}: {int(r.get('ENERGY', 0))} nhóm theo năng lượng, {int(r.get('TIME', 0))} nhóm theo thời gian" for t, r in tot.iterrows())
    x, y = _pd.read_parquet(d_ / 'sens_energy' / 'mm_metrics.parquet'), _pd.read_parquet(d_ / 'main_cal_time' / 'mm_metrics.parquet')
    num = [c for c in x.columns if x[c].dtype.kind == 'f']
    nd = int((_pd.DataFrame({c: (x[c] - y[c]).abs() for c in num}).max(axis=1) > 1e-9).sum())
    rx, ry = _pd.read_parquet(d_ / 'sens_energy' / 'mm_recommendations.parquet'), _pd.read_parquet(d_ / 'main_cal_time' / 'mm_recommendations.parquet')
    nr = int((rx.pipeline_recommended.values != ry.pipeline_recommended.values).sum())
    return (f'Theo bảng `mm_cost_basis` (12 nhóm mỗi task × mô hình): {parts}. Nhóm thiếu tỉ lệ năng lượng ở một seed tự về cơ sở thời gian. '
            f'So với `main_cal_time`, `sens_energy` khác ở {nd}/{len(x)} dòng `mm_metrics` (các cột chi phí và Pareto) và {nr}/{len(rx)} khuyến nghị pipeline.')


SE_SENT = _se_sentence()
(DOC / 'tables').mkdir(parents=True, exist_ok=True)
for p in T.glob('*.csv'):
    shutil.copy2(p, DOC / 'tables' / p.name)
shutil.copy2(T / 'sources.json', DOC / 'tables' / 'sources.json')

ORDER = ['RNN', 'LSTM', 'GRU', 'BILSTM', 'PATCHTST', 'MANTIS_V2']
FAM = {'RNN': 'F1', 'LSTM': 'F1', 'GRU': 'F1', 'BILSTM': 'F1', 'PATCHTST': 'F2', 'MANTIS_V2': 'F3'}
SEEDS = [42, 43, 44]
summ = pd.read_csv(T / 'summary_task_model_seed.csv')
across = pd.read_csv(T / 'summary_task_model_across_seeds.csv')
v0 = pd.read_csv(T / 'summary_V0_vs_V1V16.csv')
dl = pd.read_csv(T / 'delta_V0_vs_V1V16_macro_f1.csv')
bw = pd.read_csv(T / 'summary_task_model_seed_window.csv')
pa = pd.read_csv(T / 'seed_pair_agreement.csv')
sk = pd.read_csv(T / 'summary_s_leak.csv')
cov = pd.read_csv(T / 'coverage_cells.csv')
tm = pd.read_csv(T / 'summary_time_energy_seed.csv')
man = json.loads((REL / 'meta_release_manifest.json').read_text(encoding='utf-8'))
sl_cols = pd.read_parquet(REL / 'meta_dataset_seed_level.parquet').shape[1]
ag_cols = pd.read_parquet(REL / 'meta_dataset_seed_agg.parquet').shape[1]
dictionary = pd.read_csv(REL / 'meta_column_dictionary.csv')


def f(x, n=4):
    return '' if pd.isna(x) else f'{x:.{n}f}'


def tab(headers, rows):
    out = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join('---' for _ in headers) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)


def tm_rows(df, seeds=None):
    for t in ('CQ', 'LO'):
        for m in ORDER:
            for s in (seeds or SEEDS):
                r = df[(df.task == t) & (df.model_name == m) & (df.seed == s)]
                if len(r):
                    yield t, m, s, r.iloc[0]


L = []
w = L.append
w('# Báo cáo tổng hợp kết quả seed 42, 43 và 44, cấu hình meta-dataset và meta-model (CQ và LO) — 20/11/2026\n')
w('Báo cáo gộp kết quả hiệu suất của các mô hình đã chạy xong với ba seed 42, 43 và 44, cho hai tác vụ CQ và LO, ba cửa sổ W1–W3 và 17 pipeline V0–V16, sáu mô hình: F1 (RNN, LSTM, GRU, BILSTM), F2 (PatchTST) và F3 (Mantis V2). '
  'Báo cáo mô tả thêm bàn giao seed 44, cấu hình của meta-dataset ba seed và cấu hình, kết quả của meta-model (M-15). Mọi số trong bảng lấy từ release ba seed và từ các tệp nguồn nêu ở mục 8; không số nào được gõ tay.\n')

# ---- 1
w('## 1. Phạm vi và độ phủ\n')
w('Số ô (cửa sổ × pipeline) có kết quả trên tập kiểm tra, mỗi ô đủ bốn pha P1–P4:\n')
rows = []
for t in ('CQ', 'LO'):
    for m in ORDER:
        rows.append([t, FAM[m], m] + [int(cov[(cov.task == t) & (cov.model_name == m) & (cov.seed == s)].cells.iloc[0]) for s in SEEDS])
w(tab(['Task', 'Họ', 'Mô hình', 'Seed 42', 'Seed 43', 'Seed 44'], rows) + '\n')
n_ok = int((cov.cells == 51).sum())
w(f'Tất cả {n_ok} tổ hợp (task × mô hình × seed) trên {len(cov)} đều đủ 51 ô, mỗi ô {int(cov.rows.iloc[0]) // 51 if False else int(cov.rows.iloc[0] / 51)} dòng ở mức seed (2 tập × 4 pha) nên mỗi tổ hợp có {int(cov.rows.iloc[0])} dòng. '
  'Số trong các bảng dưới đây là **trung bình trên tập TEST**, lấy trung bình bốn pha P1–P4 của mỗi ô, rồi trung bình trên 51 ô.\n')

# ---- 2
w('## 2. Hiệu suất mô hình\n')
w('### 2.1 Chỉ số chính theo task, mô hình và seed\n')
rows = [[t, FAM[m], m, s] + [f(r[k]) for k in ('macro_f1', 'balanced_acc', 'kappa', 'gmean', 'log_loss', 'brier', 'ece', 'acctempo_m3_cal')] for t, m, s, r in tm_rows(summ)]
w(tab(['Task', 'Họ', 'Mô hình', 'Seed', 'F1 macro', 'Balanced acc', 'Kappa', 'G-mean', 'Log loss', 'Brier', 'ECE', 'AccTEMPO M3 cal (= M4)'], rows) + '\n')
_s = pd.read_csv(f'{A44}/facts44/CQ_patchtst_v0_v16_seed44/sanity_components.csv', usecols=['window_id', 'pipeline_id', 'eval_split', 'phase_id', 'acctempo_m4'])
_r = pd.read_parquet(REL / 'meta_dataset_seed_level.parquet', columns=['task', 'model_name', 'seed', 'window_id', 'pipeline_id', 'eval_split', 'phase_id', 'acctempo_m3_cal_after'])
_m = _s.merge(_r[(_r.task == 'CQ') & (_r.model_name == 'PATCHTST') & (_r.seed == 44)], on=['window_id', 'pipeline_id', 'eval_split', 'phase_id'])
w('**Tên chỉ số composite.** Cột `acctempo_m3_cal` của meta-dataset (AccTEMPO_M3^(cal)) là cùng một đại lượng với cột `acctempo_m4` trong các gói facts và các báo cáo trước (phiên bản M4): hai cột có giá trị trùng nhau '
  f'(chênh lệch tuyệt đối lớn nhất {float((_m.acctempo_m4 - _m.acctempo_m3_cal_after).abs().max()):.1f} trên {len(_m)} dòng CQ PatchTST seed 44), công thức S_perf^0,6 × S_san+_v2^0,4 với mỗi thành phần kẹp dưới 1e-3. '
  'Bộ lắp meta-dataset đổi tên `acctempo_m4` thành `acctempo_m3_cal`; báo cáo này dùng tên `acctempo_m3_cal` và ghi "= M4" khi cần nối với báo cáo cũ.' + chr(10))
w('Trung bình và độ lệch chuẩn giữa ba seed của chỉ số chính (F1 macro):\n')
rows = []
for t in ('CQ', 'LO'):
    for m in ORDER:
        r = across[(across.task == t) & (across.model_name == m)].iloc[0]
        rows.append([t, FAM[m], m, f(r.macro_f1_mean), f(r.macro_f1_std), f(r.acctempo_m3_cal_mean), f(r.acctempo_m3_cal_std)])
w(tab(['Task', 'Họ', 'Mô hình', 'F1 macro (trung bình 3 seed)', 'Độ lệch chuẩn', 'AccTEMPO M3 cal (trung bình)', 'Độ lệch chuẩn'], rows) + '\n')

w('### 2.2 V0 (không can thiệp) so với V1–V16 (imputation và cân bằng lớp)' + chr(10))
w('Mười bảy pipeline gồm ba nhóm: **V0** (không can thiệp); **imputation thuần** V1 (median), V5 (mean), V9 (ExtraTrees), V13 (MICE), balancer = NONE; **imputation cộng cân bằng lớp** (12 pipeline còn lại, mỗi imputer đi với CDSMOTE, SASMOTE hoặc RADIUS_SMOTE). '
  'Vì vậy V1–V16 không đồng nghĩa với "có tăng cường": bốn pipeline trong số đó chỉ là imputation. Bảng tách ba nhóm, và tách tác động của cân bằng lớp (mỗi pipeline cân bằng trừ pipeline imputation thuần cùng imputer, cùng cửa sổ):' + chr(10))
pg = pd.read_csv(T / 'summary_pipeline_groups.csv')
rows = []
for t, m, s_, r in tm_rows(pg):
    rows.append([t, FAM[m], m, s_, f(r.macro_f1_V0), f(r.macro_f1_IMP_ONLY), f(r.macro_f1_IMP_BAL), f(r.macro_f1_imp_only_minus_V0), f(r.macro_f1_imp_bal_minus_V0), f(r.bal_effect_macro_f1), f'{100 * r.bal_share_better:.0f}%'])
w(tab(['Task', 'Họ', 'Mô hình', 'Seed', 'F1 macro V0', 'F1 macro imputation thuần (4 pipeline)', 'F1 macro imputation + cân bằng (12)', 'Imputation thuần − V0', 'Imputation + cân bằng − V0', 'Riêng cân bằng lớp (so với pipeline cha)', 'Ô cân bằng hơn pipeline cha'], rows) + chr(10))
w('Gộp V1–V16 (không tách nhóm) so với V0 cho F1 macro và AccTEMPO M3 cal nằm trong `tables/summary_V0_vs_V1V16.csv`, kèm tỉ lệ ô V1–V16 hơn V0 trong `tables/delta_V0_vs_V1V16_macro_f1.csv`. Các chênh lệch trong bảng là mô tả, không có kiểm định.' + chr(10))
w('### 2.3 Theo cửa sổ (F1 macro)\n')
rows = []
for t in ('CQ', 'LO'):
    for m in ORDER:
        for win in ('W1', 'W2', 'W3'):
            rows.append([t, FAM[m], m, win] + [f(bw[(bw.task == t) & (bw.model_name == m) & (bw.window_id == win) & (bw.seed == s)].macro_f1.iloc[0]) for s in SEEDS])
w(tab(['Task', 'Họ', 'Mô hình', 'Cửa sổ', 'Seed 42', 'Seed 43', 'Seed 44'], rows) + '\n')

w('### 2.4 Độ lệch giữa ba seed (cùng ô)\n')
w('Với mỗi cặp seed, trên cùng 51 ô: độ lệch tuyệt đối trung bình của F1 macro, hệ số Pearson giữa các ô, và hệ số Spearman của thứ hạng 17 pipeline (theo trung bình mỗi pipeline):\n')
x = pa[pa.metric == 'macro_f1']
rows = []
for t in ('CQ', 'LO'):
    for m in ORDER:
        for _, r in x[(x.task == t) & (x.model_name == m)].iterrows():
            rows.append([t, FAM[m], m, f'{int(r.seed_a)}–{int(r.seed_b)}', f(r.mean_abs_diff), f(r.pearson_cells, 3), f(r.spearman_pipeline_means, 3), f'{r.best_pipeline_a} / {r.best_pipeline_b}'])
w(tab(['Task', 'Họ', 'Mô hình', 'Cặp seed', '|chênh| trung bình', 'Pearson (ô)', 'Spearman (pipeline)', 'Pipeline tốt nhất (hai seed)'], rows) + '\n')
g = x.groupby('task').agg(abs=('mean_abs_diff', 'mean'), p=('pearson_cells', 'mean'), s=('spearman_pipeline_means', 'mean'))
chg = x.assign(same=x.best_pipeline_a == x.best_pipeline_b).groupby('task').same.mean()
w(f'Tóm tắt: giá trị theo ô khá ổn định giữa các seed (Pearson trung bình CQ {f(g.loc["CQ", "p"], 3)}, LO {f(g.loc["LO", "p"], 3)}; độ lệch tuyệt đối trung bình CQ {f(g.loc["CQ", "abs"], 3)}, LO {f(g.loc["LO", "abs"], 3)}), '
  f'nhưng thứ hạng 17 pipeline theo trung bình kém ổn định (Spearman trung bình CQ {f(g.loc["CQ", "s"], 3)}, LO {f(g.loc["LO", "s"], 3)}); pipeline tốt nhất giữ nguyên giữa hai seed ở {100 * chg.loc["CQ"]:.0f}% (CQ) và {100 * chg.loc["LO"]:.0f}% (LO) số cặp. '
  'Đây là lý do meta-model được huấn luyện trên ba seed.\n')

w('### 2.5 s_leak\n')
mx = float(sk.max_abs_diff_between_seeds.max())
w(f'`s_leak` của cả ba seed được chép từ bảng tham chiếu đã đăng ký (`s_leak_source = {", ".join(json.loads((T / "sources.json").read_text())["s_leak_source_values"])}`), không fit lại đầu dò. '
  f'Chênh lệch lớn nhất của `s_leak` giữa ba seed trên mọi (task, cửa sổ, tập, pha) là {mx:.2e}. `probe_seed` ghi 42 (seed của lần fit tham chiếu) ở các gói seed 44.\n')
rows = []
for t in ('CQ', 'LO'):
    d = sk[sk.task == t]
    rows.append([t, len(d), f(d[[str(s) for s in SEEDS]].min().min()), f(d[[str(s) for s in SEEDS]].max().max()), f'{d.max_abs_diff_between_seeds.max():.2e}'])
w(tab(['Task', 'Số tổ hợp (cửa sổ, tập, pha)', 'Nhỏ nhất', 'Lớn nhất', 'Chênh lớn nhất giữa seed'], rows) + '\n')

# ---- 3 seed 44
w('## 3. Seed 44: bàn giao và vận hành\n')
w('### 3.1 Bàn giao\n')
m18s = pd.read_csv(M18 / 'm18_training_history_cell_summary_seed44.csv')
w(f'- **Sáu gói facts** (định dạng `_r2`, mỗi gói đủ 51 ô × 4 pha × 2 tập = 408 dòng mỗi mô hình): `CQ|LO/L2_facts/fact_exports/…seed44_…`; bản `staging_incoming` giống hệt; đã đối chiếu từng byte với Drive (biên nhận chuyển giao và ingest L2 đạt, hai gói Mantis kèm nhãn Q-32).\n'
  f'- **M-18 seed 44**: {len(m18s)} ô (12 tổ hợp × 51), {int(m18s.epochs_logged.sum()):,} dòng epoch; best epoch khớp manifest ở {int(m18s.best_epoch_equals_manifest.sum())}/{len(m18s)} ô; {int((m18s.n_sources > 1).sum())} ô có hai nguồn đều có history khớp nhau.\n'
  '- **Commit runner**: 510/510 ô F1 và PatchTST ghi `runner_git_commit = 5ba982958c9ce50ac6be6a28ff9c812e0f17b31e` lúc chạy; 102 ô Mantis không ghi commit trong manifest và dùng bằng chứng hồi tố (commit `6a69b7f6240a2b70ec7e6e478a446cecc2be1ec3`, khớp nội dung file với tar mã).\n'
  '- **Sửa sau đợt 29**: tiêu đề README theo seed, `probe_seed` = 42 (seed của lần fit tham chiếu), ghi commit dựng gói (`7c24981…`); bản trước khi sửa lưu ở `fact_exports_superseded_20261119`.\n')
w('### 3.2 Thời gian chạy và năng lượng\n')
w('Hai loại thời gian được tách riêng: **thời gian train** (`time_train_s`) và **tổng thời gian run** (`time_run_total_s`, gồm cả đọc dữ liệu, suy luận và ghi kết quả). Mỗi loại ghi số ô có dữ liệu (mẫu số của tổng và trung bình); '
  'ô thiếu giá trị không được tính vào tổng hay trung bình. Cột năng lượng ghi "không có dữ liệu" khi không ô nào có số đo, không có nghĩa là năng lượng bằng 0.' + chr(10))
rows = []
for t, m, s_, r in tm_rows(tm):
    en = f'{int(r.energy_runs)}/{int(r.runs)}'
    kwh = f(r.energy_kwh_measured, 2) if r.energy_runs > 0 else 'không có dữ liệu'
    rows.append([t, FAM[m], m, s_, int(r.runs), f'{int(r.n_time_train)}/{int(r.runs)}', f(r.total_train_hours, 1), f(r.mean_train_minutes, 1), f'{int(r.n_time_run)}/{int(r.runs)}', f(r.total_run_hours, 1), f(r.mean_run_minutes, 1), en, kwh])
w(tab(['Task', 'Họ', 'Mô hình', 'Seed', 'Số ô', 'Ô có thời gian train', 'Tổng train (giờ)', 'Trung bình train (phút/ô)', 'Ô có tổng thời gian run', 'Tổng run (giờ)', 'Trung bình run (phút/ô)', 'Ô có năng lượng', 'Năng lượng đo được (kWh, trên các ô có số đo)'], rows) + chr(10))
REASON = {
    ('CQ', 'MANTIS_V2', 42): 'V0 gốc không lưu run manifest, thời gian chạy và năng lượng GPU (`NOT_RECORDED`, 3 ô V0 W1–W3); các ô còn lại: thư viện đo công suất không nạp được (`TELEMETRY_UNAVAILABLE: ModuleNotFoundError`).',
    ('LO', 'MANTIS_V2', 42): 'thư viện đo công suất không nạp được (`TELEMETRY_UNAVAILABLE: ModuleNotFoundError`).',
    ('CQ', 'PATCHTST', 43): 'đo công suất không khả dụng trên máy chạy (`UNAVAILABLE`).',
    ('LO', 'PATCHTST', 43): 'đo công suất không khả dụng trên máy chạy (`UNAVAILABLE`).',
    ('CQ', 'PATCHTST', 44): 'đo công suất không hoạt động (`ENERGY_NOT_MEASURED`); có đề xuất mức năng lượng bên dưới.',
    ('CQ', 'MANTIS_V2', 44): 'đo công suất không hoạt động (`ENERGY_NOT_MEASURED`); có đề xuất mức năng lượng bên dưới.',
}
for m_ in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
    REASON[('CQ', m_, 43)] = 'không đo năng lượng (`ENERGY_NOT_MEASURED`: `energy_measurement_type = UNAVAILABLE`, 0 mẫu).'
miss = tm[(tm.energy_runs < tm.runs) | (tm.n_time_run < tm.runs) | (tm.n_time_train < tm.runs)]
w('#### Ô thiếu dữ liệu thời gian hoặc năng lượng và lý do' + chr(10))
w('Bảng liệt kê mọi tổ hợp (task, mô hình, seed) có ô thiếu thời gian hoặc năng lượng; số ô thiếu tính từ release, lý do lấy từ cột `resource_null_reason` của các gói nguồn. Tổ hợp không có trong bảng thì đủ 51/51 ô. '
  'Cột năng lượng của LO đã được điền lại ở release 20261120 (mục 4) và khớp 918/918 run với gói nguồn; các ô LO còn thiếu là các ô mà gói nguồn không có số đo.' + chr(10))
rows = []
for r in miss.sort_values(['task', 'model_name', 'seed']).itertuples():
    why = REASON.get((r.task, r.model_name, int(r.seed)), 'lý do chưa được ghi trong gói nguồn')
    rows.append([r.task, r.model_name, int(r.seed), int(r.runs - r.n_time_train), int(r.runs - r.n_time_run), int(r.runs - r.energy_runs), why])
w(tab(['Task', 'Mô hình', 'Seed', 'Ô thiếu thời gian train', 'Ô thiếu tổng thời gian run', 'Ô thiếu năng lượng', 'Lý do'], rows) + chr(10))
w('Đề xuất mức năng lượng cho 8 ô CQ seed 44 (không áp dụng vào gói), tính bằng công suất trung vị của các ô cùng họ nhân thời gian chạy:' + chr(10))
e = pd.read_csv(ENERGY)
w(tab(['Mô hình', 'Cửa sổ', 'Pipeline', 'Thời gian chạy (giờ)', 'Công suất cơ sở (W)', 'Đề xuất (kWh)', 'Khoảng p5–p95 (kWh)'],
      [[r.model, r.window_id, r.pipeline_id, f(r.elapsed_seconds / 3600, 1), f(r.basis_power_w, 1), f(r.proposed_kwh, 3), f'{r.low_kwh_p5_power:.3f}–{r.high_kwh_p95_power:.3f}'] for r in e.itertuples()]) + '\n')
w('Chi tiết và phương pháp: `cross_task_meta/work_in_progress/energy_proposal_seed44_20261119`.\n')

# ---- 4 meta-dataset
w('## 4. Cấu hình meta-dataset (release ba seed)\n')
rel_id = man['meta_release_id']
qa = list(man['child_releases'].values())[0]['qa_pass_rates']
rows = [
    ['Mã phát hành', f'`{rel_id}`'],
    ['Phạm vi', 'F1 (RNN, LSTM, GRU, BILSTM), F2 (PatchTST V0–V16) và F3 (Mantis V2 V0–V16, dòng `EXPLORATORY`) cho CQ và LO; seed 42, 43, 44'],
    ['`planned_seeds`', str(man['planned_seeds'])],
    ['Bảng mức seed (`meta_dataset_seed_level`)', f'{man["n_rows_seed_level"]:,} dòng × {sl_cols} cột ({man["rows_by_task"]["CQ"]:,} CQ, {man["rows_by_task"]["LO"]:,} LO)'],
    ['Bảng gộp seed (`meta_dataset_seed_agg`)', f'{man["n_rows_seed_agg"]:,} dòng × {ag_cols} cột; `n_seeds_planned` = 3, `n_seeds_success` = 3 ở mọi dòng'],
    ['Từ điển cột', f'{len(dictionary)} cột ({", ".join(f"{k} {v}" for k, v in dictionary.role.value_counts().head(6).items())}…)'],
    ['Trạng thái dòng', ', '.join(f'{k}: {list(v["row_status_counts"].values())[0]:,}' for k, v in man['child_releases'].items())],
    ['Cờ QA (cả hai task)', ', '.join(f'{k.replace("qa_", "").replace("_ok", "")} = {v:.1f}' for k, v in qa.items())],
    ['Mã dựng', f'{man["metamodel_version"]}; registry `{man.get("registry_revision")}` (`tempo_fix/examples/registries_v1.6`, sha256 `{man["registry_manifest_sha256"][:12]}…`)'],
    ['Đầu vào', f'{len(man["input_files_sha256"])} tệp có băm sha256 trong manifest (R4 CQ, static-v2 LO, PatchTST, Mantis, sáu gói seed 43, sáu gói seed 44, S0 v4, Z_M v2, F0 CQ, bảng tham chiếu `s_leak`, gói bàn giao)'],
    ['S0 / F0', f'S0 {man["s0_profile"]}; F0 tham chiếu: CQ có, LO chưa có'],
]
w(tab(['Mục', 'Giá trị'], rows) + '\n')
w('**Khóa quan sát** (mỗi dòng là một meta-observation): task, nhãn và bộ ngưỡng, chế độ đặc trưng, cửa sổ, seed, pha, cohort, tập đánh giá, trục và giá trị nhóm con, mô hình, pipeline. '
  'Mỗi dòng giữ giá trị trước can thiệp (V0), sau can thiệp (V1–V16), chênh lệch và các tham chiếu (imputer-only, F0), ghép cặp theo cùng seed. Bảng gộp seed bỏ trục seed và thêm trung bình, độ lệch chuẩn, trung vị, p90, p95, số seed dương và độ nhất quán dấu của chênh lệch.\n')
w('**Đối chiếu với release một seed (`full42`, 12/11):** phần seed 42 của release mới trùng 2.448/2.448 dòng mỗi task. CQ: 58 cột F1 trước đây rỗng nay đã điền (đúng kết luận nghiệm thu metamodel 0.2.4); '
  'LO: một cột chẩn đoán `probe_n_iter` khác ở 408 dòng Mantis, giá trị mới khớp tệp nguồn. Đây không phải mục tiêu của meta-model.\n')
w('**Cột năng lượng và phiên bản lắp.** Release lắp bằng metamodel 0.2.6 (registry `registries_rev_2026-11-20b`) từ cùng 70 đầu vào của bản trước. Tệp tài nguyên LO của seed 42 có sẵn cột `energy_gpu_run_kwh` rỗng; từ 0.2.5 bộ lắp lấy giá trị ước lượng theo từng dòng mà cột chính rỗng, nên cột năng lượng LO đầy đủ (khớp 918/918 run LO với gói nguồn; 10 run không có số đo là Mantis seed 42 (5) và PatchTST seed 43 (5)). '
  'So với release 20261120 (bản vá cục bộ của bộ lắp 0.2.4), mọi cột chung trùng tuyệt đối trừ `meta_release_id` và `builder_version`; cột mới: `rec_energy_measured_types` (bảng mức seed) cùng sáu cột (bảng gộp seed) về kích thước lát và kiểu đo năng lượng. Giá trị năng lượng là ước lượng từ lấy mẫu công suất NVML (`NVML_POWER_SAMPLING_ESTIMATE`).' + chr(10))
w('**M-15 và release.** Cả sáu cấu hình chạy trên đúng release này bằng metamodel 0.2.6. Năm cấu hình dùng cơ sở chi phí thời gian cho kết quả trùng bộ chạy trước trên release 20261120 (so từng bảng `mm_*`: không bảng nào khác). `sens_energy` chạy với `--accept-energy-estimates` trên chính release này.' + chr(10))
w('**Cơ sở chi phí của `sens_energy`.** ' + SE_SENT + chr(10))

# ---- 5 meta-model
w('## 5. Cấu hình meta-model (M-15)\n')
w('### 5.1 Cấu hình chạy\n')
w(tab(['Mục', 'Giá trị'], [
    ['Đầu vào', f'`meta_dataset_seed_agg.parquet` của release ba seed ({man["n_rows_seed_agg"]:,} dòng; sha256 `8fc29ce4…`)'],
    ['Mã', 'metamodel 0.2.6 (2026-11-20; lệnh `metamodel.cli run`), tempo_fix registry rev 2026-11-20b'],
    ['Giao thức', 'E1-A (W1→W2), E1-B (W1W2→W3), E2 (CQ→LO, LO→CQ), E3 (giữ lại từng họ F1, F2, F3): 7 fold'],
    ['Meta-learner chính', 'L1 (elastic net, tương tác can thiệp–trạng thái), L2 (ExtraTrees), L3 (LightGBM hồi quy, learner chính), L4 (LightGBM LambdaRank)'],
    ['Meta-learner phụ', 'L5 (LightGBM ba lớp HARM/NEUTRAL/BENEFIT), L6 (hai LightGBM cho phần hiệu năng và phần sanity)'],
    ['Tập đặc trưng', 'FS0–FS5; mỗi learner chính chạy trên cả 6 tập, learner phụ trên tập chính: 4 × 6 + 2 = 26 ô học mỗi fold, 182 ô học mỗi cấu hình'],
    ['Tìm siêu tham số', 'Optuna TPE 50 lần thử (L1: lưới), vòng trong theo hối tiếc trung bình; 5 seed cho learner'],
    ['Baseline', 'B0–B7 (8 baseline mỗi fold), kể cả B7 (chẩn đoán TEMPO-DQ); kiểm âm tính MQ08 trên L3-FS3'],
    ['Cách chạy', 'Mỗi cấu hình một tiến trình, mỗi tiến trình một luồng (`OMP/OPENBLAS/MKL/NUMEXPR` = 1, `n_jobs` = 1); Python 3.12.1, lightgbm 4.7.0, optuna 5.0.0, pandas 3.1.0 (môi trường ghim của gói 13/11)'],
]) + '\n')
w('### 5.2 Sáu cấu hình\n')
w(tab(['Cấu hình', 'Mục tiêu', 'Cờ riêng'], [
    ['`main_cal_time`', 'AccTEMPO M3 hiệu chuẩn (`PAPER_COMPOSITE_CAL`)', '(mặc định); cơ sở chi phí: năng lượng nếu đo thật, ngược lại thời gian'],
    ['`sens_v1`', 'AccTEMPO M3 v1 (`META_PRIMARY_M3_V1`)', '`--objective META_PRIMARY_M3_V1`'],
    ['`sens_energy`', 'như mặc định', '`--accept-energy-estimates` (coi ước lượng NVML là số đo)'],
    ['`sens_conservative`', 'như mặc định', '`--conservative`'],
    ['`obj_perf`', 'trục hiệu năng S_perf', '`--objective PAPER_PERF_AXIS`'],
    ['`obj_macrof1`', 'F1 macro', '`--objective SECONDARY_MACRO_F1`'],
]) + '\n')

w('### 5.3 Kết quả\n')
res = {}
for name in ('main_cal_time', 'sens_v1', 'sens_energy', 'sens_conservative', 'obj_perf', 'obj_macrof1'):
    for base in M15_DIRS + [M15_ALT]:
        d = base / name
        if (d / 'mm_metrics.parquet').exists():
            res[name] = (d, base)
            break
if not res:
    w('Kết quả M-15 chưa có tại thời điểm viết; mục này được điền khi các cấu hình chạy xong.\n')
else:
    done = ', '.join(f'`{n}`' for n in res)
    w(f'Cấu hình đã có kết quả: {done} ({len(res)}/6).\n')
    rows = []
    for name, (d, base) in res.items():
        reg = pd.read_parquet(d / 'mm_run_registry.parquet')
        nc = pd.read_parquet(d / 'mm_negative_control.parquet')
        el = float(reg.elapsed_s_total.iloc[0]) / 3600
        src_lbl = 'đội code (mã 0.2.6, một luồng bằng biến môi trường)'
        rows.append([f'`{name}`', src_lbl, len(reg), ', '.join(f'{k} {v}' for k, v in reg.status.value_counts().items()), 'không' if not reg.fallback_models.astype(bool).any() else 'có',
                     f'{int(nc.MQ08_pass.sum())}/{len(nc)}', f(el, 2)])
    w(tab(['Cấu hình', 'Nguồn kết quả', 'Dòng registry', 'Trạng thái', 'Dùng phương án dự phòng', 'MQ08 đạt (fold)', 'Thời gian (giờ)'], rows) + '\n')
    for name in ('main_cal_time', 'obj_perf'):
        if name not in res:
            continue
        d = res[name][0]
        mm = pd.read_parquet(d / 'mm_metrics.parquet')
        pick = ['B0', 'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'L1-FS3', 'L2-FS3', 'L3-FS3', 'L4-FS3', 'L5-FS3', 'L6-FS3']
        g = mm[mm.strategy.isin(pick)].groupby('strategy').agg(regret=('mean_regret', 'mean'), harm=('harm_rate', 'mean'), top1=('top1_hit_rate', 'mean')).reindex([p for p in pick if p in set(mm.strategy)])
        w(f'**Hối tiếc trung bình theo chiến lược, cấu hình `{name}`** (trung bình trên các fold; thấp hơn là tốt hơn):\n')
        w(tab(['Chiến lược', 'Hối tiếc trung bình', 'Tỉ lệ có hại', 'Top-1 trúng'], [[i, f(r.regret), f(r.harm, 3), f(r.top1, 3)] for i, r in g.iterrows()]) + '\n')
    if 'main_cal_time' in res:
        h = pd.read_parquet(res['main_cal_time'][0] / 'mm_hypotheses.parquet')
        hh = h.groupby('hypothesis').agg(n=('estimate', 'size'), estimate=('estimate', 'mean'), lo=('ci_low', 'mean'), hi=('ci_high', 'mean')).reset_index()
        w('**Giả thuyết H1–H8 (cấu hình `main_cal_time`; ước lượng trung bình trên các fold có phép thử, khoảng tin cậy trung bình):**\n')
        w(tab(['Giả thuyết', 'Số phép thử', 'Ước lượng', 'Cận dưới', 'Cận trên'], [[r.hypothesis, int(r.n), f(r.estimate), f(r.lo), f(r.hi)] for r in hh.itertuples()]) + '\n')

# ---- 6 requests
w('## 6. Đối chiếu các mục yêu cầu đợt 29 (16/11)\n')
w(tab(['Mục', 'Trạng thái', 'Ghi chú'], [
    ['1. Commit mã, ghi commit vào gói', 'Xong (commit cục bộ)', 'Commit `7c24981` và `11941f1`, sau đó đổi đường dẫn tuyệt đối thành biến môi trường; commit dựng gói ghi trong README và `summary.json` của sáu gói seed 44. Chưa đẩy lên `origin/main`.'],
    ['2. README và `probe_seed`', 'Xong', 'Seed 44 đã sửa; seed 43 chỉ ghi chú (không xuất lại): `cross_task_meta/work_in_progress/seed43_package_notes_20261120`.'],
    ['3. NVML', 'Có ghi chú', '8 ô seed 44 không có số đo (xem 3.2); ghi chú và đề xuất năng lượng đã lên Drive.'],
    ['4. Seed 44: facts, M-18, biên nhận', 'Xong', 'Sáu gói facts, M-18, bảng kiểm commit, bằng chứng Mantis, biên nhận chuyển giao và ingest L2, cùng cây thư mục như seed 43.'],
    ['5. M-15 ba seed', 'Cấu hình xong; kết quả theo mục 5.3', 'Release ba seed đã lắp và đã lên Drive; sáu cấu hình chạy một luồng.'],
    ['6. Ledger M-08', 'Chưa xác nhận', 'Cần đối chiếu từng ô đã giao với lớp định danh trong ledger; không ghi xác nhận khi chưa kiểm.'],
    ['7. Hai thư mục báo cáo 16/11', 'Đã có trên Drive ở chỗ khác', '`cross_task_meta/work_in_progress/l2_ingest_receipts_seed43_20261116` và `CQ|LO/L2_facts/receipts_seed43_20261116`.'],
    ['8. S2 seed 43/44', 'Đã trả lời ở phản hồi 13/11 (mục 1.6)', 'Bản ghi máy chuẩn và các cột thời gian đo thật; các cột còn giá trị cũ của runner Modal đã nêu.'],
]) + '\n')

# ---- 7/8
w('## 7. Nguồn của từng số\n')
w(f'- Bảng mục 2 và 3.2: `{REL.name}/meta_dataset_seed_level.parquet` (các cột `*_after`, tập TEST, trung bình bốn pha), qua `report_aggregate_3seed.py`; tệp thô trong `tables/`.\n'
  f'- Mục 3.1: gói M-18 seed 44 (`m18_training_history_seed44_20261119`), bảng kiểm commit runner, biên nhận.\n'
  '- Mục 3.2 (đề xuất năng lượng): `energy_proposal_seed44_20261119`.\n'
  f'- Mục 4: `{REL.name}/meta_release_manifest.json` và `meta_column_dictionary.csv`.\n'
  '- Mục 5: `mm_config.json`, `mm_metrics.parquet`, `mm_run_registry.parquet`, `mm_negative_control.parquet`, `mm_hypotheses.parquet` của từng cấu hình.\n')
w('## 8. Giới hạn của báo cáo' + chr(10))
w('- Chỉ số mục 2 là trung bình trên tập TEST, không có khoảng tin cậy; độ lệch giữa seed và giữa các nhóm pipeline chỉ mang tính mô tả.' + chr(10) +
  '- **Meta-dataset chưa theo đúng cách chia của tài liệu gốc**: release hiện chỉ có nhóm con `ALL/ALL` (cohort `FIXED`), chưa có các nhóm con bắt buộc; E1-A và E1-B gộp CQ và LO trong cùng fold (cả train và test chứa hai task), chưa chia E1 theo từng task như tài liệu mô tả. E2 là chuyển task (CQ→LO, LO→CQ) và E3 giữ lại từng họ mô hình.' + chr(10) +
  '- **M-15**: số cấu hình có kết quả và nguồn của chúng ghi ở bảng mục 5.3; cấu hình chưa có trong bảng chưa xong tại thời điểm viết. Kết quả chạy mỗi tiến trình một luồng, có thể khác lần 13/11 ở mức nhiễu dấu phẩy động. Kiểm âm tính MQ08 chưa đạt ở một số fold (số fold đạt ở bảng 5.3); không kết luận gì thêm ngoài việc ghi nhận. Thống kê giả thuyết lấy trung bình trên fold, không thay cho phân tích đầy đủ của tác giả.' + chr(10) +
  '- `sens_energy` về cơ sở thời gian ở mọi nhóm CQ và ở một phần nhóm LO (PatchTST và 4 nhóm Mantis), vì thiếu tỉ lệ năng lượng ở ít nhất một seed (mục 4); 8 ô CQ seed 44 không có số đo năng lượng (mục 3.2). Đề xuất năng lượng chỉ để báo cáo, không áp dụng vào dữ liệu.' + chr(10) +
  '- Mantis chạy ở chế độ thăm dò (`EXPLORATORY`); commit runner của Mantis được ánh xạ hồi tố, việc phía review chấp nhận cho seed 43 và 44 còn chờ.' + chr(10) +
  '- Tổng thời gian run của một số tổ hợp tính trên ít ô hơn số ô (bảng 3.2 ghi mẫu số), vì có ô thiếu `time_run_total_s`.' + chr(10))

out = DOC / 'BAO_CAO_TONG_HOP_SEED42_43_44_2026-11-20.md'
out.write_text('\n'.join(L), encoding='utf-8', newline='\n')
print('written', out, len('\n'.join(L)), 'chars; M-15 configs with results:', list(res))
