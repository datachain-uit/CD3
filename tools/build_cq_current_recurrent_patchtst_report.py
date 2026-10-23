#!/usr/bin/env python3
"""Build the current CQ seed-42 report, including the PatchTST V0 pilot."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
R4 = ROOT / "CQ/resuilt/cq_recurrent_allfamilies_grid_r4_20261023"
PATCH = ROOT / "CQ/resuilt/cq_patchtst_v0_seed42_20261023"
TARGET = ROOT / "CQ/docs/REPORT_CQ_CURRENT_RECURRENT_PATCHTST_V0_SEED42_2026-10-23.docx"


def heading(doc: Document, value: str, size: int = 14) -> None:
    p = doc.add_paragraph()
    r = p.add_run(value)
    r.bold = True
    r.font.size = Pt(size)


def paragraph(doc: Document, value: str) -> None:
    p = doc.add_paragraph(value)
    p.paragraph_format.space_after = Pt(5)
    for r in p.runs:
        r.font.size = Pt(10.5)


def table(doc: Document, frame: pd.DataFrame, cols: list[tuple[str, str]], size: float = 8.5) -> None:
    out = doc.add_table(rows=1, cols=len(cols))
    out.style = "Table Grid"
    for cell, (_, label) in zip(out.rows[0].cells, cols):
        cell.text = label
        for r in cell.paragraphs[0].runs:
            r.bold = True
            r.font.size = Pt(size + .5)
    for _, row in frame.iterrows():
        cells = out.add_row().cells
        for cell, (name, _) in zip(cells, cols):
            value = row.get(name)
            cell.text = "" if pd.isna(value) else (f"{value:.4f}" if isinstance(value, float) else str(value))
            for r in cell.paragraphs[0].runs:
                r.font.size = Pt(size)
    doc.add_paragraph()


def main() -> None:
    required = [R4 / "summary.json", R4 / "cq_family_pipeline_window_phase_metrics.parquet",
                R4 / "cq_qa23_reviewed_behavioural_linkage.parquet",
                PATCH / "audits_v0_seed42/CQ/PATCHTST/seed=42/audit_manifest.json"]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing report inputs: " + ", ".join(missing))

    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(.65)
    section.bottom_margin = Inches(.65)
    section.left_margin = Inches(.7)
    section.right_margin = Inches(.7)
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("BÁO CÁO CQ HIỆN TẠI — RECURRENT GRID VÀ PATCHTST V0")
    run.bold = True
    run.font.size = Pt(18)
    subtitle = doc.add_paragraph("CQ_V2_2 clean-grain · seed 42 · cập nhật 23/10/2026")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in subtitle.runs:
        r.italic = True
        r.font.size = Pt(11)

    summary = json.loads((R4 / "summary.json").read_text(encoding="utf-8"))
    heading(doc, "1. Phạm vi và trạng thái nghiệm thu")
    paragraph(doc, "Phần recurrent hoàn tất bốn họ RNN, LSTM, GRU và BiLSTM trên VastAI L4, batch 2.048: V0–V16, W1–W3, P1–P4, hai split TEST/VALIDATION. PatchTST hiện là pilot riêng chỉ cho V0 trên ba window; nó xác nhận pipeline kiến trúc hoạt động nhưng chưa phải so sánh F2/full-grid.")
    status = pd.DataFrame([
        {"Hạng mục": "Recurrent grid", "Phạm vi": "4 họ × 17 pipeline × 3 W × 4 P × 2 split", "Kết quả": f"{summary['evaluation_cells']:,} cell"},
        {"Hạng mục": "Tài nguyên recurrent", "Phạm vi": "NVIDIA L4 / BF16 / batch 2.048", "Kết quả": f"{summary['resource_runs']:,} manifest; NVML đầy đủ"},
        {"Hạng mục": "Per-class / bootstrap", "Phạm vi": "support, recall, F1; CI B=2.000", "Kết quả": f"{summary['per_class_facts']:,} / {summary['bootstrap_per_class_facts']:,} fact"},
        {"Hạng mục": "PatchTST", "Phạm vi": "V0 × W1–W3 × seed 42", "Kết quả": "3 run; post-hoc audit hoàn tất"},
    ])
    table(doc, status, [("Hạng mục", "Hạng mục"), ("Phạm vi", "Phạm vi"), ("Kết quả", "Kết quả")], 9)

    heading(doc, "2. Quy tắc đọc metric")
    paragraph(doc, "AccTEMPO-M3 v1 vẫn là composite PRIMARY đã tiền đăng ký trong meta-dataset. Khi trình bày xu hướng P1→P4 hoặc xếp hạng trong bài, phải đọc cùng S_perf, Macro-F1 và balanced accuracy; đồng thời báo cáo AccTEMPO-M4 (S_san+ v2 dựa trên s_cal) là sensitivity composite. Lý do: s_ent thường giảm khi dự đoán ở phase muộn chắc chắn hơn, nên M3 có thể giảm dù hiệu năng phân loại tăng. Accuracy không dùng độc lập vì nhãn mất cân bằng.")

    cells = pd.read_parquet(R4 / "cq_family_pipeline_window_phase_metrics.parquet")
    recurrent_mean = (cells.groupby(["model_name", "eval_split"], as_index=False)
                      [["acctempo_m3", "acctempo_m4", "f1_macro", "balanced_accuracy", "s_perf", "s_san_plus", "s_cal"]].mean()
                      .sort_values(["eval_split", "model_name"]))
    heading(doc, "3. Recurrent: trung bình mô tả theo họ")
    paragraph(doc, "Bảng này chỉ mô tả trung bình qua pipeline/window/phase; không thay thế bảng hạt đầy đủ trong package evidence."
    )
    table(doc, recurrent_mean, [("eval_split", "Split"), ("model_name", "Họ"), ("acctempo_m3", "AccTEMPO M3"), ("acctempo_m4", "AccTEMPO M4"), ("f1_macro", "Macro-F1"), ("balanced_accuracy", "Bal. acc."), ("s_perf", "S_perf"), ("s_san_plus", "S_san+ v1"), ("s_cal", "s_cal")])

    rnn_phase = (cells[(cells.model_name == "RNN") & (cells.eval_split == "TEST")]
                 .groupby(["window_id", "phase_id"], as_index=False)[["acctempo_m3", "acctempo_m4", "f1_macro", "balanced_accuracy", "s_ent"]].mean())
    heading(doc, "4. Recurrent: RNN TEST theo window × phase")
    table(doc, rnn_phase, [("window_id", "W"), ("phase_id", "P"), ("acctempo_m3", "M3"), ("acctempo_m4", "M4"), ("f1_macro", "Macro-F1"), ("balanced_accuracy", "Bal. acc."), ("s_ent", "s_ent")])

    qa = pd.read_parquet(R4 / "cq_qa23_reviewed_behavioural_linkage.parquet")
    qa_summary = (qa.groupby("phase_id", as_index=False)
                  .agg(reviewed_bases=("base", "nunique"), reviewed_columns=("column_name", "count"),
                       rho_abs_max=("spearman_abs", "max"), nmi_max=("nmi", "max"),
                       status=("review_status", "first")))
    heading(doc, "5. QA23 — feature/label-proxy")
    paragraph(doc, "Tám behavioural base được giữ với điều kiện chỉ dùng prefix đã quan sát trước cutoff. Chúng có thể tương quan với final label; correlation được công khai thay vì bị coi là label-derived. Trường tạo nhãn final-distance không thuộc predictor contract.")
    table(doc, qa_summary, [("phase_id", "Phase"), ("reviewed_bases", "Base"), ("reviewed_columns", "Cột"), ("rho_abs_max", "|ρ| max"), ("nmi_max", "NMI max"), ("status", "Trạng thái")])

    metrics = pd.concat([pd.read_parquet(PATCH / w / "metrics_overall.parquet") for w in ("W1", "W2", "W3")], ignore_index=True)
    audit_root = PATCH / "audits_v0_seed42/CQ/PATCHTST/seed=42"
    sanity = pd.read_parquet(audit_root / "sanity_components.parquet")
    patch = metrics.merge(sanity[["window_id", "pipeline_id", "seed", "eval_split", "phase_id", "acctempo_m3", "s_perf", "s_san_plus", "s_cal", "s_san_plus_v2", "s_ent", "s_leak"]], on=["window_id", "pipeline_id", "seed", "eval_split", "phase_id"], validate="one_to_one")
    patch["acctempo_m4"] = patch.s_perf.clip(lower=1e-3).pow(.6) * patch.s_san_plus_v2.clip(lower=1e-3).pow(.4)
    heading(doc, "6. PatchTST V0 — kết quả pilot")
    paragraph(doc, "PatchTST dùng đúng CQ_V2_2 clean-grain, V0, seed 42, NVIDIA L4, BF16, batch 2.048 và accumulation 4. Bảng dưới là TEST; VALIDATION được audit và giữ trong artifact nhưng không dùng TEST để chọn checkpoint.")
    patch_test = patch[patch.eval_split == "TEST"].sort_values(["window_id", "phase_id"])
    table(doc, patch_test, [("window_id", "W"), ("phase_id", "P"), ("n_rows", "n TEST"), ("acctempo_m3", "M3"), ("acctempo_m4", "M4"), ("f1_macro", "Macro-F1"), ("balanced_accuracy", "Bal. acc."), ("s_perf", "S_perf"), ("s_san_plus", "S_san+"), ("s_ent", "s_ent"), ("s_leak", "s_leak")], 8)
    patch_val = patch[patch.eval_split == "VALIDATION"].sort_values(["window_id", "phase_id"])
    heading(doc, "7. PatchTST V0 — VALIDATION")
    table(doc, patch_val, [("window_id", "W"), ("phase_id", "P"), ("n_rows", "n VAL"), ("acctempo_m3", "M3"), ("acctempo_m4", "M4"), ("f1_macro", "Macro-F1"), ("balanced_accuracy", "Bal. acc."), ("s_perf", "S_perf")], 8)

    manifest = json.loads((audit_root / "audit_manifest.json").read_text(encoding="utf-8"))
    checkpoints = pd.read_parquet(audit_root / "checkpoint_selection.parquet")
    heading(doc, "8. PatchTST V0 — audit và giới hạn")
    paragraph(doc, f"Post-hoc audit có {manifest['runs']} run, canonical S_leak={manifest['rows']['canonical_s_leak']} row, sanity={manifest['rows']['sanity_components']} row, STRICT/OVERLAP={manifest['rows']['evaluation_slices']} row, per-class={manifest['rows']['metrics_per_class']} row và bootstrap={manifest['rows']['bootstrap_metrics_per_class']} row (B={manifest['bootstrap_repetitions']:,}). Đây là audit partial được cho phép chỉ cho V0; full-grid PatchTST cần hoàn tất V1–V16 trước khi đưa vào bảng so sánh family/pipeline chính.")
    table(doc, checkpoints, [("window_id", "W"), ("best_epoch", "Epoch chọn"), ("selection_score", "Score VAL"), ("checkpoint_count_evaluated", "Checkpoint"), ("selection_margin", "Margin"), ("n_checkpoints_within_margin", "Trong margin")])
    paragraph(doc, "Kết luận: recurrent grid CQ seed 42 đạt evidence đầy đủ. PatchTST V0 chạy đúng contract và audit đạt, nên có thể mở tiếp PatchTST cho các pipeline còn lại; hiện chưa được dùng để chọn model thắng hoặc kết luận ổn định đa seed.")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    doc.save(TARGET)
    print(TARGET)


if __name__ == "__main__":
    main()
