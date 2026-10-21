"""Append the 30-09-2026 resolution status to Danh_gia_Split_V2.2.docx."""
from __future__ import annotations

from pathlib import Path

import polars as pl
from docx import Document
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "Danh_gia_Split_V2.2.docx"
OUT = ROOT / "docs" / "Danh_gia_Split_V2.2_cap_nhat_2026-09-30.docx"
BLUE, GREY, GREEN = "1F4E78", "F2F2F2", "E2F0D9"


def read(task: str, name: str) -> pl.DataFrame:
    folder = ROOT / task / "resuilt" / "long_offering_assignment_audit_v1" / name
    files = list(folder.glob("*.parquet"))
    if not files:
        raise RuntimeError(f"{folder}: no parquet file found")
    # Local download retries can leave duplicate immutable part files.  The
    # newest completed part is the current artifact; each Databricks write is
    # logically a one-file table.
    return pl.read_parquet(max(files, key=lambda path: path.stat().st_mtime))


def shade(cell, color: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    node = OxmlElement("w:shd"); node.set(qn("w:fill"), color); properties.append(node)


def table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    result = doc.add_table(rows=1, cols=len(headers))
    try:
        result.style = "Table Grid"
    except KeyError:
        # The externally supplied Vietnamese template omits this English
        # built-in name; explicit borders/colours below still keep it legible.
        pass
    for index, header in enumerate(headers):
        cell = result.rows[0].cells[index]; cell.text = ""
        run = cell.paragraphs[0].add_run(header); run.bold = True; run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(255, 255, 255); shade(cell, BLUE)
    for rindex, row in enumerate(rows):
        cells = result.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = ""; cells[index].paragraphs[0].add_run(value).font.size = Pt(11)
            if rindex % 2: shade(cells[index], GREY)
    doc.add_paragraph()


def heading(doc: Document, text: str, level: int) -> object:
    """Documents supplied externally may not contain English Heading styles."""
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text); run.bold = True
    run.font.size = Pt(16 if level == 1 else 13)
    run.font.color.rgb = RGBColor.from_string("17365D")
    return paragraph


def main() -> None:
    doc = Document(SOURCE)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    heading(doc, "7. Cập nhật đóng điểm mở — 30/09/2026", level=1)
    verdict = doc.add_paragraph()
    verdict.add_run("Kết luận cập nhật: ").bold = True
    verdict.add_run("Các điểm A, B, C, D và phần bằng chứng của F đã có artifact kiểm tra. Split V2.2 reference được giữ làm split chính; V2.3 chỉ là biến thể hardening, không trộn kết quả. Các gate còn lại là materialize V2.2, QA15/seen-course và chạy downstream trên release đã khóa.")
    properties = verdict._p.get_or_add_pPr(); node = OxmlElement("w:shd"); node.set(qn("w:fill"), GREEN); properties.append(node)

    qa_rows = []
    for task in ("CQ", "LO"):
        row = read(task, "enrollment_assignment_qa").row(0, named=True)
        qa_rows.append([task, f"{row['distinct_enrollment_count']:,}",
                        str(row["n_enrollments_multiple_rolling_blocks"]),
                        str(row["n_enrollments_multiple_splits_same_window"]),
                        str(row["n_context_rows_without_block"]),
                        "ĐẠT" if row["assignment_qa_pass"] == 1 else "KHÔNG ĐẠT"])
    heading(doc, "7.1 Điểm F(3): uniqueness đơn vị gán", level=2)
    table(doc, ["Task", "Enrollment riêng", "Đa block", "Đa split/window", "Không map block", "QA"], qa_rows)
    doc.add_paragraph("Xác nhận này áp dụng cho enrollment_id khi map qua offering_id × timeline_source. Enrollment có thể xuất hiện ở các window mở rộng, nhưng luôn thuộc đúng một rolling block và đúng một split trong từng window.")

    unit_rows = []
    for task in ("CQ", "LO"):
        frame = read(task, "unit_size_distribution")
        for slice_id in ("A", "T1", "T2", "T3"):
            subset = frame.filter(pl.col("temporal_slice") == slice_id)
            total_units = int(subset["offering_timeline_count"].sum())
            total_enrollments = int(subset["enrollment_count"].sum())
            tiny_units = int(subset["n_units_le_5"].sum())
            tiny_enrollments = int(subset["enrollment_count_units_le_5"].sum())
            unit_rows.append([task, slice_id, f"{total_units:,}", f"{total_enrollments:,}",
                              f"{tiny_units / total_units * 100:.2f}%", f"{tiny_enrollments / total_enrollments * 100:.3f}%"])
    heading(doc, "7.2 Điểm F(3): quy mô và đơn vị rất nhỏ", level=2)
    table(doc, ["Task", "Lát", "offering × timeline", "Enrollment", "Units ≤5", "Enrollment trong units ≤5"], unit_rows)
    doc.add_paragraph("Dù một số timeline proxy có tỷ lệ unit ≤5 cao, tỷ trọng enrollment tương ứng nhỏ. Đây không phải bằng chứng rằng validation/test giống nhau chỉ vì bị chi phối bởi đơn vị cực nhỏ.")

    heading(doc, "7.3 Trạng thái các điểm mở", level=2)
    table(doc, ["Điểm", "Trạng thái 30/09", "Quyết định / evidence"], [
        ["A — support LO E/G", "Đạt có điều kiện", "Drift temporal được chứng minh trên behavioural proxy; support nhỏ xử lý bằng flag, CI bootstrap và paired bootstrap."],
        ["B — shared calendar", "Đạt", "CQ là calendar anchor; LO dùng shared boundaries."],
        ["C — long offering", "Đạt", "p50/p90/max và >270 ngày đã audit; policy = retain_flagged_no_pseudo_run_v1."],
        ["D — LO label coverage", "Đạt theo scope proxy", "Eligibility proxy A/T1/T2/T3 cao; E/G thấp sau T1 là drift của accepted proxy, không suy luận final grade."],
        ["E — small support", "Đã khóa contract", "n_support, small_support_flag<100, CI bootstrap 2,000, selection_margin; paired comparison 2,000 draw."],
        ["F — registry", "Đạt về quyết định split", "V2.2 reference là primary; V2.3 hardening-only. Còn QA15 sau materialize là gate downstream."],
    ])
    heading(doc, "7.4 Việc còn lại", level=2)
    doc.add_paragraph("(1) Materialize phase_views_v2_2 và test_prefix_views_v2_2 từ manifest V2.2 đã khóa; (2) chạy QA15/seen-course; (3) chạy S0 → imputation → augmentation train-only → model. Không cần chạy lại split hoặc audit hiện tại.")
    doc.save(OUT); print(OUT)


if __name__ == "__main__": main()
