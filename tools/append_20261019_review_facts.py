"""Append 19 October window/phase and slice evidence to existing CQ/LO reports."""
import json
from pathlib import Path

import pandas as pd
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
for task in ('CQ', 'LO'):
    source = ROOT / task / 'docs' / f'REPORT_{task}_TONG_HOP_DAY_DU_SEED42_2026-10-19.docx'
    out = ROOT / task / 'docs' / f'REPORT_{task}_TONG_HOP_DAY_DU_SEED42_2026-10-19_REVIEW.docx'
    evidence_name = 'review_20261019_window_phase_r2' if task == 'LO' else 'review_20261019_window_phase'
    evidence = ROOT / task / 'resuilt' / evidence_name
    data = pd.read_parquet(evidence / 'sanity_long.parquet')
    checks = pd.read_csv(evidence / 'slice_partition_and_strict_share.csv')
    receipt = json.loads((evidence / 'review_receipt.json').read_text(encoding='utf-8'))
    doc = Document(source)
    doc.add_paragraph('Bổ sung: đối chiếu review 19/10')
    doc.add_paragraph(f'Số liệu seed 42, batch 2.048; bảng dưới là trung bình 17 pipeline trong cùng họ, window, pha và split; chỉ dùng để mô tả, không phải xếp hạng hay kết luận nhân quả. Bảng chi tiết đủ 17 pipeline và từng window/pha lưu tại resuilt/{evidence_name}/tables.')
    if task == 'CQ':
        data = data[(data.window_id == 'W2') & (data.eval_split == 'TEST')]
        title = 'CQ W2 TEST: tách hiệu năng, entropy và AccTEMPO'
    else:
        data = data[data.window_id == 'W1']
        title = 'LO W1: VALIDATION (B) và TEST (C), theo tiền tố'
    doc.add_paragraph(title)
    cols = ['model_name', 'eval_split', 'phase_id', 'acctempo_m3', 'macro_f1', 'balanced_acc', 's_ent', 'c0_recall', 'c1_recall', 'c2_recall']
    values = data[cols].groupby(cols[:3], as_index=False).mean(numeric_only=True)
    table = doc.add_table(rows=1, cols=len(cols)); table.style = 'Table Grid'
    for c, name in zip(table.rows[0].cells, ['Họ', 'Split', 'P', 'AccTEMPO', 'Macro-F1', 'Bal.acc', 's_ent', 'Recall c0', 'Recall c1', 'Recall c2']): c.text = name
    for _, row in values.iterrows():
        for cell, name in zip(table.add_row().cells, cols):
            cell.text = str(row[name]) if name in cols[:3] else f'{row[name]:.4f}'
    doc.add_paragraph('CQ c0/c1/c2 = warning/average/good; LO c0/c1/c2 = I/D/G/E. Recall trung bình các pipeline, không phải recall gộp dự đoán. s_ent là thành phần entropy dự đoán, không phải chỉ số chất lượng dữ liệu thô.')
    doc.add_paragraph('Kiểm tra phân hoạch STRICT và OVERLAP')
    doc.add_paragraph(f"Kiểm tra {receipt['partition_cells']:,} ô split × window × phase × pipeline × model: {receipt['partition_violations']} vi phạm tổng ma trận nhầm lẫn; chi tiết số mẫu và tỷ lệ STRICT trong slice_partition_and_strict_share.csv. Kiểm tra ở mức facts không xác nhận riêng khóa prediction duy nhất hoặc cờ thời gian không null.")
    if task == 'LO':
        doc.add_paragraph(f"Facts LO theo lát đã tính lại s_drift, s_eff, s_leak và các composite theo hợp đồng parent-imputer, từ ma trận nhầm lẫn và thống kê slice đã lưu; không train lại hoặc đọc lại toàn bộ prediction. AccTEMPO của ALL khớp sanity tối đa {receipt['all_slice_max_abs_diff']['acctempo_m3']:.2e}; Macro-F1 và balanced accuracy cũng khớp. Facts cũ giữ nguyên để truy vết. Facts r2 đã nhập và kiểm tra đọc độc lập tại L2 với ingest_id vastai_lo_f2_seed42_slice_parent_r2_20261019: 204 contract, 1.632 sanity, 4.896 lát và 0 vi phạm phân hoạch.")
    else:
        shares = checks[(checks.window_id == 'W2') & (checks.eval_split == 'TEST')].groupby('phase_id').strict_share.agg(['min', 'max'])
        doc.add_paragraph('Tỷ lệ STRICT W2 TEST theo pha (min–max qua họ/pipeline): ' + '; '.join(f'{p}: {v["min"]:.2%}–{v["max"]:.2%}' for p, v in shares.iterrows()) + '.')
        doc.add_paragraph('Các run recurrent CQ 2.048 có 153/153 manifest ghi ước lượng NVML; ước lượng GPU-only, không suy ra CO₂. Không áp dụng xác nhận này cho RNN Modal hoặc các run khác.')
    doc.save(out)
    print(out)
