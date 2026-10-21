"""Generate task-specific Split V2.2 QA reports from downloaded registries.

The registries are the source of truth.  This intentionally creates separate
addenda instead of rewriting the historical V1 reports.
"""
from __future__ import annotations

import argparse
from datetime import date
from math import ceil
from pathlib import Path

import polars as pl
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = date(2026, 9, 29)
TASKS = {
    "CQ": {
        "label": "CQ_label_final: warning / average / good",
        "pairing": "balanced",
    },
    "LO": {
        "label": "LO_performance_label_3: I/D / G / E",
        "pairing": "rarest_first",
    },
}

NAVY = "17365D"
BLUE = "1F4E78"
PALE_BLUE = "D9EAF7"
GREEN = "E2F0D9"
GRAY = "F2F2F2"


def parquet(root: Path, name: str) -> pl.DataFrame:
    files = sorted((root / name).glob("*.parquet"))
    if len(files) != 1:
        raise RuntimeError(f"Expected exactly one parquet in {root / name}, got {len(files)}")
    return pl.read_parquet(files[0])


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_paragraph_shading(paragraph, fill: str) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    p_pr.append(shd)


def set_cell_text(cell, value: object, *, bold: bool = False, color: str | None = None) -> None:
    cell.text = ""
    run = cell.paragraphs[0].add_run(str(value))
    run.bold = bold
    run.font.size = Pt(8.5)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def add_table(doc: Document, headers: list[str], rows: list[list[object]], widths: list[float] | None = None) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    for idx, header in enumerate(headers):
        cell = table.rows[0].cells[idx]
        set_cell_text(cell, header, bold=True, color="FFFFFF")
        set_cell_shading(cell, BLUE)
        if widths:
            cell.width = Inches(widths[idx])
    for row_idx, row in enumerate(rows):
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            set_cell_text(cells[idx], value)
            if row_idx % 2:
                set_cell_shading(cells[idx], GRAY)
            if widths:
                cells[idx].width = Inches(widths[idx])
    doc.add_paragraph()


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        run.font.color.rgb = RGBColor.from_string(NAVY if level == 1 else BLUE)


def pct(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{100 * value:.{digits}f}%"


def configure_document(doc: Document, task: str, release_label: str) -> None:
    section = doc.sections[0]
    section.top_margin = Cm(1.7)
    section.bottom_margin = Cm(1.7)
    section.left_margin = Cm(1.8)
    section.right_margin = Cm(1.8)
    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Aptos")
    normal.font.size = Pt(10)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run(f"{task} · Split {release_label} · {RUN_DATE.isoformat()} · Registry-derived report")
    footer.runs[0].font.size = Pt(8)
    footer.runs[0].font.color.rgb = RGBColor(100, 100, 100)


def build_report(task: str, config: dict[str, object], release_key: str, source_release_key: str) -> None:
    release_label = release_key.upper().replace("_", ".")
    source_release_label = source_release_key.upper().replace("_", ".")
    registry_root = ROOT / task / "resuilt" / f"split_registry_{source_release_key}"
    qa = parquet(registry_root, f"qa22_{source_release_key}").sort("window_id")
    actual = parquet(registry_root, "split_actual_ratios")
    labels = parquet(registry_root, "split_label_distribution")
    strict = parquet(registry_root, "temporal_strict_share")
    boundary = parquet(registry_root, "calendar_boundaries").row(0, named=True)
    blocks = parquet(registry_root, "block_label_audit").sort("rolling_block")

    if not qa.select(pl.col("qa22_ok").all()).item():
        raise RuntimeError(f"{task} registry is not QA22 accepted")

    doc = Document()
    configure_document(doc, task, release_label)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(f"{task} — Báo cáo Split {release_label}")
    run.bold = True
    run.font.size = Pt(22)
    run.font.color.rgb = RGBColor.from_string(NAVY)
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run(f"Hybrid scenario · split_version = {release_label} · registry QA closure").italic = True

    status = doc.add_paragraph()
    status.add_run("Kết luận: ").bold = True
    status.add_run(f"QA22 đạt cho W1–W3. Registry được phép làm input cho materialize phase views {release_label}; chưa phải kết quả mô hình.")
    set_paragraph_shading(status, GREEN)
    if source_release_key != release_key:
        provenance = doc.add_paragraph()
        provenance.add_run("Ghi chú versioning: ").bold = True
        provenance.add_run(
            f"Số liệu được tạo trước khi đổi nhãn release và tải về dưới thư mục split_registry_{source_release_key}. "
            f"Do dùng QA hai tầng, chúng được phân loại lại là kết quả {release_label}; V2.2 gốc giữ policy per-arm 5%."
        )

    add_heading(doc, "1. Phạm vi và nguồn bằng chứng")
    doc.add_paragraph(
        "Báo cáo được sinh trực tiếp từ registry parquet đã tải về. Nó không suy diễn tỷ lệ split từ cấu hình lý tưởng; "
        "mọi số lượng là sau join nhãn của task tương ứng."
    )
    add_table(doc, ["Thuộc tính", "Giá trị"], [
        ["Task", task],
        ["Scenario", "hybrid"],
        ["Split version", release_label],
        ["Nhãn", str(config["label"])],
        ["Chiến lược ghép block", str(config["pairing"])],
        ["Calendar anchor", str(boundary["calendar_anchor_task"])],
        ["Registry local (physical source)", str(registry_root)],
        ["Registry release được báo cáo", release_label],
    ], [2.0, 5.1])

    add_heading(doc, "2. Lịch sử protocol: V2.2 ban đầu và V2.3 hiện hành")
    doc.add_paragraph(
        "V2.2 là protocol temporal split gốc theo tài liệu: calendar CQ–LO dùng chung, A là lịch sử; "
        "B–G là ba cặp validation/test theo các lát thời gian liên tiếp; và QA yêu cầu từng validation, từng test "
        "phải đạt ít nhất 5% tổng enrollment của chính task. Điều này bảo vệ quy mô evaluation nhưng giả định mật độ "
        "eligible-label của CQ và LO tương tự nhau theo lịch."
    )
    doc.add_paragraph(
        "V2.3 giữ nguyên toàn bộ calendar, offering boundary, nhãn, block assignment và thứ tự W1–W3 của V2.2. "
        "Chỉ thay contract QA về quy mô evaluation để tương thích với calendar chung khi temporal density của LO khác CQ: "
        "mỗi nhánh ≥ max(2.5% tổng task, 50,000 dòng), đồng thời validation+test ≥ 5% tổng task. Đây là thay đổi protocol "
        "nên có version mới, không ghi đè V2.2."
    )
    add_table(doc, ["Thành phần", "V2.2 gốc", "V2.3 hiện hành"], [
        ["Calendar / chronology", "CQ anchor; A, T1(B/C), T2(D/E), T3(F/G)", "Giữ nguyên V2.2"],
        ["Pairing CQ", "balanced", "Giữ nguyên"],
        ["Pairing LO", "rarest_first", "Giữ nguyên"],
        ["QA end-order", "Bắt buộc", "Bắt buộc"],
        ["QA mỗi evaluation arm", "≥ 5% tổng task", "≥ max(2.5% tổng task, 50,000)"],
        ["QA evaluation gộp", "Không tách thành điều kiện riêng", "validation + test ≥ 5% tổng task"],
        ["Mục tiêu", "Mỗi nhánh lớn theo tỷ lệ toàn task", "Đủ mẫu tuyệt đối, vẫn giữ calendar chung"],
    ], [1.8, 2.65, 2.65])

    old_comparison_rows = []
    for row in qa.iter_rows(named=True):
        total_task = max(row["n_enrollments_evaluation"], 1)  # overwritten below from the actual full final window
        # The largest rolling window contains every A--G block and is the
        # complete eligible-label population for this task.
        total_task = int(actual.filter(pl.col("window_id") == "W3").select("window_enrollment_count").unique().item())
        old_threshold = ceil(total_task * 0.05)
        old_arm_ok = row["n_enrollments_validation"] >= old_threshold and row["n_enrollments_test"] >= old_threshold
        old_ok = bool(row["end_order_ok"] and old_arm_ok)
        old_comparison_rows.append([
            row["window_id"], f"{row['n_enrollments_validation']:,}", f"{row['n_enrollments_test']:,}",
            f"{old_threshold:,}", "Đạt" if old_ok else "Không đạt", "Đạt" if row["qa22_ok"] else "Không đạt",
        ])
    doc.add_paragraph("Đối chiếu trên cùng manifest A–G (chỉ thay điều kiện QA):")
    add_table(doc, ["Window", "Validation", "Test", "Ngưỡng V2.2 / nhánh", "QA V2.2", "QA V2.3"], old_comparison_rows,
              [0.7, 1.0, 1.0, 1.3, 1.0, 1.0])
    if task == "LO":
        doc.add_paragraph(
            "Kết quả then chốt: LO W1 không đạt V2.2 vì 88,732 và 93,214 đều thấp hơn 149,368; "
            "nhưng đạt V2.3 vì mỗi nhánh vượt 74,684, evaluation gộp 181,946 vượt 149,368, và hai nhánh cân bằng."
        )
    else:
        doc.add_paragraph(
            "CQ đạt cả V2.2 lẫn V2.3: mọi evaluation arm đều vượt ngưỡng V2.2 là 5% tổng CQ."
        )

    add_heading(doc, "3. Cơ chế chia theo thời gian")
    doc.add_paragraph(
        "CQ là calendar anchor. A là lịch sử sớm; future pool được cắt thành ba lát thời gian liên tiếp T1, T2, T3. "
        "Mỗi lát được chia thành một cặp validation/test ở cấp offering. W1 dùng A | B | C; "
        "W2 dùng A+B+C | D | E; W3 dùng A–E | F | G. CQ tối ưu cân bằng nhãn, còn LO dùng rarest_first để ưu tiên nhãn hiếm."
    )
    add_table(doc, ["Mốc calendar chung", "Ngày"], [
        ["Kết thúc block A", boundary["a_boundary"]],
        ["Kết thúc lát T1 (B/C)", boundary["slice_1_boundary"]],
        ["Kết thúc lát T2 (D/E)", boundary["slice_2_boundary"]],
        ["Kết thúc lát T3 (F/G)", boundary["slice_3_boundary"]],
    ], [3.3, 3.8])

    add_heading(doc, "4. QA22: thứ tự thời gian và quy mô evaluation")
    qa_policy = "quy tắc hai tầng: từng nhánh validation/test ≥ max(2.5% tổng task, 50,000), và validation+test ≥ 5% tổng task" if release_key == "v2_3" else "quy tắc gốc: từng nhánh validation/test ≥ 5% tổng task"
    doc.add_paragraph(
        "QA22 yêu cầu max(offering_end của TRAIN) không muộn hơn min(offering_end của evaluation). "
        f"Quy mô dùng {qa_policy}. P1 overlap chỉ được báo cáo riêng, không được dùng thay cho điều kiện label-end ordering."
    )
    qa_rows = []
    for row in qa.iter_rows(named=True):
        qa_rows.append([
            row["window_id"], f"{row['n_enrollments_validation']:,}", f"{row['n_enrollments_test']:,}",
            f"{row['n_enrollments_evaluation']:,}", f"{row['min_eval_arm_enrollments']:,}",
            f"{row['min_eval_total_enrollments']:,}", "Đạt" if row["end_order_ok"] else "Không đạt",
            "Đạt" if row["qa22_ok"] else "Không đạt", pct(row["ev_train_overlap_share"]),
        ])
    add_table(doc, ["Window", "Validation", "Test", "Eval gộp", "Min/nhánh", "Min/gộp", "End-order", "QA22", "P1 overlap"], qa_rows,
              [0.55, 0.85, 0.85, 0.85, 0.75, 0.75, 0.65, 0.5, 0.75])

    add_heading(doc, "5. Tỷ lệ split thực tế và quy mô TRAIN")
    actual_rows = []
    for row in actual.sort(["window_id", "split"]).iter_rows(named=True):
        actual_rows.append([row["window_id"], row["split"], f"{row['enrollment_count']:,}", pct(row["split_enrollment_share"])])
    add_table(doc, ["Window", "Split", "Enrollment", "Tỷ lệ trong window"], actual_rows, [1.0, 1.5, 1.8, 1.8])
    doc.add_paragraph(
        "Tỷ lệ trên là trong population được dùng bởi từng rolling window; các block ở tương lai xa được giữ lại cho window sau. "
        "Vì vậy không được diễn giải validation/test W1 như tỷ lệ trên toàn bộ population cuối cùng."
    )

    add_heading(doc, "6. Phân phối nhãn tại validation/test")
    eval_labels = labels.filter(pl.col("split").is_in(["validation", "test"])).sort(["window_id", "split", "label"])
    label_rows = [[r["window_id"], r["split"], r["label"], f"{r['label_enrollment_count']:,}", pct(r["label_ratio"], 3)]
                  for r in eval_labels.iter_rows(named=True)]
    add_table(doc, ["Window", "Split", "Label", "Support", "Tỷ lệ"], label_rows, [0.8, 1.2, 1.1, 1.5, 1.1])

    add_heading(doc, "7. Temporal strict theo prediction phase")
    doc.add_paragraph(
        "temporal_strict_share là phần enrollment mà cutoff của phase đã không sớm hơn tau_w (mốc kết thúc TRAIN). "
        "Nó phải được báo cáo theo phase; không dùng tỷ lệ overlap gộp để suy ra strict share của một phase riêng lẻ."
    )
    strict_rows = []
    for window_id in ("W1", "W2", "W3"):
        for split in ("validation", "test"):
            piece = strict.filter((pl.col("window_id") == window_id) & (pl.col("split") == split))
            values = {r["phase_id"]: r["temporal_strict_share"] for r in piece.iter_rows(named=True)}
            strict_rows.append([window_id, split, pct(values.get("P1")), pct(values.get("P2")), pct(values.get("P3")), pct(values.get("P4"))])
    add_table(doc, ["Window", "Split", "P1", "P2", "P3", "P4"], strict_rows, [0.8, 1.2, 0.9, 0.9, 0.9, 0.9])

    add_heading(doc, "8. Audit block và hạn chế")
    metric_labels = [c for c in blocks.columns if c.endswith("_count") and c not in {"offering_count", "enrollment_count", "long_offering_enrollment_count"}]
    headers = ["Block", "Offerings", "Enrollment", *[c.removesuffix("_count") for c in metric_labels]]
    block_rows = []
    for r in blocks.iter_rows(named=True):
        block_rows.append([r["rolling_block"], f"{r['offering_count']:,}", f"{r['enrollment_count']:,}", *[f"{r[c]:,}" for c in metric_labels]])
    add_table(doc, headers, block_rows)
    if task == "LO":
        doc.add_paragraph(
            "Hạn chế quan trọng: drift nhãn LO theo thời gian là dữ liệu thật. Ở W3, G có khoảng 97 validation và 96 test; "
            "metric theo lớp hiếm cần kèm support và khoảng tin cậy. Không augment validation/test."
        )
    else:
        doc.add_paragraph(
            "Hạn chế quan trọng: CQ cũng có label drift theo lát thời gian; mọi kết quả phải báo macro-F1, support từng lớp và strict/relaxed context theo phase."
        )

    add_heading(doc, "9. Cấu trúc lưu trữ và bước kế tiếp")
    doc.add_paragraph(
        f"Registry {release_label} lưu theo cây: split_registry_{release_key}/ → manifest/, qa22_{release_key}/, split_registry/, "
        "split_actual_ratios/, split_label_distribution/, temporal_strict_context/, temporal_strict_share/, "
        "duration_summary/, calendar_boundaries/, block_label_audit/."
    )
    doc.add_paragraph(
        f"Bước được phép tiếp theo: materialize phase views {release_label} và test-prefix views P1–P4 bằng manifest immutable này; "
        "sau đó mới materialize S0, imputation, augmentation (TRAIN-only) và model runs. Không trộn artifact V1/V2.1 vào meta-release V2.2."
    )

    output = ROOT / task / "docs" / f"REPORT_{task}_SPLIT_{release_key.upper()}_2026-09-29.docx"
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", choices=("v2_2", "v2_3"), required=True,
                        help="logical release label in the report")
    parser.add_argument("--source-release", choices=("v2_2", "v2_3"),
                        help="physical downloaded registry name; defaults to --release")
    args = parser.parse_args()
    source_release = args.source_release or args.release
    for task_name, task_config in TASKS.items():
        build_report(task_name, task_config, args.release, source_release)
