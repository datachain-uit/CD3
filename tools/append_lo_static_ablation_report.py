"""Append a descriptive seed-42 static ablation to the current LO report."""
from pathlib import Path
import pandas as pd
from docx import Document

root = Path(__file__).resolve().parents[1]
source = root / 'LO/docs/REPORT_LO_TONG_HOP_DAY_DU_SEED42_2026-10-19_REVIEW.docx'
dest = root / 'LO/docs/REPORT_LO_TONG_HOP_DAY_DU_SEED42_2026-10-19_ABLATION.docx'
data = pd.read_csv(root / 'LO/resuilt/lo_static_ablation_20261019/ablation_comparison.csv')
doc = Document(source)
doc.add_paragraph('Bổ sung: ablation nhánh static LO W1, LSTM seed 42')
doc.add_paragraph('Pilot so sánh V0 và V8, batch 2.048, L4. Đối chứng là checkpoint lịch sử có static đầy đủ; hai run mới lần lượt bỏ toàn bộ static/mask static và giữ gender + window_duration_seconds cùng mask của duration. Dynamic và mask động được kiểm tra khớp layout lịch sử. Bảng P1 dưới đây là mô tả từng cell; toàn bộ P1–P4 trong ablation_comparison.csv.')
cols = ['pipeline_id', 'variant', 'split', 'macro_f1', 'balanced_acc', 'recall_c1', 'recall_c2', 'best_epoch']
table = doc.add_table(rows=1, cols=len(cols)); table.style = 'Table Grid'
for cell, title in zip(table.rows[0].cells, ['V', 'Cấu hình', 'Split', 'Macro-F1', 'Bal. acc.', 'Recall G', 'Recall E', 'Epoch chọn']): cell.text = title
for _, row in data[data.phase == 'P1'].iterrows():
    for cell, col in zip(table.add_row().cells, cols):
        cell.text = f'{row[col]:.4f}' if col in ('macro_f1', 'balanced_acc', 'recall_c1', 'recall_c2') else str(row[col])
doc.add_paragraph('V0 bỏ static không làm validation P1 giảm so với baseline; V8 có giảm. Các test P1 thay đổi ít theo Macro-F1 trong pilot này và recall E vẫn bằng 0. Kết quả chưa đủ để xác nhận nhánh static gây validation lạc quan hoặc chốt chính sách cho mọi V/model: chỉ một seed, một window, một model; số epoch được chọn có thể khác, và baseline được train trong lần trước với môi trường và code khác. Cần so sánh đầy đủ theo P1–P4 và diễn giải support lớp E.')
doc.add_paragraph('Bốn run được tải về và 52 file khớp SHA-256 với VastAI. Chúng là thử nghiệm thăm dò tách khỏi grid/L2 chính, không phải các cell thay thế. Prediction dùng salt mới riêng cho ablation, không dùng để khẳng định đã ghép hash với các run lịch sử.')
audit_path = root / 'LO/resuilt/lo_prediction_grain_20261019/file_audit.csv'
if audit_path.exists():
    audit = pd.read_csv(audit_path, keep_default_na=False)
    problems = sum((pd.to_numeric(audit[col], errors='coerce').fillna(0) > 0).sum() for col in ('null_id', 'duplicate_rows', 'null_or_invalid_flag'))
    doc.add_paragraph(f"Kiểm tra prediction LO lịch sử: đã quét {len(audit):,}/1.632 file; số file lỗi đọc {audit['error'].ne('').sum()}, số lượt vi phạm hash null/trùng hoặc cờ STRICT active null/không hợp lệ {problems}. Chi tiết tại LO/resuilt/lo_prediction_grain_20261019/file_audit.csv. Kết quả này không thay thế ghép SEEN/UNSEEN với STRICT/OVERLAP, cần salt gốc.")
cohort_path = root / 'LO/resuilt/lo_static_ablation_20261019/ablation_seen_course_x_strict.csv'
if cohort_path.exists():
    cohort = pd.read_csv(cohort_path)
    doc.add_paragraph(f"Đã ghép bằng salt riêng, xác nhận hash một-một và nhãn đúng cho 32 prediction file của bốn run ablation; xuất {len(cohort)} lát giao nhau SEEN_COURSE/UNSEEN_COURSE × STRICT/OVERLAP. SEEN_COURSE nghĩa là course_id từng xuất hiện trong TRAIN thật của parent, không đồng nghĩa đã thấy offering. Tất cả {int(cohort.small_support_flag.sum())}/{len(cohort)} lát có ít nhất một lớp support dưới 400 hoặc vắng lớp, nên chỉ xem mô tả. Việc ghép này không áp dụng cho run lịch sử dùng salt khác.")
doc.save(dest)
print(dest)
