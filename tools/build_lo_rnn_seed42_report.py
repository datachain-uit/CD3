"""Build the LO V3.1 clean-grain RNN seed-42 execution report from L2 facts."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "LO" / "docs" / "REPORT_LO_V3_1.docx"
FACTS = ROOT / "_tmp_lo_rnn_facts" / "report_id=RNN_seed42_v3_1"
OUTPUT = ROOT / "LO" / "docs" / "REPORT_LO_V3.1_CLEAN_GRAIN_RNN_SEED42_2026-10-07.docx"


def clear_body(doc: Document) -> None:
    for node in list(doc._element.body):
        if node.tag != qn("w:sectPr"):
            doc._element.body.remove(node)


def font(run, size: float, bold: bool = False) -> None:
    run.bold = bold
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    run.font.size = Pt(size)


def heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12 if level == 1 else 7)
    p.paragraph_format.space_after = Pt(5)
    font(p.add_run(text), 14 if level == 1 else 12, True)


def paragraph(doc: Document, text: str) -> None:
    font(doc.add_paragraph().add_run(text), 11)


def bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    font(p.add_run("• " + text), 11)


def shade(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    value = OxmlElement("w:shd")
    value.set(qn("w:fill"), fill)
    props.append(value)


def cell(cell, value: object, bold: bool = False) -> None:
    cell.text = ""
    font(cell.paragraphs[0].add_run(str(value)), 10.5, bold)


def table(doc: Document, headers: list[str], rows: list[list[object]]) -> None:
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.style = "Table Grid"
    for target, value in zip(tbl.rows[0].cells, headers):
        cell(target, value, True)
        shade(target, "D9EAF7")
    for values in rows:
        for target, value in zip(tbl.add_row().cells, values):
            cell(target, value)
    doc.add_paragraph()


def fmt(value: float, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}"


def main() -> None:
    paths = {
        "metrics": FACTS / "metrics_test_long.parquet",
        "sanity": FACTS / "sanity_summary_p1_p4_mean.parquet",
        "resources": FACTS / "resource_long.parquet",
        "runs": FACTS / "run_inventory.parquet",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing LO facts: " + ", ".join(missing))
    metrics = pd.read_parquet(paths["metrics"])
    sanity = pd.read_parquet(paths["sanity"])
    resources = pd.read_parquet(paths["resources"])
    runs = pd.read_parquet(paths["runs"])
    if (len(metrics), len(sanity), len(resources), len(runs)) != (204, 51, 51, 51):
        raise ValueError("Expected 204 TEST metrics and 51 model/sanity/resource rows")

    rank = (sanity.groupby("pipeline_id", as_index=False)
            [["acctempo_m3", "s_perf", "s_san_plus", "s_cal"]].mean()
            .sort_values("acctempo_m3", ascending=False))
    per_window = sanity.pivot(index="pipeline_id", columns="window_id", values="acctempo_m3")
    phases = (metrics.groupby(["pipeline_id", "phase_id"], as_index=False)
              [["f1_macro", "balanced_accuracy", "mcc", "top_label_ece_15"]].mean())

    doc = Document(TEMPLATE)
    clear_body(doc)
    doc.styles["Normal"].font.name = "Times New Roman"
    doc.styles["Normal"].font.size = Pt(11)
    doc.styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(title.add_run("BÁO CÁO LO — V3.1 CLEAN-GRAIN\nRNN SEED 42: S0–S3 HOÀN TẤT"), 18, True)
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(subtitle.add_run("Đơn vị: learner–course enrollment | scenario=hybrid | cập nhật 07/10/2026"), 11)
    paragraph(doc, "Phạm vi báo cáo là LO_V3_1: final-score catalog-normalized, loại course không có scored signal; split_version=v3_1 và phase_version=wide_prefix_v3_1. Chỉ facts của 51 RNN seed 42 khớp release identity hiện hành được dùng.")

    heading(doc, "Tóm tắt điều hành")
    table(doc, ["Hạng mục", "Trạng thái", "Kết luận"], [
        ["Label LO", "LOCKED", "Activity-derived final_score catalog-normalized; I/D, G, E; loại course không có scored signal."],
        ["Input và grain", "LOCKED / GRAIN_OK", "LO_V3_1; split v3_1; mỗi model input đúng một dòng/enrollment."],
        ["S1 imputation", "SUCCESS 15/15", "V0, V1, V5, V9, V13 × W1–W3."],
        ["S2 augmentation", "SUCCESS 36/36", "TRAIN-only; seed augmentation cố định 42."],
        ["S3 RNN", "SUCCESS 51/51", "Đủ TEST metrics, sanity và resource facts trên NVIDIA L4 BF16."],
        ["Kết quả sơ bộ", "V2 cao nhất", f"Mean TEST AccTEMPO-M3 P1–P4/W1–W3 = {fmt(rank.iloc[0].acctempo_m3)}; chưa test-select."],
    ])

    heading(doc, "1. Nhãn, grain và split LO V3.1")
    paragraph(doc, "Nhãn primary là final_score suy ra từ hoạt động được chấm theo catalog course (video, assignment và final-chapter exam khi khả dụng). Nó không phải final grade quan sát độc lập, completion hay dropout. Catalog normalization dùng mẫu số scoreable activities; course không có scored signal bị loại thay vì gán mặc định I/D.")
    bullet(doc, "Đơn vị phân tích là enrollment_id; user_id/course_id/offering/timeline chỉ là context hoặc code categorical TRAIN-only.")
    bullet(doc, "Shared-calendar split V3.1 dùng registry làm nguồn duy nhất cho boundary, purge và label drift; không tái sử dụng manifest legacy/reference.")
    bullet(doc, "TEST P1–P4 tuân thủ prefix availability. Future slots giữ unavailable, không impute hay augment thành dữ liệu đã quan sát.")
    table(doc, ["Window", "TRAIN rows", "VALIDATION rows", "TEST rows mỗi prefix"], [
        ["W1", "1,787,557", "78,090", "78,591"],
        ["W2", "1,944,238", "200,842", "200,844"],
        ["W3", "2,345,924", "129,426", "130,073"],
    ])

    heading(doc, "2. S0/S1/S2 và contract anti-leakage")
    paragraph(doc, "S0 profile ALL_ROWS phân biệt missing đủ điều kiện với structural absence. Imputer/scaler chỉ fit TRAIN; transform toàn bộ TRAIN/VALIDATION/TEST prefix mà không dùng future values. S1 đạt 15/15, không có future imputation, preprocessor và model inputs đầy đủ.")
    table(doc, ["Pipeline", "Phương pháp", "Trạng thái W1–W3"], [
        ["V0", "zero-fill + masks", "SUCCESS"],
        ["V1", "median", "SUCCESS"],
        ["V5", "mean", "SUCCESS"],
        ["V9", "ExtraTrees light", "SUCCESS"],
        ["V13", "MICE: 3 vòng; fit tối đa 1,000,000 TRAIN rows", "SUCCESS"],
    ])
    table(doc, ["Parent imputer", "CDSMOTE", "SASMOTE", "RadiusSMOTE"], [
        ["V1 median", "V2", "V3", "V4"],
        ["V5 mean", "V6", "V7", "V8"],
        ["V9 ExtraTrees", "V10", "V11", "V12"],
        ["V13 MICE", "V14", "V15", "V16"],
    ])
    table(doc, ["Window", "Balanced TRAIN rows", "S2 status"], [
        ["W1", "1,835,932", "12/12 SUCCESS"],
        ["W2", "2,013,394", "12/12 SUCCESS"],
        ["W3", "2,415,656", "12/12 SUCCESS"],
    ])

    heading(doc, "3. RNN seed 42 — primary outcome")
    paragraph(doc, "Bảng dưới là AccTEMPO-M3 TEST trung bình qua P1–P4 trong từng window; Mean là trung bình W1–W3. Đây là outcome hiệu năng chính. V2 là median + CDSMOTE; V10 là ExtraTrees + CDSMOTE; V14 là MICE + CDSMOTE.")
    rows = []
    for item in rank.itertuples(index=False):
        pipeline = item.pipeline_id
        rows.append([pipeline, fmt(per_window.loc[pipeline, "W1"]), fmt(per_window.loc[pipeline, "W2"]),
                     fmt(per_window.loc[pipeline, "W3"]), fmt(item.acctempo_m3), fmt(item.s_perf)])
    table(doc, ["Pipeline", "W1", "W2", "W3", "Mean AccTEMPO-M3", "Mean S_perf"], rows)
    paragraph(doc, "V2 dẫn đầu primary outcome trong RNN seed 42. Khoảng cách với V10 rất nhỏ, nên không được gọi là quyết định cuối: shortlist vẫn phải được định nghĩa theo VALIDATION, sau đó mới chạy replication model seed 43/44.")

    heading(doc, "4. Chỉ số hỗ trợ theo phase")
    paragraph(doc, "Minh họa baseline V0 và V2 (leader theo AccTEMPO). Mỗi giá trị trung bình qua W1–W3; ECE-15 nhỏ hơn là tốt hơn.")
    rows = []
    for pipeline in ("V0", "V2"):
        for phase_id in ("P1", "P2", "P3", "P4"):
            row = phases[(phases.pipeline_id == pipeline) & (phases.phase_id == phase_id)].iloc[0]
            rows.append([pipeline, phase_id, fmt(row.f1_macro), fmt(row.balanced_accuracy), fmt(row.mcc), fmt(row.top_label_ece_15)])
    table(doc, ["Pipeline", "Phase", "Macro-F1", "Balanced accuracy", "MCC", "ECE-15"], rows)

    heading(doc, "5. Sanity, calibration và tài nguyên")
    paragraph(doc, "S_san+ v1 là data-quality/sanity metric chính; s_cal v2 là sensitivity. Cả hai không thay AccTEMPO-M3. Các thành phần s_leak, s_eff và s_drift được tính trên real rows theo recipe đã khóa.")
    rows = []
    for pipeline in ("V0", "V2", "V10", "V14"):
        row = sanity[sanity.pipeline_id == pipeline].mean(numeric_only=True)
        primary = rank[rank.pipeline_id == pipeline].iloc[0]
        rows.append([pipeline, fmt(primary.acctempo_m3), fmt(row.s_san_plus), fmt(row.s_ent), fmt(row.s_leak), fmt(row.s_eff), fmt(row.s_drift), fmt(primary.s_cal)])
    table(doc, ["Pipeline", "AccTEMPO", "S_san+", "s_ent", "s_leak", "s_eff", "s_drift", "s_cal"], rows)
    table(doc, ["Resource fact", "Giá trị"], [
        ["Run thành công", "51/51 RNN cells trên NVIDIA L4 với AMP bfloat16."],
        ["Tổng wall-clock", f"{resources.time_run_total_s.sum()/3600:.2f} giờ (50,020.6 giây)."],
        ["Median / max mỗi run", f"{resources.time_run_total_s.median():.1f} / {resources.time_run_total_s.max():.1f} giây."],
        ["CPU process time", f"{resources.cpu_process_s.sum()/3600:.2f} CPU-giờ; peak RAM telemetry không khả dụng."],
        ["Energy / cost", "Modal không cung cấp telemetry billing/energy cho các run này; không suy diễn CO2e hoặc USD."],
    ])

    heading(doc, "6. Truy vết và bước tiếp theo")
    paragraph(doc, "Mọi retry là attempt immutable. Status/exporter hiện chỉ nhận run khớp LO_V3_1, split registry V3.1, phase version và data_release_id đang active. Facts compact phục vụ báo cáo nằm ở L2, tách khỏi L1 prediction/checkpoint artifacts.")
    tree = (
        "tempo-data-v1/\n"
        "├── input/LO_v3_1/{release_manifest,phase_views,test_prefix_views/P1..P4}\n"
        "└── meta_release=imputation-v1/\n"
        "    ├── L1_runs/task=LO/feature_regime=LO_FULL_EARLY/window_id=W*/pipeline_id=V*/\n"
        "    └── L2_facts/report_exports/task=LO/report_id=RNN_seed42_v3_1/\n"
        "        ├── metrics_test_long.parquet (204 rows)\n"
        "        ├── sanity_test_long.parquet (204 rows)\n"
        "        ├── resource_long.parquet (51 rows)\n"
        "        └── run_inventory.parquet (51 rows)"
    )
    p = doc.add_paragraph()
    run = p.add_run(tree)
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    table(doc, ["Ưu tiên", "Bước tiếp theo", "Điều kiện"], [
        ["1", "Khóa shortlist theo VALIDATION, không dùng TEST ranking trong báo cáo này.", "Recipe được chốt trước replication."],
        ["2", "Chạy model seed 43/44 cho shortlist; sau đó LSTM/GRU/BiLSTM cùng contract.", "Báo cáo stability/CI paired theo window và phase."],
        ["3", "Báo cáo per-class support/recall, probability/confusion và calibration từ L2 facts.", "Không chọn winner bằng accuracy đơn lẻ."],
        ["4", "Đưa Radius fallback-nearest-neighbour rate vào phân tích augmentation.", "Cảnh báo nếu rate > 0.50 theo window."],
    ])
    paragraph(doc, "Kết luận: LO V3.1 clean-grain đã hoàn tất từ S0/S1/S2 đến RNN seed 42, với provenance khớp release hiện hành. V2 dẫn đầu AccTEMPO-M3 sơ bộ; diễn giải cuối vẫn cần validation-governed shortlist và replication, không test-select.")
    doc.core_properties.title = "LO V3.1 clean-grain — RNN seed 42 execution report"
    doc.core_properties.subject = "LO release, final-score label, S0-S3 execution and TEST facts"
    doc.core_properties.author = "CD3 experimental pipeline"
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
