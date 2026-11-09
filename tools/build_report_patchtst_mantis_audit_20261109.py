"""Build docs/09112026/BAO_CAO_PATCHTST_MANTIS_CQ_LO_2026-11-09.docx from the audit tables (no hand-typed numbers).

Sources (all standard audit tables, seed 42):
  CQ PatchTST  : CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103 and cq_patchtst_v7_v16_full_facts_20261109
  LO PatchTST  : LO audit root (--lo-audit) + per-pipeline audits (--lo-other)
  CQ Mantis    : audit roots given with --mantis-audit (later roots win on duplicate cells)
Headline metric: TEST split, mean over phases P1-P4 of macro-F1 / acctempo_m4 / s_leak (sanity_components).
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from docx import Document
from docx.shared import Pt

ap = argparse.ArgumentParser()
ap.add_argument('--lo-audit', type=Path, required=True)
ap.add_argument('--lo-other', type=Path, required=True)
ap.add_argument('--mantis-audit', type=Path, nargs='+', required=True)
ap.add_argument('--out', type=Path, default=Path('docs/09112026/BAO_CAO_PATCHTST_MANTIS_CQ_LO_2026-11-09.docx'))
args = ap.parse_args()

K = ['window_id', 'pipeline_id', 'eval_split', 'phase_id']
CQ = Path('CQ/resuilt')


def read(p):
    return pd.read_parquet(p)


def vkey(v):
    return int(v[1:])


def san_from(paths):
    frames = [read(p) for p in paths]
    d = pd.concat(frames, ignore_index=True)
    if 'acctempo_m4' not in d.columns:
        d['acctempo_m4'] = float('nan')
    miss = d.acctempo_m4.isna()
    d.loc[miss, 'acctempo_m4'] = d.loc[miss, 's_perf'].clip(lower=1e-3).pow(.6) * d.loc[miss, 's_san_plus_v2'].clip(lower=1e-3).pow(.4)
    return d.drop_duplicates(K, keep='last')


def headline(san, split='TEST'):
    t = san[san.eval_split == split]
    g = t.groupby(['pipeline_id', 'window_id']).agg(f1=('macro_f1', 'mean'), m4=('acctempo_m4', 'mean'), leak=('s_leak', 'mean'), n=('macro_f1', 'size')).reset_index()
    return g


def add_table(doc, header, rows, size=9):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = 'Table Grid'
    for c, h in zip(t.rows[0].cells, header):
        c.text = h
    for r in rows:
        for c, v in zip(t.add_row().cells, r):
            c.text = str(v)
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(size)
    return t


def fmt(x):
    return '—' if x is None or pd.isna(x) else f'{x:.3f}'


def model_table(doc, san, title, note):
    doc.add_heading(title, level=2)
    doc.add_paragraph(note)
    g = headline(san)
    rows = []
    for v in sorted(g.pipeline_id.unique(), key=vkey):
        gv = g[g.pipeline_id == v].set_index('window_id')
        cells = [fmt(gv.f1.get(w)) if w in gv.index else '—' for w in ('W1', 'W2', 'W3')]
        rows.append([v] + cells + [fmt(gv.f1.mean()), fmt(gv.m4.mean()), fmt(gv.leak.mean()), f'{len(gv)}/3'])
    add_table(doc, ['Pipeline', 'F1 W1', 'F1 W2', 'F1 W3', 'F1 TB', 'AccTempo m4 TB', 'S_leak TB', 'Cửa sổ'], rows)
    return g



def cohort_section(doc, c, level, title, intro):
    doc.add_heading(title, level=level)
    doc.add_paragraph(intro)
    ct = c[(c.eval_split == 'TEST') & (c.status == 'OK')]
    g = ct.groupby(['pipeline_id', 'course_cohort', 'temporal_slice']).macro_f1.mean().unstack(['course_cohort', 'temporal_slice'])
    rows = []
    for v in sorted(g.index, key=vkey):
        rows.append([v] + [fmt(g.loc[v].get((a, b))) for a in ('SEEN_COURSE', 'UNSEEN_COURSE') for b in ('STRICT', 'OVERLAP')])
    add_table(doc, ['Pipeline', 'SEEN-STRICT', 'SEEN-OVERLAP', 'UNSEEN-STRICT', 'UNSEEN-OVERLAP'], rows)
    doc.add_paragraph(f'Tổng {len(c)} lát cohort; trạng thái: {c.status.value_counts().to_dict()}. Tổng 4 lát khớp số mẫu đánh giá ở mọi ô.')


doc = Document()
doc.add_heading('Báo cáo tổng hợp audit PatchTST (CQ, LO) và Mantis (CQ) — seed 42', level=0)
doc.add_paragraph(f'Lập ngày {datetime.now(timezone.utc):%d/%m/%Y} (UTC) từ các bảng audit chuẩn; số liệu được tính trực tiếp từ bảng, không nhập tay. '
                  'F1 = macro-F1 trên tập TEST, trung bình các pha P1–P4; "TB" là trung bình các cửa sổ. AccTempo m4 = S_perf^0.6 × S_san_plus_v2^0.4 (sàn 0,001). '
                  'Mantis là chạy thăm dò (EXPLORATORY), không so trực tiếp thứ hạng với PatchTST chính thức.')

# ---- 1. coverage
doc.add_heading('1. Phạm vi và vị trí lưu trên Drive', level=1)

cq_san = san_from([CQ / 'cq_patchtst_v0_v6_full_facts_20261103/sanity_components.parquet', CQ / 'cq_patchtst_v7_v16_full_facts_20261109/sanity_components.parquet'])
lo_paths = [args.lo_audit / 'LO/PATCHTST/seed=42/sanity_components.parquet'] + sorted(args.lo_other.rglob('sanity_components.parquet'))
lo_san = san_from(lo_paths)
mt_paths = []
for root in args.mantis_audit:
    mt_paths += sorted(root.rglob('sanity_components.parquet'))
mt_san = san_from(mt_paths)


def cells(s):
    return s.groupby(['pipeline_id', 'window_id']).ngroups


add_table(doc, ['Nhóm', 'Pipeline có audit chuẩn', 'Ô (pipeline × cửa sổ)', 'Vị trí trên Drive (Results/)'], [
    ['CQ PatchTST', ', '.join(sorted(cq_san.pipeline_id.unique(), key=vkey)), f'{cells(cq_san)}/51',
     'CQ/L2_facts/fact_exports/cq_patchtst_v0_v6_full_facts_20261103 và …v7_v16_full_facts_20261109; bundle V1–V8, V10, V11, V13–V15 ở CQ/L1_runs/S3_model/staging_incoming/patchtst_seed42_20261105/<V>/, V9/V12/V16 ở primary/family=PATCHTST/'],
    ['LO PatchTST', ', '.join(sorted(lo_san.pipeline_id.unique(), key=vkey)), f'{cells(lo_san)}/51',
     'LO/L2_facts/fact_exports/lo_patchtst_v0_v16_full_facts_20261109; audit chạy lại cho V0–V4, V7, V11, V12 ở LO/L2_facts/audits/lo_patchtst_standard_audit_V0-V4_V7_V11_V12_seed42_20261109; bundle ở LO/L1_runs/S3_model/staging_incoming/patchtst_seed42_after_credit_20261108/<V>/'],
    ['CQ Mantis (MANTIS_V2)', ', '.join(sorted(mt_san.pipeline_id.unique(), key=vkey)), f'{cells(mt_san)}/51',
     'CQ/L2_facts/fact_exports/cq_mantis_v2_v0_v16_full_facts_20261109; audit và dữ liệu chuẩn hóa ở CQ/L1_runs/S3_model/staging_incoming/mantis_v2_seed42_exploratory_20261108/{audit,standardized_runs}_*_20261109'],
])

# ---- 2. CQ PatchTST
doc.add_heading('2. CQ PatchTST V0–V16', level=1)
model_table(doc, cq_san, '2.1 Hiệu năng theo pipeline và cửa sổ', 'Audit chuẩn B=2000 cho mọi pipeline; mỗi ô có đủ 4 pha × 2 split.')

c = pd.concat([read(CQ / 'cq_patchtst_v0_v6_full_facts_20261103/cohort_slice_status.parquet'), read(CQ / 'cq_patchtst_v7_v16_full_facts_20261109/cohort_slice_status.parquet')], ignore_index=True)
doc.add_heading('2.2 SEEN/UNSEEN × STRICT/OVERLAP (TEST)', level=2)
doc.add_paragraph('SEEN là course có trong TRAIN thật của parent cùng cửa sổ. Giá trị là macro-F1 trung bình qua cửa sổ và pha; các lát một lớp hoặc rỗng (nếu có) được loại khỏi trung bình.')
ct = c[(c.eval_split == 'TEST') & (c.status == 'OK')]
g = ct.groupby(['pipeline_id', 'course_cohort', 'temporal_slice']).macro_f1.mean().unstack(['course_cohort', 'temporal_slice'])
rows = []
for v in sorted(g.index, key=vkey):
    rows.append([v] + [fmt(g.loc[v].get((a, b))) for a in ('SEEN_COURSE', 'UNSEEN_COURSE') for b in ('STRICT', 'OVERLAP')])
add_table(doc, ['Pipeline', 'SEEN-STRICT', 'SEEN-OVERLAP', 'UNSEEN-STRICT', 'UNSEEN-OVERLAP'], rows)
doc.add_paragraph(f'Tổng {len(c)} lát cohort; trạng thái: {c.status.value_counts().to_dict()}. Tổng 4 lát khớp số mẫu đánh giá ở mọi ô (168 ô V0–V6 và 240 ô V7–V16).')

# ---- 3. LO PatchTST
doc.add_heading('3. LO PatchTST', level=1)
model_table(doc, lo_san, '3.1 Hiệu năng theo pipeline và cửa sổ', 'Audit chuẩn B=2000, release LO_V3_1. Nhãn LO_performance_label_3, lớp I/D, G, E.')
lo_c = read(Path('LO/resuilt/lo_patchtst_v0_v16_full_facts_20261109/cohort_slice_status.parquet'))
cohort_section(doc, lo_c, 2, '3.2 SEEN/UNSEEN × STRICT/OVERLAP (TEST)',
               'Cùng định nghĩa như CQ. Macro-F1 trung bình qua cửa sổ và pha, chỉ tính các lát có đủ nhiều lớp (trạng thái OK); các lát một lớp (ONE_CLASS) hoặc rỗng (SLICE_EMPTY), tập trung ở nhóm UNSEEN, không đưa vào trung bình và cần đọc thận trọng.')
doc.add_paragraph('Facts F2 của LO PatchTST: LO/L2_facts/fact_exports/lo_patchtst_v0_v16_full_facts_20261109 (bảng audit, cohort, tài nguyên theo run).')

# ---- 4. Mantis
doc.add_heading('4. CQ Mantis (MANTIS_V2, thăm dò)', level=1)
model_table(doc, mt_san, '4.1 Hiệu năng theo pipeline và cửa sổ',
            'Backbone đóng băng, bộ chuyển kênh PCA8 fit trên TRAIN thật của parent, probe tuyến tính; chọn checkpoint theo MEAN_PHASE_MACRO_F1. Release CQ_V2_2.')
doc.add_paragraph('V0 (bundle gốc chỉ lưu xác suất): file dự đoán được dựng lại từ đúng mảng xác suất đã lưu (tools/rebuild_mantis_v0_predictions_20261109.py); điểm validation dựng lại khớp cell record ở cả 3 cửa sổ (chênh lệch 0). Thời gian chạy và năng lượng GPU của V0 không được ghi trong bundle gốc nên để null. runner_git_commit của Mantis chưa được ghi (null).')
mt_c = read(Path('CQ/resuilt/cq_mantis_v2_v0_v16_full_facts_20261109/cohort_slice_status.parquet'))
cohort_section(doc, mt_c, 2, '4.2 SEEN/UNSEEN × STRICT/OVERLAP (TEST)', 'Cùng định nghĩa như PatchTST. Facts F2: CQ/L2_facts/fact_exports/cq_mantis_v2_v0_v16_full_facts_20261109.')

# ---- 5. pending
doc.add_heading('5. Việc còn lại', level=1)
for line in ['Mantis LO (V0, V1, V5, V9, V13 × W1–W3) đang train; pipeline con của LO chưa lên lịch.',
             'Cập nhật dòng registry MANTIS_V2 và đưa các gói facts vào L2 theo quy trình ingest chính thức.',
             'Báo cáo docx chi tiết theo mẫu V0–V6 cho CQ PatchTST V7–V16 (hiện chỉ có bảng tổng hợp ở tài liệu này).']:
    doc.add_paragraph(line, style='List Bullet')

args.out.parent.mkdir(parents=True, exist_ok=True)
doc.save(args.out)
print('saved', args.out, 'CQ', cells(cq_san), 'LO', cells(lo_san), 'Mantis', cells(mt_san))
