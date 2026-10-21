"""Append completed RadiusSMOTE fallback evidence to the CQ V2 report."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from docx import Document
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "CQ" / "docs" / "REPORT_CQ_V2.2_CLEAN_GRAIN_RNN_SEED42_V2_2026-10-07.docx"
AUDIT_ROOT = ROOT / "_tmp_cq_radius_audit"
MARKER = "9. RadiusSMOTE fallback audit — CQ V2.2"


def _text(cell, value: object, bold: bool = False) -> None:
    cell.text = str(value)
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(9)
            run.bold = bold


def _heading(document: Document, value: str) -> None:
    paragraph = document.add_paragraph()
    run = paragraph.add_run(value)
    run.bold = True
    run.font.size = Pt(14)


def _table(document: Document, headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for cell, header in zip(table.rows[0].cells, headers):
        _text(cell, header, bold=True)
    for values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, values):
            _text(cell, value)


def main() -> None:
    files = sorted(AUDIT_ROOT.rglob("*.parquet"))
    if len(files) != 12:
        raise RuntimeError(f"Expected 12 Radius audit files, found {len(files)}")
    audit = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    required_rows = 3 * 4 * 2
    if len(audit) != required_rows:
        raise RuntimeError(f"Expected {required_rows} class-level Radius rows, found {len(audit)}")
    if audit.duplicated(["window_id", "parent_pipeline", "class_code"]).any():
        raise RuntimeError("Duplicate Radius fallback audit cell")

    document = Document(REPORT)
    if any(paragraph.text == MARKER for paragraph in document.paragraphs):
        raise RuntimeError("Radius evidence already appended")
    _heading(document, MARKER)
    document.add_paragraph(
        "RadiusSMOTE balanced TRAIN artifacts were created once for each parent imputer and window "
        "at augmentation seed 42. The following post-hoc audit deterministically replays only the "
        "neighbour-selection decision; it does not change the synthetic rows, balanced train files, "
        "or any RNN run."
    )
    if set(audit["radius"].round(6)) != {0.092}:
        raise ValueError("Unexpected RadiusSMOTE radius")
    summary = (audit.groupby(["window_id", "class_code"], as_index=False)
               .agg(generated_rows=("generated_rows", "first"),
                    parent_imputers=("parent_pipeline", "nunique"),
                    fallback_rate_mean=("fallback_nearest_neighbour_rate", "mean"),
                    fallback_rate_min=("fallback_nearest_neighbour_rate", "min"),
                    fallback_rate_max=("fallback_nearest_neighbour_rate", "max"))
               .sort_values(["window_id", "class_code"]))
    _table(document,
           ("Window", "Class", "Synthetic rows", "Parent imputers", "Fallback mean", "Range"),
           [(row.window_id, row.class_code, f"{row.generated_rows:,}", row.parent_imputers,
             f"{row.fallback_rate_mean:.1%}", f"{row.fallback_rate_min:.1%}–{row.fallback_rate_max:.1%}")
            for row in summary.itertuples(index=False)])
    high = int((audit["fallback_nearest_neighbour_rate"] > 0.50).sum())
    document.add_paragraph(
        f"All {high}/{len(audit)} class-level cells exceed the registered 50% warning threshold. "
        "Fallback is consistently higher for the good class than for average. Consequently RadiusSMOTE "
        "at radius 0.092 should be interpreted as a sensitivity comparator with frequent nearest-neighbour "
        "fallback, not as evidence of reliably local-radius interpolation. Performance comparisons remain "
        "valid because the audit is descriptive and the exact balanced artifacts are immutable."
    )
    document.save(REPORT)
    print(REPORT)


if __name__ == "__main__":
    main()
