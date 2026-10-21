"""Append the canonical storage and naming contract to CQ/LO V1 reports."""
from pathlib import Path

from docx import Document
from docx.shared import Pt


REPORTS = (Path("CQ/docs/REPORT_CQ_V1.docx"), Path("LO/docs/REPORT_LO_V1.docx"))


def set_size(paragraph, size=13):
    for run in paragraph.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(size)


for path in REPORTS:
    doc = Document(path)
    if any(p.text.startswith("14. Quy ước đặt tên") for p in doc.paragraphs):
        print(f"already updated: {path}")
        continue
    # These reports use a custom style set, so do not assume Word's built-in
    # English `Heading 1` style exists.
    heading = doc.add_paragraph()
    heading.add_run("14. Quy ước đặt tên và đường dẫn artifact").bold = True
    set_size(heading, 15)
    p = doc.add_paragraph(
        "Tên cột dùng snake_case ASCII không dấu. Số đếm dùng tiền tố n_; tỷ lệ dùng hậu tố "
        "_rate, _ratio hoặc _share; cờ kiểm tra dùng qa_; phiên bản dùng _version; thời gian UTC "
        "dùng _utc; đơn vị ghi trong tên (_s, _mb, _kwh, _g, _w, _usd). Mã lớp trong fact và "
        "meta-dataset là c0/c1/c2: CQ = Warning/Average/Good, LO = I/D/E/G."
    )
    set_size(p)
    p = doc.add_paragraph(
        "Partition dùng thống nhất key=value: task, feature_regime, window_id, phase_id, stage, "
        "pipeline_id, model_name, seed, run_id và attempt_id. phase_id chỉ nhận P1–P4; artifact "
        "fit gộp dùng fit_scope=TRAIN_POOLED_P1_P4, không dùng phase giả ALL."
    )
    set_size(p)
    p = doc.add_paragraph(
        "run_id là SHA-256 của cấu hình khoa học chuẩn hóa; implementation_version và môi trường là "
        "provenance của attempt, không làm thay đổi run_id. attempt_id tăng 0001, 0002… để lần chạy lại "
        "không ghi đè artifact cũ."
    )
    set_size(p)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "Tầng"
    table.rows[0].cells[1].text = "Dạng đường dẫn chuẩn"
    rows = (
        ("L1 run", "L1_runs/task={task}/feature_regime={regime}/window_id={window}/pipeline_id={pipeline}/model_name={model}/seed={seed}/run_id={run_id}/attempt_id={attempt}/"),
        ("L2 fact", "L2_facts/{fact}/task={task}/feature_regime={regime}/window_id={window}/phase_id={phase}/stage={state}/run_id={run_id}/attempt_id={attempt}/part-00000.parquet"),
        ("L2 pooled fit", "L2_facts/bin_scheme/task={task}/feature_regime={regime}/window_id={window}/fit_scope=TRAIN_POOLED_P1_P4/stage={state}/…"),
        ("L3 diagnostic", "L3_meta/imputation_diagnostic_seed_level/task={task}/feature_regime={regime}/window_id={window}/pipeline_id={pipeline}/model_name=IMPUTATION_ONLY/seed={seed}/run_id={run_id}/attempt_id={attempt}/"),
    )
    for left, right in rows:
        cells = table.add_row().cells
        cells[0].text, cells[1].text = left, right
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                set_size(para)
    doc.save(path)
    print(f"updated: {path}")
