"""Build the CQ PatchTST V0 seed-42 acceptance report from downloaded facts."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "CQ" / "resuilt" / "cq_patchtst_v0_seed42_20261023"
AUDIT = INPUT / "audits_v0_seed42" / "CQ" / "PATCHTST" / "seed=42"
OUTPUT = ROOT / "CQ" / "docs" / "REPORT_CQ_PATCHTST_V0_SEED42_2026-10-23.docx"


def _shade(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    props.append(shading)


def _set_cell_text(cell, text: str, bold: bool = False) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(str(text))
    run.bold = bold
    run.font.name = "Calibri"
    run.font.size = Pt(10.5)


def _table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True
    for index, header in enumerate(headers):
        _set_cell_text(table.rows[0].cells[index], header, bold=True)
        _shade(table.rows[0].cells[index], "1F4E78")
        for run in table.rows[0].cells[index].paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255)
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            _set_cell_text(cells[index], value)
    doc.add_paragraph()


def _heading(doc: Document, text: str, level: int = 1) -> None:
    paragraph = doc.add_heading(text, level=level)
    paragraph.paragraph_format.space_before = Pt(10)
    paragraph.paragraph_format.space_after = Pt(5)


def _p(doc: Document, text: str, bold_prefix: str | None = None) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(5)
    if bold_prefix and text.startswith(bold_prefix):
        paragraph.add_run(bold_prefix).bold = True
        paragraph.add_run(text[len(bold_prefix):])
    else:
        paragraph.add_run(text)


def _fmt(value: float, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    manifests = {window: json.loads((INPUT / window / "run_manifest.json").read_text(encoding="utf-8"))
                 for window in ("W1", "W2", "W3")}
    metrics = pd.concat([pd.read_parquet(INPUT / window / "metrics_overall.parquet")
                         for window in ("W1", "W2", "W3")], ignore_index=True)
    histories = {window: pd.read_parquet(INPUT / window / "train_history.parquet")
                 for window in ("W1", "W2", "W3")}
    audit_manifest = json.loads((AUDIT / "audit_manifest.json").read_text(encoding="utf-8"))
    sanity = pd.read_parquet(AUDIT / "sanity_components.parquet")
    slices = pd.read_parquet(AUDIT / "evaluation_slices.parquet")
    checkpoints = pd.read_parquet(AUDIT / "checkpoint_selection.parquet")
    per_class = pd.read_parquet(AUDIT / "metrics_per_class.parquet")
    bootstrap = pd.read_parquet(AUDIT / "bootstrap_metrics_per_class.parquet")

    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("BÁO CÁO NGHIỆM THU PATCHTST — CQ V0, SEED 42")
    run.bold = True
    run.font.name = "Calibri"
    run.font.size = Pt(17)
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run("Clean-grain CQ V2.2 | VastAI NVIDIA L4 | 23/10/2026").italic = True

    _heading(doc, "1. Kết luận ngắn")
    _p(doc, "PatchTST đã hoạt động đúng về mặt thực thi trên ba window của baseline V0: cả ba run có manifest hoàn tất, dự đoán TEST/VALIDATION, checkpoint selection và NVML energy record. Audit hậu kiểm V0-only cũng hoàn tất với B=2.000 bootstrap repetitions, không ghi nhận NaN/Inf prediction và sai số tổng xác suất ở mức số học nhỏ.")
    _p(doc, "AccTEMPO M3 được giữ là độ đo hiệu năng chính. Báo cáo này chỉ nghiệm thu V0 (zero-fill + masks); nó không phải kết luận so sánh PatchTST với 16 pipeline hay các seed stability khác.")

    _heading(doc, "2. Phạm vi và hợp đồng thực nghiệm")
    _table(doc,
           ["Trường", "Giá trị"],
           [["Task / release", f"CQ / {audit_manifest['release_id']}"],
            ["Model", "PATCHTST — channel-independent v2.1, math SDP"],
            ["Pipeline / seed", "V0 (zero-fill + masks) / 42"],
            ["Windows", "W1, W2, W3"],
            ["Dữ liệu", "clean-grain immutable portable input; data_release_id=" + audit_manifest["data_release_id"][:20] + "…"],
            ["Tối ưu", "AdamW; tối đa 50 epoch; patience=5"],
            ["Precision / GPU", "BF16; NVIDIA L4 (22.04 GiB reported)"],
            ["Batch", "batch_size=2,048; accumulation_steps=4"],
            ["Energy", "NVML_POWER_SAMPLING_ESTIMATE, 1-second sampling; GPU-only boundary"]])

    _heading(doc, "3. Hoàn tất run, checkpoint và tài nguyên")
    runtime_rows = []
    for window in ("W1", "W2", "W3"):
        manifest = manifests[window]
        selected = checkpoints.loc[checkpoints.window_id.eq(window)].iloc[0]
        history = histories[window]
        runtime_rows.append([
            window,
            f"{manifest['train_rows']:,}",
            f"{manifest['validation_rows']:,}",
            f"{int(manifest['test_rows']['P1']):,}",
            str(int(selected.best_epoch)),
            str(int(selected.checkpoint_count_evaluated)),
            str(int(selected.n_checkpoints_within_margin)),
            _fmt(manifest["elapsed_seconds"] / 3600, 2),
            _fmt(manifest["peak_ram_mb"] / 1024, 2),
            _fmt(manifest["energy_gpu_estimated_kwh"], 4),
        ])
    _table(doc,
           ["W", "Train", "Validation", "Test", "Best epoch", "Checkpoint", "Trong margin", "Wall h", "Peak RAM GiB", "GPU kWh est."],
           runtime_rows)
    _p(doc, "`n_checkpoints_within_margin=2` cho cả ba window: checkpoint được chọn theo Validation Macro-F1 trung bình P1–P4, đồng thời giữ lại thông tin margin đã khóa.")

    _heading(doc, "4. Kết quả chính — TEST (ALL rows)")
    test = slices.loc[(slices.eval_split == "TEST") & (slices.slice == "ALL")].copy()
    test = test.sort_values(["window_id", "phase_id"])
    _table(doc,
           ["W", "Phase", "n", "AccTEMPO", "Macro-F1", "Balanced acc.", "S_perf", "S_san+", "s_ent", "Recall warning / average / good"],
           [[row.window_id, row.phase_id, f"{int(row.n_eval_samples):,}", _fmt(row.acctempo_m3),
             _fmt(row.macro_f1), _fmt(row.balanced_acc), _fmt(row.s_perf), _fmt(row.s_san_plus), _fmt(row.s_ent),
             " / ".join(_fmt(getattr(row, column), 3) for column in ("c0_recall", "c1_recall", "c2_recall"))]
            for row in test.itertuples(index=False)])

    _heading(doc, "5. Kết quả chính — VALIDATION (ALL rows)")
    validation = slices.loc[(slices.eval_split == "VALIDATION") & (slices.slice == "ALL")].copy()
    validation = validation.sort_values(["window_id", "phase_id"])
    _table(doc,
           ["W", "Phase", "n", "AccTEMPO", "Macro-F1", "Balanced acc.", "S_perf", "S_san+", "s_ent"],
           [[row.window_id, row.phase_id, f"{int(row.n_eval_samples):,}", _fmt(row.acctempo_m3),
             _fmt(row.macro_f1), _fmt(row.balanced_acc), _fmt(row.s_perf), _fmt(row.s_san_plus), _fmt(row.s_ent)]
            for row in validation.itertuples(index=False)])

    _heading(doc, "6. Bằng chứng audit")
    probability_error = float(sanity.probability_sum_max_abs_error.max())
    nan_count = int(sanity.prediction_nan_inf_count.sum())
    small_count = int(per_class.small_support_flag.astype(bool).sum())
    _table(doc,
           ["Artifact", "Kết quả"],
           [["Run coverage", f"{audit_manifest['runs']} V0 run: W1–W3"],
            ["Canonical S_leak", f"{audit_manifest['rows']['canonical_s_leak']} facts; real-parent TRAIN pooled P1–P4, không refit theo augmentation"],
            ["Sanity", f"{audit_manifest['rows']['sanity_components']} facts: TEST/VALIDATION × W × P"],
            ["STRICT / OVERLAP", f"{audit_manifest['rows']['evaluation_slices']} slice facts; ALL, STRICT, OVERLAP"],
            ["Per-class", f"{audit_manifest['rows']['metrics_per_class']} rows; small-support flagged={small_count}"],
            ["Bootstrap CI", f"{audit_manifest['rows']['bootstrap_metrics_per_class']} rows; B={audit_manifest['bootstrap_repetitions']:,}"],
            ["Probability integrity", f"NaN/Inf={nan_count}; max |Σp−1|={probability_error:.2e}"],
            ["Checkpoint selection", f"{audit_manifest['rows']['checkpoint_selection']} rows; selected epoch/margin retained"]])

    _heading(doc, "7. Diễn giải và giới hạn")
    _p(doc, "Kết quả có quỹ đạo hợp lý theo phase: phần lớn window tăng Macro-F1, balanced accuracy và AccTEMPO khi đi từ P1 đến P4. Accuracy đơn thuần cao do mất cân bằng nhãn, vì vậy không dùng làm tiêu chí chính; bảng giữ Macro-F1, balanced accuracy, recall theo lớp và AccTEMPO để đánh giá đầy đủ hơn.")
    _p(doc, "Audit này xác nhận pipeline V0 hoạt động và facts được sinh nhất quán. Chưa được dùng để tuyên bố PatchTST tốt hơn RNN/LSTM/GRU/BiLSTM hoặc augmentation, vì các pipeline V1–V16 PatchTST và replication seed 43/44 chưa chạy.")

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("CQ PatchTST V0 seed 42 — generated from immutable run artifacts and post-hoc audit facts")
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
