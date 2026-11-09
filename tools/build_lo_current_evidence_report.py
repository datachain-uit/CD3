"""Create the current LO evidence report without overstating incomplete runs.

The historical all-family fact export remains the only source for performance
claims in this report.  The later NVML campaign is listed separately so that
completed-but-not-yet-audited/downloaded runs cannot be mixed into results.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from docx import Document
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "LO/resuilt/lo_recurrent_allfamilies_grid_r2_20261021"
SOURCE = ROOT / "LO/docs/REPORT_LO_TONG_HOP_HOAN_CHINH_SEED42_2026-10-21.docx"
TARGET = ROOT / "LO/docs/REPORT_LO_CURRENT_EVIDENCE_SEED42_2026-10-25.docx"
NVML = ROOT / "LO/resuilt/lo_nvml_historical_layout_seed42_20261023_complete/lo_nvml_historical_layout_seed42"
PREFIX = ROOT / "LO/resuilt/audit_prefix_validation_alignment_v1-20261016T105149Z-1-001/audit_prefix_validation_alignment_v1/summary.json"


def add_text(doc: Document, text: str, size: float = 9.5) -> None:
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    run.font.size = Pt(size)


def add_table(doc: Document, frame: pd.DataFrame, columns: list[tuple[str, str]]) -> None:
    table = doc.add_table(rows=1, cols=len(columns))
    table.style = "Table Grid"
    for cell, (_, label) in zip(table.rows[0].cells, columns):
        cell.text = label
    for _, row in frame.iterrows():
        cells = table.add_row().cells
        for cell, (name, _) in zip(cells, columns):
            value = row[name]
            if pd.isna(value):
                value = ""
            elif isinstance(value, float):
                value = f"{value:.4f}"
            cell.text = str(value)
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(10)


def local_run_count(model: str) -> int:
    return len(list(NVML.glob(f"LO/*/*/{model}/seed=42/run_manifest.json")))


def main() -> None:
    summary = json.loads((FACTS / "summary.json").read_text(encoding="utf-8"))
    prefix = json.loads(PREFIX.read_text(encoding="utf-8"))
    cells = pd.read_parquet(FACTS / "lo_family_pipeline_window_phase_metrics.parquet")
    doc = Document(SOURCE)
    doc.add_page_break()
    doc.add_heading("CẬP NHẬT EVIDENCE LO — 25/10/2026", level=1)
    add_text(doc, "Bổ sung này tách nghiêm ngặt hai phạm vi: (i) lưới historical-layout đã có facts/audit hoàn chỉnh, là nguồn duy nhất cho các bảng hiệu năng; và (ii) campaign VastAI NVML batch 2.048 mới, chỉ ghi trạng thái thực thi cho đến khi artifacts được tải và audit hậu kiểm.")

    doc.add_heading("1. Phạm vi kết quả đủ điều kiện diễn giải", level=2)
    add_table(doc, pd.DataFrame([{
        "Release": "LO_V3_1 clean-grain",
        "Seed": 42,
        "Pipelines": "V0–V16",
        "Windows": "W1–W3",
        "Phases": "P1–P4",
        "Families": ", ".join(summary["families"]),
        "Evaluation cells": summary["evaluation_cells"],
        "Resource runs": summary["resource_runs"],
        "Prediction files": summary["prediction_grain_files"],
    }]), [(key, key) for key in ("Release", "Seed", "Pipelines", "Windows", "Phases", "Families", "Evaluation cells", "Resource runs", "Prediction files")])
    add_text(doc, "Các facts historical-layout đã kiểm tra prediction grain và STRICT/OVERLAP partition. AccTEMPO là metric hiệu năng chính; Macro-F1, balanced accuracy, recall từng lớp và sáu thành phần sanity được trình bày để tránh diễn giải accuracy cao như hiệu năng tốt trong bối cảnh LO mất cân bằng nhãn mạnh.")

    doc.add_heading("2. Bảng tổng hợp đầy đủ family × pipeline", level=2)
    add_text(doc, "Mỗi hàng dưới đây là trung bình 12 cell window × phase trong cùng split. Các bảng chi tiết 204 hàng/family/split theo window × phase vẫn nằm trong phần trước của cùng tài liệu.")
    aggregate = (cells.groupby(["eval_split", "model_name", "pipeline_id"], as_index=False)
                 .agg(acctempo_m3=("acctempo_m3", "mean"), macro_f1=("macro_f1", "mean"),
                      balanced_acc=("balanced_acc", "mean"), s_ent=("s_ent", "mean"),
                      s_san_plus=("s_san_plus", "mean"), strict_share=("strict_share", "mean"),
                      recall_id=("c0_recall", "mean"), recall_g=("c1_recall", "mean"), recall_e=("c2_recall", "mean")))
    order = {f"V{i}": i for i in range(17)}
    aggregate["_order"] = aggregate.pipeline_id.map(order)
    for split in ("TEST", "VALIDATION"):
        doc.add_heading(f"{split} — 68 cấu hình", level=3)
        table = aggregate[aggregate.eval_split.eq(split)].sort_values(["model_name", "_order"]).drop(columns="_order")
        add_table(doc, table, [("model_name", "Family"), ("pipeline_id", "Pipeline"), ("acctempo_m3", "AccTEMPO"), ("macro_f1", "Macro-F1"), ("balanced_acc", "Balanced acc."), ("s_ent", "s_ent"), ("s_san_plus", "S_san+"), ("strict_share", "STRICT"), ("recall_id", "Recall I/D"), ("recall_g", "Recall G"), ("recall_e", "Recall E")])

    doc.add_page_break()
    doc.add_heading("3. Kiểm chứng prefix, static và grain", level=2)
    add_table(doc, pd.DataFrame([{
        "Layout signatures": prefix["layout_signature_count"],
        "Static columns": prefix["static_column_count"],
        "Future prefix mask": "Đạt" if prefix["prefix_future_mask_all_samples_ok"] else "Không đạt",
        "Test static parity": "Đạt" if prefix["test_static_prefix_parity_ok"] else "Không đạt",
        "Manual static review": prefix["static_columns_requiring_manual_review"],
        "W1/P1 prediction cells": prefix["w1_p1_prediction_cells"],
    }]), [(key, key) for key in ("Layout signatures", "Static columns", "Future prefix mask", "Test static parity", "Manual static review", "W1/P1 prediction cells")])
    add_text(doc, "Audit xác nhận không có future dynamic value lộ vào TEST prefix và static values giữ parity giữa P1–P4. Tuy nhiên 15 cột static vẫn cần phê duyệt khoa học về thời điểm sẵn có; audit kỹ thuật không tự kết luận causal leakage chỉ từ tên cột.")

    doc.add_heading("4. Campaign VastAI NVML batch 2.048 — trạng thái tách biệt", level=2)
    bilstm_audit_root = ROOT / "LO/resuilt/lo_bilstm_nvml_audited_seed42_20261025/audits_seed42/LO/BILSTM/seed=42"
    bilstm_manifest = json.loads((bilstm_audit_root / "audit_manifest.json").read_text(encoding="utf-8"))
    bilstm_sanity = pd.read_parquet(bilstm_audit_root / "sanity_components.parquet")
    bilstm_run_root = ROOT / "LO/resuilt/lo_bilstm_nvml_audited_seed42_20261025/lo_bilstm_historical_layout_seed42"
    bilstm_runs = len(list(bilstm_run_root.glob("LO/*/*/BILSTM/seed=42/run_manifest.json")))
    current = pd.DataFrame([
        {"Family": "RNN", "Run manifests local": local_run_count("RNN"), "Expected": 51, "Audit local": "Đủ facts hậu kiểm", "Đưa vào bảng primary": "Chưa thay historical facts"},
        {"Family": "LSTM", "Run manifests local": local_run_count("LSTM"), "Expected": 51, "Audit local": "Đủ facts hậu kiểm", "Đưa vào bảng primary": "Chưa thay historical facts"},
        {"Family": "GRU", "Run manifests local": local_run_count("GRU"), "Expected": 51, "Audit local": "Chưa tải/audit đủ 51", "Đưa vào bảng primary": "Không"},
        {"Family": "BiLSTM", "Run manifests local": bilstm_runs, "Expected": 51, "Audit local": "Đủ facts hậu kiểm", "Đưa vào bảng primary": "Có, facts NVML audited"},
    ])
    add_table(doc, current, [(col, col) for col in current.columns])
    add_text(doc, "Campaign NVML ghi batch 2.048, GPU NVIDIA L4 và energy_measurement_type = NVML_POWER_SAMPLING_ESTIMATE trong từng manifest. BiLSTM đã đủ artifacts và audit hậu kiểm; GRU vẫn chưa tải/audit đủ 51. Vì vậy chỉ facts BiLSTM dưới đây được cập nhật bằng campaign NVML.")

    doc.add_heading("4.1 BiLSTM NVML batch 2.048 — facts đã audit", level=3)
    add_table(doc, pd.DataFrame([{
        "Runs": bilstm_manifest["runs"],
        "Bootstrap repetitions": bilstm_manifest["bootstrap_repetitions"],
        "Sanity rows": bilstm_manifest["rows"]["sanity_components"],
        "Canonical S_leak rows": bilstm_manifest["rows"]["canonical_s_leak"],
        "Slice rows": bilstm_manifest["rows"]["evaluation_slices"],
        "Per-class rows": bilstm_manifest["rows"]["metrics_per_class"],
        "Checkpoint rows": bilstm_manifest["rows"]["checkpoint_selection"],
    }]), [(key, key) for key in ("Runs", "Bootstrap repetitions", "Sanity rows", "Canonical S_leak rows", "Slice rows", "Per-class rows", "Checkpoint rows")])
    bilstm_summary = (bilstm_sanity.groupby(["eval_split", "pipeline_id"], as_index=False)
                      .agg(acctempo_m3=("acctempo_m3", "mean"), macro_f1=("macro_f1", "mean"),
                           balanced_acc=("balanced_acc", "mean"), s_san_plus=("s_san_plus", "mean"),
                           s_ent=("s_ent", "mean"), s_leak=("s_leak", "mean"),
                           recall_id=("c0_recall", "mean"), recall_g=("c1_recall", "mean"), recall_e=("c2_recall", "mean")))
    bilstm_summary["_order"] = bilstm_summary.pipeline_id.map(order)
    for split in ("TEST", "VALIDATION"):
        doc.add_heading(f"BiLSTM NVML — {split}, trung bình W1–W3 × P1–P4", level=4)
        add_table(doc, bilstm_summary[bilstm_summary.eval_split.eq(split)].sort_values("_order").drop(columns="_order"), [
            ("pipeline_id", "Pipeline"), ("acctempo_m3", "AccTEMPO"), ("macro_f1", "Macro-F1"),
            ("balanced_acc", "Balanced acc."), ("s_san_plus", "S_san+"), ("s_ent", "s_ent"),
            ("s_leak", "s_leak"), ("recall_id", "Recall I/D"), ("recall_g", "Recall G"), ("recall_e", "Recall E"),
        ])

    doc.add_heading("5. Kết luận vận hành", level=2)
    add_text(doc, "Báo cáo có đủ bằng chứng historical-layout để mô tả đầy đủ grid 4 family × 17 pipeline × 3 window × 4 phase × TEST/VALIDATION. Campaign NVML đã đóng facts BiLSTM nhưng GRU chưa tải/audit đủ 51, nên không gộp GRU NVML vào kết luận. Việc tiếp theo là tải GRU, chạy audit cùng hợp đồng, rồi materialize L2 để xuất revision batch-2.048 hoàn toàn đồng nhất.")
    doc.save(TARGET)
    print(TARGET)


if __name__ == "__main__":
    main()
