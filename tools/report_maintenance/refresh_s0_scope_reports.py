"""Update the reports after promoting S0 from a sampled profile to an all-row census."""
from pathlib import Path

from docx import Document


REPORTS = (
    Path("CQ/docs/REPORT_CQ_V1.docx"),
    Path("LO/docs/REPORT_LO_V1.docx"),
)


def replace(paragraph, text: str) -> None:
    paragraph.text = text
    for run in paragraph.runs:
        run.font.name = "Times New Roman"
        run.font.size = None


for report in REPORTS:
    document = Document(report)
    for paragraph in document.paragraphs:
        current = paragraph.text
        if current.startswith("Tiến độ imputation (Modal): S0_RAW đã materialize"):
            replace(paragraph, current.replace(
                "S0_RAW đã materialize cho CQ và LO, W1–W3.",
                "S0_RAW mẫu trước đây cho CQ và LO, W1–W3 đang được thay bằng census toàn bộ dòng; S1_IMPUTED cũng census toàn bộ dòng sau mỗi imputer; chỉ các census mới là baseline chính thức.",
            ))
        elif current.startswith("S0_RAW đã hoàn tất cho ") and "profile mẫu tối đa 100,000" in current:
            task = "CQ" if "cho CQ" in current else "LO"
            replace(paragraph, (
                f"S0_RAW mẫu trước đây của {task} (W1–W3, tối đa 100.000 dòng mỗi trạng thái) "
                "không được dùng làm số liệu chính thức. S0_RAW hiện được cấu hình chạy lại trên toàn bộ dòng "
                "của từng W/split/phase; manifest mới sẽ ghi profile_scope=ALL_ROWS."
            ))
        elif current.startswith("S0_RAW profile tối đa 100.000 dòng"):
            replace(paragraph, (
                "S0_RAW và S1_IMPUTED đều là census toàn bộ dòng của từng trạng thái W/split/phase; vì vậy số đếm và tỷ lệ "
                "chất lượng trước/sau điền khuyết là chính xác trên release. Mọi metric lưu cả số đếm lẫn mẫu số, nên không "
                "suy diễn tỷ lệ thiếu từ structural absence."
            ))
    document.save(report)
    print(report)
