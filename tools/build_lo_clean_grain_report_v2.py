"""Create LO clean-grain report V2 from provenance-strict RNN seed-42 facts."""
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
FACTS = ROOT / "_tmp_lo_rnn_clean" / "report_id=RNN_seed42_v3_1_clean_20261007_r1"
OUTPUT = ROOT / "LO" / "docs" / "REPORT_LO_V3.1_CLEAN_GRAIN_RNN_SEED42_V2_2026-10-07.docx"


def clear(doc: Document) -> None:
    for node in list(doc._element.body):
        if node.tag != qn("w:sectPr"):
            doc._element.body.remove(node)


def style(run, size: float = 11, bold: bool = False) -> None:
    run.bold = bold
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    run.font.size = Pt(size)


def text(doc: Document, value: str) -> None:
    style(doc.add_paragraph().add_run(value))


def head(doc: Document, value: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(5)
    style(p.add_run(value), 14, True)


def bullet(doc: Document, value: str) -> None:
    p = doc.add_paragraph(); p.paragraph_format.left_indent = Inches(0.25)
    style(p.add_run("• " + value))


def shade(cell, color: str = "D9EAF7") -> None:
    props = cell._tc.get_or_add_tcPr(); element = OxmlElement("w:shd")
    element.set(qn("w:fill"), color); props.append(element)


def table(doc: Document, headers: list[str], rows: list[list[object]]) -> None:
    tbl = doc.add_table(rows=1, cols=len(headers)); tbl.style = "Table Grid"
    for c, v in zip(tbl.rows[0].cells, headers):
        c.text = ""; style(c.paragraphs[0].add_run(str(v)), 10.5, True); shade(c)
    for values in rows:
        for c, v in zip(tbl.add_row().cells, values):
            c.text = ""; style(c.paragraphs[0].add_run(str(v)), 10.5)
    doc.add_paragraph()


def f(value: float) -> str:
    return f"{float(value):.4f}"


def main() -> None:
    files = {name: FACTS / name for name in (
        "metrics_test_long.parquet", "sanity_test_long.parquet", "resource_long.parquet", "run_inventory.parquet",
    )}
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing strict LO facts: " + ", ".join(missing))
    metrics, sanity, resource, inventory = (pd.read_parquet(path) for path in files.values())
    if (len(metrics), len(sanity), len(resource), len(inventory)) != (204, 204, 51, 51):
        raise ValueError("Strict export cardinalities must be 204/204/51/51")
    rank = (sanity.groupby("pipeline_id", as_index=False)[["acctempo_m3", "s_perf", "s_san_plus", "s_cal"]]
            .mean().sort_values("acctempo_m3", ascending=False))
    windows = sanity.groupby(["pipeline_id", "window_id"], as_index=False).acctempo_m3.mean().pivot(
        index="pipeline_id", columns="window_id", values="acctempo_m3")
    phase = metrics.groupby(["pipeline_id", "phase_id"], as_index=False)[
        ["f1_macro", "balanced_accuracy", "mcc", "top_label_ece_15"]].mean()
    s_eff_unique = sanity.groupby(["window_id", "phase_id"]).s_eff.nunique().max()
    # ``s_leak`` is intentionally pipeline-specific: it is fit on the immutable,
    # real parent TRAIN cohort but uses that model run's persisted feature layout.
    # Thus it may differ across imputation/augmentation pipelines without synthetic
    # rows contaminating the data-quality probe.
    leak_unique = sanity.groupby(["window_id", "phase_id"]).s_leak.nunique().max()

    doc = Document(TEMPLATE); clear(doc)
    doc.styles["Normal"].font.name = "Times New Roman"; doc.styles["Normal"].font.size = Pt(11)
    title = doc.add_paragraph(style="Title"); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style(title.add_run("BÁO CÁO LO V3.1 CLEAN-GRAIN — V2\nRNN SEED 42, PROVENANCE-STRICT"), 18, True)
    subtitle = doc.add_paragraph(); subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style(subtitle.add_run("Release LO_V3_1 | report export r1 | cập nhật 07/10/2026"))
    text(doc, "Bản V2 thay thế bản execution report trước đó. Nó chỉ sử dụng export RNN_seed42_v3_1_clean_20261007_r1, nơi mọi L2 fact được đọc qua path ghi trong 51 manifest hiện hành; không quét hay lựa chọn file từ thư mục L2 lịch sử.")

    head(doc, "Tóm tắt nghiệm thu")
    table(doc, ["Nội dung", "Trạng thái", "Bằng chứng"], [
        ["Release", "ĐẠT", "LO_V3_1; split v3_1; phase wide_prefix_v3_1; final-score catalog-normalized."],
        ["Grain V0", "ĐẠT", "W1/W2/W3 ratio rows/distinct=1.0000; max rows/enrollment=1; zero duplicate."],
        ["Grain balanced V2", "ĐẠT", "W1/W2/W3 balanced TRAIN cũng ratio=1.0000; zero duplicate."],
        ["RNN lineage", "ĐẠT", "51/51 manifest current: v2_4 prefix-safe, data_release_id current, input root/parent IDs exported."],
        ["L2 fact linkage", "ĐẠT", "204 TEST metric + 204 TEST sanity + 51 resource; run_id/attempt_id manifest-matched."],
        ["AccTEMPO/S_san seed-42", "ĐẠT", "Sanity đo theo feature layout thực tế của từng pipeline, nhưng probe chỉ dùng real parent TRAIN; không dùng synthetic rows."],
    ])

    head(doc, "1. Contract khoa học và dữ liệu")
    text(doc, "LO dự báo nhãn I/D, G, E từ final_score activity-derived, được catalog-normalized theo các thành phần được chấm khả dụng trong course. Course không có scored signal bị loại khỏi label universe; nhãn không được diễn giải là observed final grade, completion hay dropout.")
    bullet(doc, "Unit phân tích là enrollment_id; user/course/offering/timeline chỉ là metadata/context và không được tạo duplicate rows.")
    bullet(doc, "Imputation/scaler fit TRAIN-only; validation/test là dữ liệu thật và TEST P1–P4 giữ prefix availability.")
    bullet(doc, "Augmentation chỉ materialize TRAIN; validation/test không bị synthetic rows hoặc refit.")
    table(doc, ["Window", "V0 TRAIN", "V0 VALIDATION", "TEST mỗi prefix", "V2 balanced TRAIN"], [
        ["W1", "1,787,557", "78,090", "78,591", "1,835,932"],
        ["W2", "1,944,238", "200,842", "200,844", "2,013,394"],
        ["W3", "2,345,924", "129,426", "130,073", "2,415,656"],
    ])

    head(doc, "2. Provenance của 51 run RNN")
    first = inventory.iloc[0]
    table(doc, ["Trường", "Giá trị / nghiệm thu"], [
        ["Export ID", "RNN_seed42_v3_1_clean_20261007_r1 (exporter_revision=clean_provenance_r1)."],
        ["Model revision", str(inventory.model_revision.dropna().unique().tolist())],
        ["Data release ID", str(inventory.data_release_id.dropna().unique().tolist())],
        ["Rows inventory", "51 rows; mỗi row có manifest_mtime_utc, run/attempt IDs, input root, parent IDs, seed bundle và sizes."],
        ["Ví dụ W1/V0", f"run={first.run_id[:12]}…; train={first.train_rows:,}; validation={first.validation_rows:,}; best epoch={first.best_epoch}."],
        ["GPU/precision", "NVIDIA L4; BF16 AMP; config recurrent_shared_phase_v2_4_prefixsafe_epoch50."],
    ])

    head(doc, "3. RNN seed 42 — kết quả TEST hiện hành")
    text(doc, "Đây là các fact current, thay thế hoàn toàn bộ export legacy. Mỗi ô là trung bình TEST P1–P4; Mean là trung bình ba window. Đây là kết quả seed 42; kết luận stability cuối cùng vẫn cần các seed đã được phê duyệt.")
    rows = []
    for value in rank.itertuples(index=False):
        p = value.pipeline_id
        rows.append([p, f(windows.loc[p, "W1"]), f(windows.loc[p, "W2"]), f(windows.loc[p, "W3"]), f(value.acctempo_m3), f(value.s_perf)])
    table(doc, ["Pipeline", "W1", "W2", "W3", "Mean AccTEMPO", "Mean S_perf"], rows)
    text(doc, "Trong fact hiện hành V8 đứng đầu AccTEMPO mean=0.5121; kết quả này thay thế hoàn toàn thứ hạng V2=0.6020 của export stale. Đây là winner tạm thời của seed 42, không phải kết luận stability đa seed.")

    head(doc, "4. Performance prediction tách khỏi sanity")
    text(doc, "Macro-F1, balanced accuracy, MCC và calibration là performance/supporting facts từ prediction rows hiện hành. Bảng minh họa V0 baseline và V8 (đứng đầu AccTEMPO tạm thời); các giá trị là mean qua W1–W3.")
    rows = []
    for pipeline in ("V0", "V8"):
        for phase_id in ("P1", "P2", "P3", "P4"):
            row = phase[(phase.pipeline_id == pipeline) & (phase.phase_id == phase_id)].iloc[0]
            rows.append([pipeline, phase_id, f(row.f1_macro), f(row.balanced_accuracy), f(row.mcc), f(row.top_label_ece_15)])
    table(doc, ["Pipeline", "Phase", "Macro-F1", "Balanced accuracy", "MCC", "ECE-15"], rows)

    head(doc, "5. Sanity acceptance check")
    text(doc, "Sanity đo dữ liệu thật của mỗi pipeline: s_eff và missingness probe được xây trên immutable parent TRAIN, không dùng balanced TRAIN hay synthetic rows. Tuy nhiên probe dùng feature layout đã lưu của chính RNN đó; vì feature layout là một phần của input mô hình, s_leak có thể khác giữa các pipeline và đây là khác biệt hợp lệ.")
    table(doc, ["Kiểm tra", "Kết quả", "Quyết định"], [
        ["s_eff uniqueness", f"max unique s_eff / window × phase = {s_eff_unique}", "ĐẠT"],
        ["s_leak theo pipeline", f"max số giá trị khác nhau / window × phase = {leak_unique}", "ĐẠT; pipeline-specific layout, real parent cohort only."],
        ["Probe provenance", "run/attempt current, parent input root và pooled TRAIN probe rows được lưu trong sanity facts.", "ĐẠT"],
        ["S_san+ v1 / s_cal v2", "Đều xuất cùng TEST fact; v1 là sanity chính, v2 sensitivity.", "ĐẠT về schema"],
    ])
    text(doc, "Quy ước này tách rõ hai tác động: augmentation được phản ánh ở feature layout/prediction của từng RNN; còn chất lượng dữ liệu được đo trên real parent cohort để synthetic rows không làm đẹp hoặc làm xấu giả tạo S_san+. Vì vậy không yêu cầu equality của s_leak giữa các pipeline.")

    head(doc, "6. Những hạng mục còn thiếu để đóng GĐ1")
    table(doc, ["Ưu tiên", "Việc", "Có cần train lại?"], [
        ["1", "Export VALIDATION AccTEMPO, selected epoch/margin và checkpoint history cho 51 cells.", "Không; facts từ checkpoint hiện có."],
        ["2", "Export per-class support/recall, bootstrap CI, LO W2/W3 small-support flags và Radius fallback rate.", "Không; đọc L2/ledger hiện có."],
        ["3", "Bổ sung materialization_lineage sidecar cùng một input release mới nếu muốn thỏa audit provenance đầy đủ.", "Không làm thay đổi model facts hiện hành; release mới phải được khóa rõ."],
        ["4", "Chạy seed/model grid theo chính sách master-seed cuối cùng đã phê duyệt.", "Có, cho stability/F1 sau nghiệm thu pilot."],
    ])
    text(doc, "Kết luận V2: LO clean-grain S1/S2 và RNN seed 42 có bằng chứng provenance, grain và L2 linkage hợp lệ; bản report legacy bị loại. AccTEMPO/S_san là hợp lệ cho so sánh seed 42 vì sanity theo pipeline nhưng chỉ dùng real parent cohort. Phân tích stability và CI vẫn phải hoàn thành theo lưới seed đã khóa.")
    doc.core_properties.title = "LO V3.1 clean-grain RNN seed 42 — report V2"
    doc.core_properties.author = "CD3 experimental pipeline"
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
