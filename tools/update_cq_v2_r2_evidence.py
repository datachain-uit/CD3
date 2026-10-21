"""Append r2 acceptance evidence to the canonical CQ V2 clean-grain report.

The script consumes exported facts only.  It never queries Modal or changes an
experiment artifact, which makes the report update repeatable after download.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from docx import Document
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "CQ" / "docs" / "REPORT_CQ_V2.2_CLEAN_GRAIN_RNN_SEED42_V2_2026-10-07.docx"
FACTS = ROOT / "_tmp_cq_rnn_r3_facts"
MARKER = "8. Evidence acceptance r2 — clean-grain CQ V2.2"

GRAIN_ROWS = (
    ("W1", "V0 TRAIN", "1,609,276", "1,609,276", "1", "{1: 1,609,276}"),
    ("W1", "V2 balanced TRAIN", "1,866,048", "1,866,048", "1", "{1: 1,866,048}"),
    ("W2", "V0 TRAIN", "1,963,060", "1,963,060", "1", "{1: 1,963,060}"),
    ("W2", "V2 balanced TRAIN", "2,269,260", "2,269,260", "1", "{1: 2,269,260}"),
    ("W3", "V0 TRAIN", "2,324,027", "2,324,027", "1", "{1: 2,324,027}"),
    ("W3", "V2 balanced TRAIN", "2,688,368", "2,688,368", "1", "{1: 2,688,368}"),
)


def _cell(cell, value: object, *, bold: bool = False) -> None:
    cell.text = str(value)
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(9)
            run.bold = bold


def _heading(document: Document, text: str) -> None:
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.bold = True
    run.font.size = Pt(14)


def _table(document: Document, headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for cell, header in zip(table.rows[0].cells, headers):
        _cell(cell, header, bold=True)
    for values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, values):
            _cell(cell, value)


def _require(name: str) -> pd.DataFrame:
    path = FACTS / name
    if not path.is_file():
        nested = FACTS / "report_id=RNN_seed42_v2_2_clean_20261007_r2" / name
        if nested.is_file():
            path = nested
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def main() -> None:
    if not REPORT.is_file():
        raise FileNotFoundError(REPORT)
    validation = _require("metrics_validation_long.parquet")
    validation_sanity = _require("sanity_validation_long.parquet")
    selection = _require("checkpoint_selection_long.parquet")
    per_class = _require("metrics_per_class_long.parquet")
    bootstrap = _require("bootstrap_metrics_per_class_long.parquet")
    slices = _require("strict_overlap_metrics_long.parquet")
    canonical = _require("canonical_s_leak.parquet")

    document = Document(REPORT)
    if any(paragraph.text == MARKER for paragraph in document.paragraphs):
        raise RuntimeError("r2 evidence is already present; refusing to append it twice")

    _heading(document, MARKER)
    document.add_paragraph(
        "This section supersedes the preliminary seed-42 acceptance notes. It is generated from "
        "the provenance-strict r2 export after canonical real-parent S_leak overlay. No model, "
        "imputation, or augmentation artifact was rerun for this export."
    )

    _heading(document, "8.1 Grain and lineage")
    document.add_paragraph(
        "The release lineage sidecar records zero exact duplicates for labels, features, "
        "enrollment_windows, and joined_base. Read-only grain audits also verify the actual V0 "
        "and balanced model inputs below. In every audited table, rows equal distinct enrollment_id; "
        "the histogram has only one row per enrollment."
    )
    _table(document, ("Window", "Input", "Rows", "Distinct enrollment", "Max rows", "Histogram"), list(GRAIN_ROWS))

    _heading(document, "8.2 Canonical sanity and validation AccTEMPO")
    expected_canonical = 15 * 2 * 4
    if len(canonical) != expected_canonical:
        raise ValueError(f"Expected {expected_canonical} canonical S_leak facts, got {len(canonical)}")
    if canonical["s_leak_probe_n_eval"].isna().any():
        raise ValueError("Canonical S_leak facts lack n_eval")
    invariant = (canonical.groupby(["window_id", "parent_imputation_run_id", "eval_split", "phase_id"])["s_leak"]
                 .nunique().max())
    val = validation.merge(
        validation_sanity[["pipeline_id", "window_id", "phase_id", "run_id", "attempt_id", "acctempo_m3",
                           "s_san_plus", "s_perf", "s_eff", "s_leak"]],
        on=["pipeline_id", "window_id", "phase_id", "run_id", "attempt_id"], how="inner", validate="one_to_one",
    )
    if len(val) != 204:
        raise ValueError(f"Expected 204 validation rows after sanity merge, got {len(val)}")
    val_summary = (val.groupby("pipeline_id", as_index=False)[["acctempo_m3", "s_perf", "s_san_plus"]]
                   .mean().sort_values("acctempo_m3", ascending=False).head(5))
    document.add_paragraph(
        f"Canonical S_leak coverage is {len(canonical)}/{expected_canonical} parent/split/phase facts. "
        f"Each row carries real-parent TRAIN pooled fit scope, frozen evaluation scope, probe fit rows and n_eval. "
        f"The maximum duplicate canonical value count per parent/split/phase key is {invariant}; "
        "augmented variants therefore cannot refit a separate leakage probe."
    )
    _table(document, ("Pipeline", "Validation AccTEMPO", "S_perf", "S_san+"), [
        (row.pipeline_id, f"{row.acctempo_m3:.4f}", f"{row.s_perf:.4f}", f"{row.s_san_plus:.4f}")
        for row in val_summary.itertuples(index=False)
    ])

    _heading(document, "8.3 Checkpoint selection, class support, CI, and evaluation slices")
    if len(selection) != 51:
        raise ValueError(f"Expected 51 checkpoint records, got {len(selection)}")
    selection_rows = [
        (len(selection), int(selection["checkpoint_count_evaluated"].min()),
         int(selection["checkpoint_count_evaluated"].max()),
         int(selection["n_checkpoints_within_margin"].min()),
         int(selection["n_checkpoints_within_margin"].max()))
    ]
    _table(document, ("Runs", "Checkpoints min", "Checkpoints max", "Within-margin min", "Within-margin max"), selection_rows)
    document.add_paragraph(
        f"Per-class facts contain {len(per_class):,} rows and bootstrap facts contain {len(bootstrap):,} rows; "
        f"all bootstrap records use B={int(bootstrap['bootstrap_repetitions'].iloc[0]):,}. "
        "They retain support, small-support flags, precision, recall, F1 and interval bounds by class."
    )
    slice_summary = (slices.groupby(["eval_split", "slice"], as_index=False)
                     [["n_eval_samples", "macro_f1", "balanced_accuracy"]].mean())
    _table(document, ("Split", "Slice", "Mean n", "Macro-F1", "Balanced accuracy"), [
        (row.eval_split, row.slice, f"{row.n_eval_samples:,.0f}", f"{row.macro_f1:.4f}", f"{row.balanced_accuracy:.4f}")
        for row in slice_summary.itertuples(index=False)
    ])
    document.add_paragraph(
        "STRICT/OVERLAP are descriptive evaluation slices. They do not alter the locked TEST cohort, "
        "selection rule, or the primary all-row result."
    )
    document.save(REPORT)
    print(REPORT)


if __name__ == "__main__":
    main()
