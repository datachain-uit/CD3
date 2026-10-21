"""Append the immutable 36-cell S2 sampling-plan summary to CQ V2."""
from pathlib import Path

import pandas as pd
from docx import Document
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "CQ" / "docs" / "REPORT_CQ_V2.2_CLEAN_GRAIN_RNN_SEED42_V2_2026-10-07.docx"
PLAN = ROOT / "_tmp_cq_rnn_r2_facts" / "augmentation_sampling_plan_long.parquet"
MARKER = "9.1 S2 sampling-plan coverage"


def _set(cell, value, bold=False):
    cell.text = str(value)
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(9)
            run.bold = bold


def main():
    plan = pd.read_parquet(PLAN)
    # Early S2 manifests legitimately predate explicit method metadata for
    # CDSMOTE/SASMOTE. Pipeline IDs are one-to-one with the locked methods.
    pipeline_method = {
        **{pipeline: "CDSMOTE" for pipeline in ("V2", "V6", "V10", "V14")},
        **{pipeline: "SASMOTE" for pipeline in ("V3", "V7", "V11", "V15")},
        **{pipeline: "RADIUS_SMOTE" for pipeline in ("V4", "V8", "V12", "V16")},
    }
    plan["method"] = plan["pipeline_id"].map(pipeline_method).fillna(plan["method"])
    if len(plan) != 36 or set(plan["method"]) != {"CDSMOTE", "SASMOTE", "RADIUS_SMOTE"}:
        raise RuntimeError("Expected 36 seed-42 S2 plans across three augmentation methods")
    summary = (plan.groupby(["method", "window_id"], as_index=False)
               .agg(pipeline_count=("pipeline_id", "nunique"),
                    train_rows_real=("rows_original", "first"),
                    train_rows_synthetic=("rows_synthetic", "first"),
                    train_rows_balanced=("rows_balanced", "first"))
               .sort_values(["method", "window_id"]))
    doc = Document(REPORT)
    if any(p.text == MARKER for p in doc.paragraphs):
        raise RuntimeError("sampling-plan summary already appended")
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(MARKER)
    run.bold = True
    run.font.size = Pt(12)
    doc.add_paragraph(
        "The S2 ledger contains 36 immutable seed-42 plans: four parent imputers × three windows × "
        "three methods. All plans use the registered IR10_K10 target policy; validation and test remain untouched."
    )
    table = doc.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    headers = ("Method", "Window", "Pipelines", "Real TRAIN", "Synthetic", "Balanced TRAIN")
    for cell, header in zip(table.rows[0].cells, headers):
        _set(cell, header, True)
    for row in summary.itertuples(index=False):
        cells = table.add_row().cells
        values = (row.method, row.window_id, row.pipeline_count, f"{row.train_rows_real:,}",
                  f"{row.train_rows_synthetic:,}", f"{row.train_rows_balanced:,}")
        for cell, value in zip(cells, values):
            _set(cell, value)
    doc.save(REPORT)
    print(REPORT)


if __name__ == "__main__":
    main()
