#!/usr/bin/env python3
"""Export the registered QA23 linkage table for reviewed CQ behavioural bases.

The QA23 audit is intentionally feature-level: a reviewed prefix-observed
behavioural variable can correlate with the final CQ label without being a
post-label proxy.  This utility makes that decision auditable by extracting
the Spearman/NMI evidence for the eight reviewed bases at each P1--P4 prefix.
It neither changes the dictionary nor reclassifies any feature.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REVIEWED_BASES = (
    "problem_count", "exercise_count", "problem_context_count", "score_sum",
    "correct_problem_count", "attempts_sum", "problem_catalog_coverage",
    "problem_score_catalog_coverage",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows: list[pd.DataFrame] = []
    for phase in ("P1", "P2", "P3", "P4"):
        frame = pd.read_parquet(args.qa_root / f"phase_id={phase}" / "label_proxy_audit")
        expected = {f"{base}_{prefix}" for base in REVIEWED_BASES for prefix in ("P1", "P2", "P3", "P4")}
        selected = frame[frame["column_name"].isin(expected)].copy()
        selected["base"] = selected["column_name"].str.rsplit("_P", n=1).str[0]
        # At phase Pk only the observed P1..Pk prefix variables are admissible.
        selected["column_phase"] = selected["column_name"].str.extract(r"_(P[1-4])$")[0]
        selected = selected[selected["column_phase"] <= phase]
        rows.append(selected)

    out = pd.concat(rows, ignore_index=True)
    required = {"n_obs", "spearman_rho", "nmi", "needs_review", "proxy_review_note", "is_label_proxy"}
    missing = required.difference(out.columns)
    if missing:
        raise ValueError(f"QA23 source missing {sorted(missing)}")
    # These eight bases intentionally remain ``needs_review=True``: that is
    # the audit marker which led to their explicit behavioural review.  They
    # are admissible only when the recorded resolution says so; an automatic
    # correlation flag alone must not silently become a label-derived flag.
    approved_note = "reviewed_prefix_observed_behaviour__not_label_derived"
    if out["is_label_proxy"].astype(bool).any() or not out["proxy_review_note"].eq(approved_note).all():
        raise RuntimeError("Reviewed behavioural linkage table lacks the registered non-label-derived resolution")
    out["review_status"] = "APPROVED_PREFIX_OBSERVED_BEHAVIOUR"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out = out.sort_values(["phase_id", "base", "column_phase"]).reset_index(drop=True)
    out.to_csv(args.out, index=False)
    out.to_parquet(args.out.with_suffix(".parquet"), index=False)
    print(f"wrote {len(out)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
