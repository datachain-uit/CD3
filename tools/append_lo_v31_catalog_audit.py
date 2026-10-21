"""Append the accepted LO V3.1 catalog-denominator audit to the LO report."""
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


REPORT = Path(__file__).resolve().parents[1] / "LO" / "docs" / "REPORT_LO_V3_1.docx"
HEADING = "14. Audit catalog denominator và quyết định V3.1"


def shade(cell, color: str) -> None:
    element = OxmlElement("w:shd")
    element.set(qn("w:fill"), color)
    cell._tc.get_or_add_tcPr().append(element)


def table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    result = doc.add_table(rows=1, cols=len(headers))
    result.style = "Table Grid"
    result.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, value in zip(result.rows[0].cells, headers):
        cell.text = value
        shade(cell, "1F4E78")
        for run in cell.paragraphs[0].runs:
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(11)
    for values in rows:
        for cell, value in zip(result.add_row().cells, values):
            cell.text = value
            for run in cell.paragraphs[0].runs:
                run.font.size = Pt(11)
    doc.add_paragraph()


def heading(doc: Document, text: str, level: int) -> None:
    """Use the report's custom style IDs (not Word's localized name lookup)."""
    paragraph = doc.add_paragraph()
    paragraph.style = doc.styles["693" if level == 1 else "694"]
    paragraph.add_run(text)


def main() -> None:
    document = Document(REPORT)
    if any(paragraph.text == HEADING for paragraph in document.paragraphs):
        raise RuntimeError("Catalog-audit section already exists; refusing to append it twice.")

    heading(document, HEADING, 1)
    document.add_paragraph(
        "Audit catalog-denominator V3.1 đọc artifact nhãn bất biến, course_problem_catalog và "
        "problem_events_clean. Một catalog problem được xem là active khi có ít nhất một automatic-score "
        "event từ bất kỳ enrollment nào trong course. Chỉ assignment/exam có trọng số dương trong công thức "
        "PRIMARY mới được đưa vào mẫu số; catalog của component weight = 0 không làm giảm tỷ lệ active."
    )

    heading(document, "14.1. Trần điểm quan sát theo course", 2)
    table(document, ["Nhóm", "Course", "Enrollment eligible", "Tỷ lệ cohort"], [
        ["Toàn bộ cohort V3.1", "711", "2,605,423", "100.000%"],
        ["course_score_ceiling_observed < 60", "493", "1,668,604", "64.044%"],
        ["course_score_ceiling_observed < 85", "675", "2,372,394", "91.056%"],
        ["course_score_ceiling_observed ≥ 60", "218", "936,819", "35.956%"],
        ["course_score_ceiling_observed ≥ 85", "36", "233,029", "8.944%"],
    ])
    document.add_paragraph(
        "course_score_ceiling_observed là final_score PRIMARY lớn nhất quan sát được trong course, "
        "không phải một nhãn hay feature dự báo. Nó được lưu làm context/reporting field; không tự động "
        "loại course chỉ vì trần thấp. Quy tắc loại duy nhất vẫn là no_scored_signal_in_course đã được "
        "áp dụng tại V3.1."
    )

    heading(document, "14.2. Kiểm tra giả thuyết active catalog", 2)
    table(document, ["Band trần điểm", "Course", "Enrollment", "Active ratio p50", "p90", "Mean"], [
        ["<60", "493", "1,668,604", "0.900", "1.000", "0.740"],
        ["60–<85", "182", "703,790", "1.000", "1.000", "0.986"],
        ["≥85", "36", "233,029", "1.000", "1.000", "0.993"],
    ])
    document.add_paragraph(
        "Kết quả không ủng hộ giả thuyết rằng trần thấp chủ yếu do catalog problem không được mở/không có "
        "hoạt động trong offering: ngay band <60 có median active ratio 0.900 và p90 = 1.000. Vì vậy không "
        "đổi mẫu số sang active catalog và không mở V3.2. V3.1 catalog-normalized được giữ làm PRIMARY; "
        "sự không đồng nhất giữa course được minh bạch hóa bằng course_score_ceiling_observed và đánh giá "
        "theo window/slice."
    )

    heading(document, "14.3. Coverage trần điểm theo lát thời gian", 2)
    table(document, ["Lát", "Enrollment", "Ceiling ≥60", "Tỷ lệ ≥60", "Ceiling ≥85", "Tỷ lệ ≥85"], [
        ["A", "1,787,557", "659,474", "36.893%", "166,159", "9.295%"],
        ["T1", "156,681", "59,054", "37.691%", "10,237", "6.534%"],
        ["T2", "401,686", "120,925", "30.104%", "24,864", "6.190%"],
        ["T3", "259,499", "97,366", "37.521%", "31,769", "12.242%"],
    ])
    document.add_paragraph(
        "Bốn lát cộng đúng 2,605,423 enrollment của cohort eligible và không còn UNASSIGNED. Audit dùng "
        "timeline_source từ enrollment_windows, đúng cùng logic với build_split_v2_2.py; vì vậy bảng này "
        "được gắn với registry LO hiện hành, không phải shared-calendar registry của CQ."
    )

    heading(document, "14.4. Quyết định chốt", 2)
    document.add_paragraph(
        "Yêu cầu catalog-denominator audit được đáp ứng. Giữ LO V3.1 và QA22 hiện hành; không rebuild label, "
        "split hoặc materialize chỉ vì audit này. Artifact chính thức cần được lưu ở một output path sạch "
        "catalog_denominator_audit_v3_1_r2 trước khi trích xuất/đóng gói, để không lẫn parquet của các lần thử trước."
    )

    document.save(REPORT)
    print(REPORT)


if __name__ == "__main__":
    main()
