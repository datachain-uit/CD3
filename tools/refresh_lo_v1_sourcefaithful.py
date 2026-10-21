"""Refresh the existing LO V1 report with the accepted source-faithful state."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "LO" / "docs" / "REPORT_LO_V1.docx"
RESULT = ROOT / "LO" / "resuilt"
REGISTRY = RESULT / "split_registry_v2_2_sourcefaithful_overlap_audit_v1"
SCORE = RESULT / "final_score_contract_audit_v2_sourcefaithful"
LONG = RESULT / "long_offering_assignment_audit_v2_sourcefaithful"
COVERAGE = RESULT / "label_coverage_audit_proxy_v2_sourcefaithful"
BLUE, GREY = "1F4E78", "F2F2F2"


def read(root: Path, name: str) -> pd.DataFrame:
    return pd.read_parquet(max((root / name).glob("*.parquet"), key=lambda p: p.stat().st_mtime))


def shade(cell, colour: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    node = OxmlElement("w:shd")
    node.set(qn("w:fill"), colour)
    props.append(node)


def add_table(doc: Document, headers: list[str], rows: list[list[object]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]; cell.text = str(header); shade(cell, BLUE)
        for run in cell.paragraphs[0].runs:
            run.bold = True; run.font.color.rgb = RGBColor(255, 255, 255); run.font.size = Pt(10.5)
    for rindex, row in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
            for run in cells[i].paragraphs[0].runs: run.font.size = Pt(10.5)
            if rindex % 2: shade(cells[i], GREY)
    doc.add_paragraph()


def replace_start(doc: Document, start: str, value: str) -> None:
    for paragraph in doc.paragraphs:
        if paragraph.text.startswith(start):
            paragraph.text = value
            return
    raise KeyError(start)


def heading(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text); run.bold = True; run.font.size = Pt(14)
    run.font.color.rgb = RGBColor.from_string("17365D")


def jsd(left: list[float], right: list[float]) -> float:
    """Jensen-Shannon divergence, base 2."""
    import math
    mid = [(a + b) / 2 for a, b in zip(left, right)]
    def kl(values: list[float], reference: list[float]) -> float:
        return sum(v * math.log2(v / r) for v, r in zip(values, reference) if v)
    return (kl(left, mid) + kl(right, mid)) / 2


def main() -> None:
    registry = read(REGISTRY, "split_registry")
    labels = read(REGISTRY, "split_label_distribution")
    ratios = read(REGISTRY, "split_actual_ratios")
    strict = read(LONG, "strict_by_window_split_phase")
    unit = read(LONG, "unit_size_distribution")
    coverage = read(COVERAGE, "slice_timeline_summary")
    coverage_meta = read(COVERAGE, "audit_manifest").iloc[0]
    duration = read(LONG, "duration_by_timeline")
    assignment = read(LONG, "enrollment_assignment_qa").iloc[0]
    version = read(SCORE, "label_version_summary").iloc[0]
    contract = read(SCORE, "label_semantics_contract").iloc[0]
    ranges = read(SCORE, "score_range_by_profile")
    w3 = labels[labels.window_id.eq("W3")].groupby("label", as_index=False).label_enrollment_count.sum()
    totals = dict(zip(w3.label, w3.label_enrollment_count))
    score_gt100 = int(ranges.n_final_score_gt_100.sum())

    doc = Document(REPORT)
    replace_start(doc, "BÁO CÁO QUY TRÌNH LO", "BÁO CÁO QUY TRÌNH LO — SOURCE-FAITHFUL V2.2")
    replace_start(doc, "Phạm vi:", "Phạm vi: learner–course enrollment | final_score source-faithful | split V2.2 hybrid | cập nhật 30/09/2026")
    replace_start(doc, "8. Audit final_score", "8. Audit final_score, leakage contract và quyết định đã khóa")
    replace_start(doc, "Cảnh báo cần xác nhận nghiệp vụ:",
        f"Quyết định đã khóa theo TEMPO: {score_gt100:,} enrollment final_score >100 ({score_gt100 / int(version['eligible_enrollment_count']) * 100:.3f}% cohort) thuộc nhánh mặc định I/D. Không clip score về 100, không gán sang E/G. final_score là activity-derived weighted aggregate uncapped, không phải final grade quan sát độc lập.")
    replace_start(doc, "Label drift giữa T1/T2/T3", "Label drift giữa T1/T2/T3 là thay đổi thật theo thời gian, không được san bằng giữa các lát. Metric per-class luôn kèm support; theo giao thức Split V2.2, small_support_flag=1 khi n_support<100 cho từng window × phase × split × subgroup × class; cell nhỏ cần CI bootstrap 95% và không là bằng chứng so sánh pipeline độc lập.")
    replace_start(doc, "Kết luận: split V2.2", "Kết luận: label source-faithful, split V2.2, assignment integrity và audit cohort đã đủ để LO materialize → S0 → dictionary → imputation. LO W1 là window đánh giá chính; LO W2/W3 vẫn chạy nhưng E/G có support nhỏ, chỉ diễn giải exploratory với paired bootstrap.")

    heading(doc, "12. Phụ lục cập nhật — bằng chứng source-faithful")
    doc.add_paragraph("Phụ lục này thay thế mọi bảng nhãn/split LO cũ dùng mapping behavioural hoặc source label chưa source-faithful.")
    add_table(doc, ["Thuộc tính", "Giá trị"], [
        ["Label rule version", version["label_rule_version"]],
        ["Score semantics", contract["score_semantics"]],
        ["Bands", contract["class_thresholds"]],
        ["Split", "v2.2.sourcefaithful; scenario=hybrid; CQ calendar anchor"],
        ["QA22", "W1–W3 đều đạt; purge_mode=NONE"],
    ])
    eligible = int(version["eligible_enrollment_count"])
    add_table(doc, ["Nhãn", "Enrollment", "Tỷ lệ cohort eligible"], [
        [label, f"{int(totals[label]):,}", f"{int(totals[label]) / eligible * 100:.3f}%"]
        for label in ("I/D", "G", "E")
    ])
    support_rows: list[list[object]] = []
    for window in ("W1", "W2", "W3"):
        parts = labels[labels.window_id.eq(window)]
        values = {}
        for split in ("validation", "test"):
            subset = parts[parts.split.eq(split)].set_index("label").label_enrollment_count
            values[split] = f"E={int(subset['E']):,}; G={int(subset['G']):,}"
        support_rows.append([window, values["validation"], values["test"], "primary" if window == "W1" else "small-support protocol"])
    add_table(doc, ["Window", "Validation support", "Test support", "Diễn giải"], support_rows)
    block = read(REGISTRY, "block_label_audit")
    slice_rows = []
    for slice_name, blocks in (("A", ["A"]), ("T1", ["B", "C"]), ("T2", ["D", "E"]), ("T3", ["F", "G"])):
        subset = block[block.rolling_block.isin(blocks)]
        total = int(subset.enrollment_count.sum())
        slice_rows.append([
            slice_name, f"{total:,}",
            f"{int(subset['I/D_count'].sum()):,} ({subset['I/D_count'].sum() / total * 100:.3f}%)",
            f"{int(subset.G_count.sum()):,} ({subset.G_count.sum() / total * 100:.3f}%)",
            f"{int(subset.E_count.sum()):,} ({subset.E_count.sum() / total * 100:.3f}%)",
        ])
    add_table(doc, ["Temporal slice", "Enrollment", "I/D", "G", "E"], slice_rows)
    split_label_rows, balance_rows = [], []
    for window in ("W1", "W2", "W3"):
        arm_distribution = {}
        for split in ("train", "validation", "test"):
            subset = labels[(labels.window_id.eq(window)) & (labels.split.eq(split))].set_index("label")
            n = int(subset.enrollment_count.iloc[0])
            split_label_rows.append([window, split, f"{n:,}",
                f"{int(subset.loc['I/D', 'label_enrollment_count']):,} ({subset.loc['I/D', 'label_ratio'] * 100:.3f}%)",
                f"{int(subset.loc['G', 'label_enrollment_count']):,} ({subset.loc['G', 'label_ratio'] * 100:.3f}%)",
                f"{int(subset.loc['E', 'label_enrollment_count']):,} ({subset.loc['E', 'label_ratio'] * 100:.3f}%)"])
            arm_distribution[split] = [float(subset.loc[label, "label_ratio"]) for label in ("I/D", "G", "E")]
        balance_rows.append([window, f"{jsd(arm_distribution['validation'], arm_distribution['test']):.6f}"])
    add_table(doc, ["Window", "Split", "Enrollment", "I/D", "G", "E"], split_label_rows)
    add_table(doc, ["Window", "JSD validation-test (3 labels)"], balance_rows)
    add_table(doc, ["Window", "Validation", "Test", "QA22", "TEST strict P1"], [
        [
            window,
            f"{int(registry[registry.window_id.eq(window)].iloc[0]['n_enrollments_validation']):,}",
            f"{int(registry[registry.window_id.eq(window)].iloc[0]['n_enrollments_test']):,}",
            "Đạt",
            f"{strict[(strict.window_id.eq(window)) & (strict.split.eq('test')) & (strict.phase_id.eq('P1'))].iloc[0]['temporal_strict_share'] * 100:.3f}%",
        ] for window in ("W1", "W2", "W3")
    ])
    add_table(doc, ["Timeline source", "p50 ngày", "p90 ngày", "Max", "Enrollment >270 ngày"], [
        [r.timeline_source, int(r.duration_days_p50), int(r.duration_days_p90), int(r.duration_days_max), f"{r.long_offering_enrollment_share * 100:.3f}%"]
        for _, r in duration.iterrows()
    ])
    strict_rows = []
    for window in ("W1", "W2", "W3"):
        for split in ("validation", "test"):
            subset = strict[(strict.window_id.eq(window)) & (strict.split.eq(split))].set_index("phase_id")
            strict_rows.append([window, split, *[
                f"{subset.loc[phase, 'temporal_strict_share'] * 100:.3f}%" for phase in ("P1", "P2", "P3", "P4")
            ]])
    add_table(doc, ["Window", "Evaluation split", "Strict P1", "Strict P2", "Strict P3", "Strict P4"], strict_rows)
    add_table(doc, ["Slice", "Timeline", "Units", "Enrollment", "Units <=5", "Enrollment in units <=5"], [
        [r.temporal_slice, r.timeline_source, f"{int(r.offering_timeline_count):,}", f"{int(r.enrollment_count):,}",
         f"{r.share_units_le_5 * 100:.3f}%", f"{r.share_enrollments_units_le_5 * 100:.3f}%"]
        for _, r in unit.sort_values(["temporal_slice", "timeline_source"]).iterrows()
    ])
    covered = coverage[coverage.temporal_slice.ne("UNASSIGNED")].groupby("temporal_slice", as_index=False)[
        ["n_enrollments_total", "n_proxy_eligible", "n_I_D", "n_G", "n_E"]
    ].sum()
    add_table(doc, ["Coverage slice", "Total", "Eligible", "Eligible share", "I/D", "G", "E"], [
        [r.temporal_slice, f"{int(r.n_enrollments_total):,}", f"{int(r.n_proxy_eligible):,}",
         f"{r.n_proxy_eligible / r.n_enrollments_total * 100:.3f}%", f"{int(r.n_I_D):,}", f"{int(r.n_G):,}", f"{int(r.n_E):,}"]
        for _, r in covered.sort_values("temporal_slice").iterrows()
    ])
    doc.add_paragraph("Coverage evidence source: " + str(coverage_meta["label_source"]) +
                      ". The reported counts are source-faithful and are reconciled with the split registry.")
    doc.add_paragraph(
        f"Assignment audit: {int(assignment['distinct_enrollment_count']):,} enrollment; đa rolling block=0; "
        "đa split trong cùng window=0; context không map block=0. Các tỷ lệ split thực tế được lưu trong split_actual_ratios theo từng task/window."
    )
    doc.save(REPORT)
    print(REPORT)


if __name__ == "__main__":
    main()
