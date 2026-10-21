"""Generate the compact CQ RNN seed-42 screening report from local runner logs.

This report intentionally labels the available scores as validation selection
scores.  It never substitutes old V1-release TEST parquet files for the locked
V2.2 experiment.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
LOG_ROOT = ROOT / "logs" / "model_grid"
OUT = ROOT / "CQ" / "docs" / "REPORT_CQ_RNN_SEED42_V2_2_2026-10-02.docx"
EXPORT_ROOT = ROOT / "downloads" / "analysis" / "cq_rnn_seed42_v2_2"
WINDOWS = ("W1", "W2", "W3")
PIPELINES = tuple(f"V{i}" for i in range(17))
PIPELINE_NAMES = {
    "V0": "Zero-fill + masks", "V1": "Median", "V2": "Median + CDSMOTE",
    "V3": "Median + SASMOTE", "V4": "Median + RadiusSMOTE", "V5": "Mean",
    "V6": "Mean + CDSMOTE", "V7": "Mean + SASMOTE", "V8": "Mean + RadiusSMOTE",
    "V9": "ExtraTrees", "V10": "ExtraTrees + CDSMOTE", "V11": "ExtraTrees + SASMOTE",
    "V12": "ExtraTrees + RadiusSMOTE", "V13": "MICE", "V14": "MICE + CDSMOTE",
    "V15": "MICE + SASMOTE", "V16": "MICE + RadiusSMOTE",
}
NAME_RE = re.compile(r"^(W[123])_(V\d+)_RNN_seed42\.(model|sanity)\.log$")
EPOCH_RE = re.compile(r'^\{"best_epoch": .*"event": "epoch_complete".*$')


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_text(cell, text: str, bold: bool = False, size: float = 9.5) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = bold
    run.font.name = "Aptos"
    run.font.size = Pt(size)


def add_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True
    for cell, value in zip(table.rows[0].cells, headers):
        set_cell_text(cell, value, bold=True, size=9.5)
        shade(cell, "1F4E78")
        for run in cell.paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255)
    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row):
            set_cell_text(cell, str(value))
    doc.add_paragraph()


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_heading(text, level=level)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)


def completed_scores() -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], bool], dict[tuple[str, str], bool]]:
    """Return the latest completed model score and completion flags per cell."""
    models: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    sanity: dict[tuple[str, str], bool] = defaultdict(bool)
    for path in LOG_ROOT.rglob("*_RNN_seed42.*.log"):
        m = NAME_RE.match(path.name)
        if not m:
            continue
        window, pipeline, kind = m.groups()
        # Tee-Object on Windows PowerShell writes UTF-16LE with a BOM, while
        # manually captured logs may be UTF-8.  Detect the BOM so both are
        # parsed rather than silently producing an empty report.
        payload = path.read_bytes()
        raw = payload.decode("utf-16" if payload.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8", errors="replace")
        key = (pipeline, window)
        if kind == "sanity":
            sanity[key] = sanity[key] or ('"records": 8' in raw)
            continue
        if '"event": "run_finished"' not in raw:
            continue
        epoch_scores = []
        for line in raw.splitlines():
            if not EPOCH_RE.match(line):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            score = record.get("best_validation_macro_f1_mean_p1_p4")
            if isinstance(score, (float, int)):
                epoch_scores.append(float(score))
        # The pre-progress-logging W1 V0 run is valid but has no local score.
        score = max(epoch_scores) if epoch_scores else float("nan")
        models[key].append((path.stat().st_mtime, score))
    score_out: dict[tuple[str, str], float] = {}
    model_out: dict[tuple[str, str], bool] = {}
    for key, values in models.items():
        latest = max(values, key=lambda item: item[0])
        model_out[key] = True
        score_out[key] = latest[1]
    return score_out, model_out, sanity


def status(model: bool, sanity: bool) -> str:
    if model and sanity:
        return "Complete"
    if model:
        return "Model only"
    return "Pending"


def score_text(value: float | None) -> str:
    if value is None:
        return "—"
    if value != value:  # nan
        return "logged run; score unavailable"
    return f"{value:.4f}"


def load_official_export():
    """Load the compact, immutable L2 export created by export_cq_rnn_facts."""
    import pandas as pd

    required = {
        "metrics_long": "metrics_test_long.parquet",
        "test": "test_summary_p1_p4_mean.parquet",
        "sanity_long": "sanity_test_long.parquet",
        "sanity": "sanity_summary_p1_p4_mean.parquet",
        "resource": "resource_long.parquet",
    }
    found = {}
    for name, filename in required.items():
        candidates = list(EXPORT_ROOT.rglob(filename))
        if not candidates:
            raise FileNotFoundError(f"Missing downloaded official export: {filename}")
        found[name] = pd.read_parquet(candidates[0])
    if len(found["metrics_long"]) != 204:
        raise ValueError("Official TEST export is incomplete; expected 204 window/pipeline/phase rows.")
    if len(found["sanity_long"]) != 204:
        raise ValueError("Official sanity export is incomplete; expected 204 window/pipeline/phase rows.")
    if len(found["test"]) != 51 or len(found["sanity"]) != 51 or len(found["resource"]) != 51:
        raise ValueError("Official export is incomplete; expected 51 P1--P4 summaries and 51 resource rows.")
    return found["metrics_long"], found["test"], found["sanity_long"], found["sanity"], found["resource"]


def main() -> None:
    scores, model_done, sanity_done = completed_scores()
    metrics_test, test_summary, sanity_test, sanity_summary, resource = load_official_export()
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(1.7)
    sec.bottom_margin = Cm(1.7)
    sec.left_margin = Cm(1.7)
    sec.right_margin = Cm(1.7)
    style = doc.styles["Normal"]
    style.font.name = "Aptos"
    style.font.size = Pt(10.5)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("BÁO CÁO TÓM TẮT THỰC NGHIỆM CQ")
    run.bold = True
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(31, 78, 120)
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subrun = subtitle.add_run("RNN · seed 42 · release V2.2 · cập nhật 02/10/2026")
    subrun.italic = True
    subrun.font.size = Pt(10.5)

    doc.add_paragraph(
        "Phạm vi: vòng sàng lọc đầu tiên cho CQ, một shared RNN checkpoint trên P1–P4, "
        "GPU NVIDIA L4 và AMP bfloat16. Mỗi window được train độc lập; checkpoint được chọn "
        "bằng trung bình Validation Macro-F1 của P1–P4."
    )

    add_heading(doc, "1. Giao thức và trạng thái thực thi")
    add_table(doc, ["Hạng mục", "Quy ước khóa"], [
        ["Split / phase", "v2_2 / wide_prefix_v2_2"],
        ["Input channels", "X, M_missing, M_available, delta_t, phase_id, observed_length"],
        ["Checkpoint selection", "Mean Validation Macro-F1 (P1–P4); hòa thì chọn cross-entropy thấp hơn"],
        ["Test protocol", "TEST chỉ inference P1–P4; không refit/retrain sau validation"],
        ["Model / precision", "RNN · L4 · bf16 AMP; logits/loss float32"],
        ["Seed", "42 (screening seed; chưa phải ước lượng bất định cuối cùng)"],
    ])

    completed = sum(model_done.get((p, w), False) and sanity_done.get((p, w), False)
                    for p in PIPELINES for w in WINDOWS)
    add_table(doc, ["Pipeline", "Cách xử lý", "W1", "W2", "W3"], [
        [p, PIPELINE_NAMES[p], *[status(model_done.get((p, w), False), sanity_done.get((p, w), False)) for w in WINDOWS]]
        for p in PIPELINES
    ])
    doc.add_paragraph(
        f"Tại thời điểm tạo báo cáo: {completed}/51 cell đã hoàn tất cả model và sanity. "
        "Các cell chưa hoàn tất không được dùng để xếp hạng."
    )

    add_heading(doc, "2. Metric sàng lọc chính: Validation Macro-F1")
    doc.add_paragraph(
        "Bảng dưới là Macro-F1 trung bình P1–P4 tại checkpoint tốt nhất. Đây là metric validation "
        "để sàng lọc pipeline, không phải kết quả TEST cuối cùng. W1–V0 hoàn tất trước khi bổ sung epoch telemetry, "
        "do đó score validation không có trong log cục bộ dù artefact TEST và sanity đã được ghi."
    )
    score_rows = []
    for p in PIPELINES:
        row = [p, PIPELINE_NAMES[p]]
        for w in WINDOWS:
            is_complete = model_done.get((p, w), False) and sanity_done.get((p, w), False)
            row.append(score_text(scores.get((p, w))) if is_complete else "Pending")
        observed = [scores.get((p, w)) for w in WINDOWS if scores.get((p, w)) is not None and scores.get((p, w)) == scores.get((p, w))]
        row.append(f"{sum(observed) / len(observed):.4f}" if observed else "—")
        score_rows.append(row)
    add_table(doc, ["Pipeline", "Cách xử lý", "W1", "W2", "W3", "TB logged"], score_rows)

    originals = ("V1", "V5", "V9", "V13")
    means = {}
    for p in originals:
        values = [scores.get((p, w)) for w in WINDOWS]
        values = [v for v in values if v is not None and v == v]
        means[p] = sum(values) / len(values)
    best_original = max(means, key=means.get)
    doc.add_paragraph(
        f"Trong bốn imputer-only có log đầy đủ, {best_original} ({PIPELINE_NAMES[best_original]}) "
        f"có trung bình validation Macro-F1 cao nhất ({means[best_original]:.4f}). "
        "Đây mới là kết luận sàng lọc một seed; không dùng để tuyên bố thắng cuối cùng."
    )

    add_heading(doc, "3. Các độ đo chính được lưu cho kết quả TEST")
    add_table(doc, ["Nhóm", "Độ đo chính", "Vai trò"], [
        ["Discrimination", "Macro-F1, balanced accuracy, MCC", "So sánh hiệu quả giữa lớp mất cân bằng"],
        ["Probability", "PR-AUC macro, ROC-AUC macro OVR, NLL, Brier, ECE", "Đánh giá ranking và calibration"],
        ["Theo lớp", "Precision, recall, F1, support; confusion matrix", "Kiểm tra lớp thiểu số"],
        ["Sanity", "s_nan, s_maj_jsd, s_ent, s_drift, s_eff, s_leak, S_san_plus", "QA prediction, missingness và leakage"],
        ["Efficiency", "run time, CPU/GPU allocation, peak RAM/GPU memory", "So sánh chi phí thực thi"],
    ])
    doc.add_paragraph(
        "Bảng sau dùng kết quả TEST chính thức, trung bình bốn prefix P1–P4 rồi trung bình ba window. "
        "Mỗi pipeline có cùng 12 test evaluation cells; đây là kết quả một seed, không phải khoảng tin cậy đa seed."
    )
    test_fields = ["f1_macro", "balanced_accuracy", "mcc", "pr_auc_macro", "roc_auc_macro_ovr", "top_label_ece_15"]
    overall_test = test_summary.groupby("pipeline_id", as_index=False)[test_fields].mean().sort_values("f1_macro", ascending=False)
    add_table(doc, ["Rank", "Pipeline", "Macro-F1", "Bal. acc.", "MCC", "PR-AUC", "ROC-AUC", "ECE↓"], [
        [str(index), row.pipeline_id, *(f"{getattr(row, field):.4f}" for field in test_fields)]
        for index, row in enumerate(overall_test.itertuples(index=False), start=1)
    ])
    winners = test_summary.loc[test_summary.groupby("window_id")["f1_macro"].idxmax()].sort_values("window_id")
    add_table(doc, ["Window", "Top Macro-F1 pipeline", "Macro-F1", "Bal. acc.", "PR-AUC", "MCC"], [
        [row.window_id, row.pipeline_id, f"{row.f1_macro:.4f}", f"{row.balanced_accuracy:.4f}",
         f"{row.pr_auc_macro:.4f}", f"{row.mcc:.4f}"]
        for row in winners.itertuples(index=False)
    ])
    test_winner = overall_test.iloc[0]
    doc.add_paragraph(
        f"Theo TEST Macro-F1 trung bình, {test_winner.pipeline_id} ({PIPELINE_NAMES[test_winner.pipeline_id]}) "
        f"đứng đầu ({test_winner.f1_macro:.4f}). Điều này khác ranking validation, nên shortlist cuối cùng phải dựa "
        "trên validation để tránh test-selection bias; TEST ở đây dùng để báo cáo sau khi grid đã khóa."
    )

    add_heading(doc, "3.1. TEST theo từng window × prefix (toàn bộ grid)")
    doc.add_paragraph(
        "Không gộp TEST giữa các window khi đánh giá từng cell. Phụ lục dưới đây ghi riêng 204 cell "
        "(17 pipeline × W1–W3 × P1–P4) từ immutable L2 facts; các chỉ số là Macro-F1, balanced accuracy, MCC, "
        "PR-AUC macro, ROC-AUC macro, NLL và ECE."
    )
    exact_fields = ("f1_macro", "balanced_accuracy", "mcc", "pr_auc_macro", "roc_auc_macro_ovr", "multiclass_nll", "top_label_ece_15")
    for phase in ("P1", "P2", "P3", "P4"):
        add_heading(doc, f"TEST {phase}: W1, W2 và W3", level=2)
        phase_rows = metrics_test.loc[metrics_test.phase_id.eq(phase)].copy()
        phase_rows["_pipeline_num"] = phase_rows.pipeline_id.str[1:].astype(int)
        phase_rows = phase_rows.sort_values(["window_id", "_pipeline_num"])
        add_table(doc, ["Window", "Pipeline", "Macro-F1", "Bal. acc.", "MCC", "PR-AUC", "ROC-AUC", "NLL↓", "ECE↓"], [
            [row.window_id, row.pipeline_id, *(f"{getattr(row, field):.4f}" for field in exact_fields)]
            for row in phase_rows.itertuples(index=False)
        ])

    add_heading(doc, "3.2. Chi tiết bắt buộc: V0 tại W1")
    doc.add_paragraph(
        "V0 là baseline zero-fill kèm masks. Bảng này giữ tách từng prefix TEST của W1, bao gồm số mẫu, "
        "accuracy, các chỉ số mất cân bằng và chỉ số xác suất; không dùng trung bình P1–P4 thay thế."
    )
    v0_w1 = metrics_test.loc[(metrics_test.pipeline_id == "V0") & (metrics_test.window_id == "W1")].copy()
    v0_w1["_phase_num"] = v0_w1.phase_id.str[1:].astype(int)
    v0_w1 = v0_w1.sort_values("_phase_num")
    add_table(doc, ["Prefix", "N test", "Accuracy", "Macro-F1", "Bal. acc.", "MCC", "PR-AUC", "ROC-AUC", "NLL↓", "Brier↓", "ECE↓"], [
        [row.phase_id, f"{int(row.n_rows):,}", f"{row.accuracy:.4f}", f"{row.f1_macro:.4f}",
         f"{row.balanced_accuracy:.4f}", f"{row.mcc:.4f}", f"{row.pr_auc_macro:.4f}",
         f"{row.roc_auc_macro_ovr:.4f}", f"{row.multiclass_nll:.4f}", f"{row.multiclass_brier:.4f}",
         f"{row.top_label_ece_15:.4f}"]
        for row in v0_w1.itertuples(index=False)
    ])

    add_heading(doc, "3.3. AccTEMPO-M3 theo từng window × prefix")
    doc.add_paragraph(
        "AccTEMPO-M3 được lưu tách riêng cho cùng 204 TEST cell, không suy ra từ bảng Macro-F1. "
        "Phiên bản công thức: acctempo_m3_v1_jsd_base2_six_components. Bảng ghi AccTEMPO-M3 cùng S_perf, "
        "S_san+ v2 và S_cal để diễn giải cấu phần; s_leak là probe cấp pipeline, fit trên TRAIN và score TEST."
    )
    sanity_fields_exact = ("acctempo_m3", "s_perf", "s_san_plus_v2", "s_cal", "s_leak")
    for phase in ("P1", "P2", "P3", "P4"):
        add_heading(doc, f"AccTEMPO-M3 TEST {phase}: W1, W2 và W3", level=2)
        phase_rows = sanity_test.loc[sanity_test.phase_id.eq(phase)].copy()
        phase_rows["_pipeline_num"] = phase_rows.pipeline_id.str[1:].astype(int)
        phase_rows = phase_rows.sort_values(["window_id", "_pipeline_num"])
        add_table(doc, ["Window", "Pipeline", "AccTEMPO-M3", "S_perf", "S_san+ v2", "S_cal", "s_leak"], [
            [row.window_id, row.pipeline_id, *(f"{getattr(row, field):.4f}" for field in sanity_fields_exact)]
            for row in phase_rows.itertuples(index=False)
        ])

    add_heading(doc, "4. Sanity, leakage diagnostic và hiệu năng thực thi")
    sanity_fields = ["s_san_plus", "s_san_plus_v2", "s_leak", "acctempo_m3"]
    sanity_overall = sanity_summary.groupby("pipeline_id", as_index=False)[sanity_fields].mean().sort_values("acctempo_m3", ascending=False)
    add_table(doc, ["Pipeline", "S_san+", "S_san+ v2", "s_leak", "AccTEMPO_M3"], [
        [row.pipeline_id, *(f"{getattr(row, field):.4f}" for field in sanity_fields)]
        for row in sanity_overall.itertuples(index=False)
    ])
    resource_rows = []
    for pipeline, frame in resource.groupby("pipeline_id"):
        resource_rows.append([
            pipeline,
            f"{frame['time_run_total_s'].mean() / 60:.1f}",
            f"{frame['time_run_total_s'].max() / 60:.1f}",
            f"{frame['peak_gpu_memory_mb'].max():.1f}",
            "not recorded in historical run",
        ])
    add_table(doc, ["Pipeline", "Mean run min", "Max run min", "Peak GPU MiB", "Peak RAM"],
              sorted(resource_rows, key=lambda row: int(row[0][1:])))
    doc.add_paragraph(
        "GPU peak trên facts hiện có là PyTorch allocated memory, không phải tổng GPU reservation. Peak host RAM chưa được "
        "ghi cho grid seed 42; telemetry peak RSS đã được bổ sung cho run mới và sẽ dùng để hạ CPU/RAM request an toàn."
    )

    add_heading(doc, "5. Diễn giải và bước kế tiếp")
    for text in (
        "W2 có Macro-F1 validation thấp hơn đáng kể so với W1/W3 ở hầu hết pipeline; cần đọc TEST P1–P4 theo window, không kết luận bằng accuracy đơn lẻ.",
        "Không nhân toàn bộ 17 pipeline sang ba seed và bốn kiến trúc. Sau khi đủ grid seed 42, shortlist tối đa 3–4 pipeline bằng validation; chỉ shortlist mới chạy seed 43/44 và kiến trúc khác.",
        "s_leak là QA cấp pipeline: fit TRAIN masks/labels và score VALIDATION/TEST. Nó không phụ thuộc RNN/LSTM/GRU/BiLSTM; dùng một fact chuẩn cho mỗi training recipe thay vì nhân theo kiến trúc.",
    ):
        doc.add_paragraph(text, style="List Bullet")

    add_heading(doc, "6. Cấu trúc lưu trữ hiện hành (CQ V2.2)")
    doc.add_paragraph(
        "Mọi đường dẫn định danh đầy đủ theo task, feature regime, window, pipeline, model, seed, run_id và attempt_id. "
        "Không dùng file local hay ‘latest’ không có manifest làm nguồn kết quả chính thức."
    )
    tree = [
        "tempo-data-v1/",
        "├── input/CQ_v2_2/",
        "│   ├── release_manifest.json",
        "│   ├── phase_views_v2_2/                 # TRAIN + VALIDATION, P1–P4",
        "│   └── test_prefix_views_v2_2/P1..P4/     # TEST prefixes bất biến",
        "└── meta_release=imputation-v1/",
        "    ├── L0_registry/                       # input/schema/code/environment manifests",
        "    ├── L1_runs/",
        "    │   └── task=CQ/feature_regime=CQ_RAW_EARLY/window_id=W*/",
        "    │       └── pipeline_id=V0..V16/model_name=RNN/seed=42/",
        "    │           └── run_id=*/attempt_id=*/",
        "    │               ├── run_manifest.json · checkpoint · feature layout",
        "    │               └── predictions/{VALIDATION,TEST}/phase_id=P1..P4/",
        "    ├── L2_facts/",
        "    │   ├── metrics_overall/ · calibration/ · confusion_matrix/",
        "    │   ├── sanity_components/ · resource_usage/ · checkpoint_selection/",
        "    │   └── report_exports/task=CQ/report_id=RNN_seed42_v2_2/",
        "    └── L3_meta/                           # chưa materialize; chỉ tạo sau paired seed grid",
    ]
    for line in tree:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(line)
        run.font.name = "Consolas"
        run.font.size = Pt(8.5)

    doc.add_paragraph()
    footer = doc.add_paragraph(f"Nguồn tự động: logs/model_grid · tạo ngày {date.today().isoformat()} · phạm vi CQ RNN seed 42.")
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in footer.runs:
        run.italic = True
        run.font.size = Pt(8.5)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
