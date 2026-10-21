"""Rebuild the shared Split report with the locked CQ/LO V2.1 registries."""
from __future__ import annotations

from pathlib import Path

import polars as pl
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/SPLIT_V2_QA_INCIDENT_REPORT_2026-09-28.docx"


def read(task: str, name: str) -> pl.DataFrame:
    root = ROOT / task / "resuilt" / "split_registry_v2_1" / name
    return pl.read_parquet(next(root.glob("*.parquet")))


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12 if level == 1 else 8)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(16 if level == 1 else 12)


def para(doc: Document, text: str, bold_prefix: str | None = None) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    if bold_prefix and text.startswith(bold_prefix):
        p.add_run(bold_prefix).bold = True
        p.add_run(text[len(bold_prefix):])
    else:
        p.add_run(text)


def table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for cell, value in zip(t.rows[0].cells, headers):
        cell.text = value
        for r in cell.paragraphs[0].runs:
            r.bold = True
            r.font.size = Pt(8.5)
    for row in rows:
        cells = t.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = value
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(8.5)


def registry_rows(task: str) -> tuple[list[list[str]], list[list[str]], list[list[str]], list[list[str]]]:
    qa = read(task, "qa22_v2_1").sort("window_id")
    reg = read(task, "split_registry").sort("window_id")
    ratios = read(task, "split_actual_ratios")
    ctx = read(task, "temporal_strict_context")
    labels = read(task, "split_label_distribution")

    qa_rows = [[task, x["window_id"], f"{x['n_enrollments_validation']:,}", f"{x['n_enrollments_test']:,}",
                f"{x['min_eval_enrollments']:,}", "PASS" if x["qa22_ok"] else "FAIL",
                pct(x["ev_train_overlap_share"]), str(x["days_train_end_to_test_start"]),
                str(x["train_history_span_days"])] for x in qa.to_dicts()]
    reg_rows = [[task, x["window_id"], x["purge_mode"], str(x["n_purged"]),
                 pct(x["purged_enrollment_share"]),
                 "—" if x["label_drift_window_prev_jsd"] is None else f"{x['label_drift_window_prev_jsd']:.4f}"
                 ] for x in reg.to_dicts()]
    strict_rows = []
    for split in ("validation", "test"):
        x = ctx.filter(pl.col("split") == split)
        strict_rows.append([task, split.upper(), *[pct(x.select(pl.col(f"temporal_strict_P{i}").mean()).item()) for i in range(1, 5)]])
    support = (labels.filter(pl.col("split").is_in(["validation", "test"]))
        .group_by("label").agg(pl.col("label_enrollment_count").min().alias("minimum")).sort("label"))
    support_rows = [[task, x["label"], f"{x['minimum']:,}"] for x in support.to_dicts()]
    return qa_rows, reg_rows, strict_rows, support_rows


def main() -> None:
    cq = registry_rows("CQ")
    lo = registry_rows("LO")
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(1.8); sec.bottom_margin = Cm(1.8)
    sec.left_margin = Cm(1.8); sec.right_margin = Cm(1.8)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("BÁO CÁO QA SPLIT V2.1")
    run.bold = True; run.font.size = Pt(18)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run("CQ và LO · hybrid scenario · registry khóa ngày 28/09/2026").italic = True

    heading(doc, "1. Kết luận điều hành")
    para(doc, "Registry Split V2.1 của cả CQ và LO đã được xây dựng đầy đủ và QA22 PASS ở W1–W3. V2.1 thay thế artifact V2 strict-purge trước đó; không có enrollment nào bị purge. Đánh giá bổ sung ngày 29/09 phát hiện ba điều kiện cần chốt trước khi materialize: support E/G của LO, đồng bộ calendar CQ–LO và offering dài.")
    para(doc, "Quyết định: V2.1 vẫn là bằng chứng split/audit hợp lệ, nhưng không materialize thành release thực nghiệm. V2.2 sẽ giữ CQ calendar làm anchor, re-cut LO với rarest_first và ghi long_offering_flag. Không được gộp S0, imputation, augmentation hoặc model results của V1/V2 cũ vào meta-release V2.2.", "Quyết định: ")

    heading(doc, "2. Quy tắc V2.1 theo tài liệu cập nhật 28/09")
    para(doc, "Đơn vị gán là offering kèm timeline_source; mỗi offering chỉ có một split trong mỗi window. Offering được sắp theo offering_end_date. A là phần lịch sử sớm; future pool được chia thành ba lát thời gian liên tiếp, rồi chỉ trong mỗi lát mới phân tầng validation/test theo nhãn hiếm và quy mô offering.")
    para(doc, "W1: TRAIN=A; VALIDATION=B; TEST=C.  W2: TRAIN=A+B+C; VALIDATION=D; TEST=E.  W3: TRAIN=A+B+C+D+E; VALIDATION=F; TEST=G.")
    para(doc, "QA22 V2.1 kiểm tra: H1 không trùng offering giữa split; H2 max(offering_end_date TRAIN) không muộn hơn min(offering_end_date evaluation); H3 validation/test không rỗng và đạt ngưỡng tối thiểu. ev_train_overlap_share và days_train_end_to_test_start chỉ là chỉ số báo cáo, không là điều kiện loại mẫu.")

    heading(doc, "3. Vì sao V2.1 thay thế V2 strict-purge")
    para(doc, "V2 strict-purge dùng offering_start_date để loại evaluation offering mở trước khi TRAIN kết thúc. Với các MOOC diễn ra đồng thời, biện pháp này đã loại khoảng 90–100% evaluation ở nhiều window. V2.1 giữ nguyên evaluation (purge_mode=NONE), bảo toàn quy mô mẫu và công bố overlap thay vì cố ép overlap bằng 0.")
    para(doc, "Đánh giá hậu nghiệm phải tách TEMPORAL STRICT và OVERLAP. STRICT được xác định tại từng P1–P4 khi cutoff phase không sớm hơn tau_w, là thời điểm nhãn cuối cùng của TRAIN đã có.")

    heading(doc, "4. QA22 và quy mô evaluation")
    table(doc, ["Task", "W", "Validation", "Test", "Ngưỡng eval", "QA22", "Overlap", "Gap ngày", "History ngày"], cq[0] + lo[0])
    para(doc, "Tất cả sáu task-window đạt end_order_ok và eval_size_ok. Gap âm là dấu hiệu offering chồng lịch, được giữ và báo cáo theo quy ước V2.1.")

    heading(doc, "5. Metadata registry, purge và label drift")
    table(doc, ["Task", "W", "Purge mode", "n_purged", "Tỷ lệ purge", "Drift JSD từ window trước"], cq[1] + lo[1])
    para(doc, "Metadata chung: scenario=hybrid, split_version=v2.1, purge_gt_half_eval=false. JSD drift không bị san bằng vì phản ánh biến động nhãn thật theo thời gian.")

    heading(doc, "6. Temporal-strict coverage cho evaluation")
    table(doc, ["Task", "Split", "P1 strict", "P2 strict", "P3 strict", "P4 strict"], cq[2] + lo[2])
    para(doc, "Các tỷ lệ trên là cơ sở để stratify kết quả model. Metric tổng hợp không thay thế metric STRICT; hai loại cần được lưu như các slice đánh giá riêng.")

    heading(doc, "7. Support lớp nhỏ nhất trong validation/test")
    table(doc, ["Task", "Nhãn", "Support nhỏ nhất"], cq[3] + lo[3])
    para(doc, "CQ có support evaluation đủ lớn cho mọi lớp: average tối thiểu 2,462; good tối thiểu 3,169; warning tối thiểu 156,692. CQ vẫn mất cân bằng mạnh nên không dùng Accuracy làm metric chính.")
    para(doc, "LO có E=22 và G=81 ở split bất lợi nhất: metric per-class LO phải luôn kèm support và khoảng tin cậy; không nên kết luận độ ổn định chỉ từ một window.")

    heading(doc, "8. Cấu trúc artifact và trạng thái release")
    para(doc, "Mỗi task lưu registry tại tasks/{CQ|LO}/hybrid/split_registry_v2_1/: manifest/, qa22_v2_1/, split_registry/, split_actual_ratios/, split_label_distribution/, temporal_strict_context/, temporal_profile_monthly/, duration_summary/ và block_label_audit/.")
    para(doc, "V2.1 không được materialize. Code V2.2 đã bổ sung calendar_boundaries/, temporal_strict_share/, duration_days, long_offering_flag và long-offering audit. Sau khi V2.2 QA pass, các artifact tiếp theo là split_manifest_v2_2/, phase_views_v2_2/, test_prefix_views_v2_2/; split_version=v2.2 phải đi xuyên suốt manifest và meta-observation.")

    heading(doc, "9. Hành động tiếp theo")
    para(doc, "(1) Build CQ V2.2 để xuất CQ calendar boundaries. (2) Build LO V2.2 với CQ boundaries và pairing=rarest_first. (3) Kiểm QA22, support E/G, strict/overlap theo window×split×phase, và long-offering audit. (4) Materialize views V2.2. (5) Kiểm coverage sau join feature/label, rồi chạy S0 → imputation → augmentation → model. (6) Báo cáo prediction metrics tổng, STRICT và OVERLAP; tách riêng chi phí CPU/GPU/RAM/wall time theo run manifest.")

    doc.save(OUT)


if __name__ == "__main__":
    main()
