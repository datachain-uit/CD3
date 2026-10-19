#!/usr/bin/env python3
"""Read-only audit of the static columns that ``model.data.fit_layout`` feeds to every model.

``fit_layout`` selects static features by exclusion: every numeric column of the TRAIN frame that is not an
identity, the label, a ``_P1..P4`` column or a ``missing__``/``phase_available_``/``context__`` column becomes a
static input.  Nothing in the pipeline attests that such a column is known at the P1 cutoff or that it does
not identify the offering.  This tool makes the selected set explicit and scores each column for

* constancy (``n_unique <= 1``: the column carries no information but still enters the tensor),
* offering-level constancy and intraclass correlation (an offering attribute lets the model learn
  offering identity, which transfers to seen offerings only),
* association with the label (normalised mutual information on quantile bins),
* distribution shift between TRAIN and each evaluation split (Jensen-Shannon divergence, base 2, on
  TRAIN quantile bins),
* membership in an explicit allowlist (``--allowlist``), so that an unlisted numeric column fails ``--strict``.

Usage::

    python tools/audit_static_columns.py --task LO --train model_inputs/W1/V0/train.parquet \
        --eval VALIDATION=model_inputs/W1/V0/validation.parquet --eval TEST=test_prefix_views/W1/P1.parquet \
        --allowlist static_allowlist_LO.json --out audit_static_columns_W1_V0.json [--strict]

The allowlist is a JSON file ``{"task": "LO", "allowed": [...], "denied": [...], "note": "..."}``.  Every
column is reported with its status ``ALLOWED`` / ``DENIED`` / ``UNLISTED``; without an allowlist every column
is ``UNLISTED``.  The tool never modifies inputs and never trains anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model.data import IDENTITY_OR_PROVENANCE, fit_layout, label_column  # noqa: E402

OFFERING_CANDIDATES = ("offering_id", "course_id", "course_id_code")
DEFAULT_BINS = 10
THRESHOLDS = {"offering_constant_share": 0.99, "nmi_label": 0.02, "jsd_shift": 0.10}


def _jsd_base2(p: np.ndarray, q: np.ndarray) -> float:
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    if p.sum() <= 0 or q.sum() <= 0:
        return float("nan")
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = a > 0
        return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def select_layout(train: pd.DataFrame, task: str) -> tuple[list[str], list[str], str]:
    """Return (static_columns, mask_static_columns, mode) exactly as the trainer would select them."""
    try:
        layout = fit_layout(train, task=task, phase_id="P4", use_masks=True)
        return list(layout.static_columns), list(layout.mask_static_columns), "use_masks=True (registered V0_mask input)"
    except ValueError as error:
        layout = fit_layout(train, task=task, phase_id="P4", use_masks=False)
        return list(layout.static_columns), [], f"use_masks=False fallback ({error})"


def find_offering_column(frame: pd.DataFrame) -> str | None:
    for name in OFFERING_CANDIDATES:
        if name in frame:
            return name
    return None


def quantile_edges(values: pd.Series, bins: int = DEFAULT_BINS) -> np.ndarray:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return np.array([])
    edges = np.unique(np.quantile(clean, np.linspace(0, 1, bins + 1)))
    return edges


def bin_counts(values: pd.Series, edges: np.ndarray) -> np.ndarray:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if edges.size < 2:
        return np.array([len(clean)], dtype=float)
    index = np.clip(np.searchsorted(edges, clean, side="right") - 1, 0, edges.size - 2)
    return np.bincount(index, minlength=edges.size - 1).astype(float)


def nmi_with_label(values: pd.Series, labels: pd.Series, edges: np.ndarray) -> float | None:
    try:
        from sklearn.metrics import normalized_mutual_info_score
    except ImportError:  # pragma: no cover - sklearn is a project dependency
        return None
    clean = pd.to_numeric(values, errors="coerce")
    mask = clean.notna().to_numpy()
    if mask.sum() < 2 or edges.size < 2:
        return 0.0
    binned = np.clip(np.searchsorted(edges, clean[mask].to_numpy(dtype=float), side="right") - 1, 0, edges.size - 2)
    return float(normalized_mutual_info_score(labels[mask].astype(str).to_numpy(), binned))


def offering_statistics(values: pd.Series, offering: pd.Series | None) -> dict[str, Any]:
    if offering is None:
        return {"offering_constant_share": None, "icc_offering": None, "n_offerings": None}
    clean = pd.to_numeric(values, errors="coerce")
    frame = pd.DataFrame({"v": clean, "o": offering.astype(str)}).dropna()
    if frame.empty:
        return {"offering_constant_share": None, "icc_offering": None, "n_offerings": 0}
    grouped = frame.groupby("o")["v"]
    sizes = grouped.size()
    multi = sizes[sizes >= 2].index
    nunique = grouped.nunique()
    constant_share = float((nunique.loc[multi] <= 1).mean()) if len(multi) else None
    total_var = float(frame["v"].var(ddof=0))
    if total_var <= 0:
        icc = None
    else:
        within = grouped.var(ddof=0).fillna(0.0)
        weighted_within = float((within * sizes).sum() / sizes.sum())
        icc = float(np.clip(1.0 - weighted_within / total_var, 0.0, 1.0))
    return {"offering_constant_share": constant_share, "icc_offering": icc, "n_offerings": int(len(sizes))}


def profile_column(name: str, train: pd.DataFrame, label: str, offering_column: str | None,
                   evals: dict[str, pd.DataFrame], allow: set[str], deny: set[str]) -> dict[str, Any]:
    values = train[name]
    numeric = pd.to_numeric(values, errors="coerce")
    edges = quantile_edges(numeric)
    record: dict[str, Any] = {
        "column": name,
        "dtype": str(values.dtype),
        "n_unique_train": int(numeric.nunique(dropna=True)),
        "null_share_train": float(numeric.isna().mean()),
        "constant": bool(numeric.nunique(dropna=True) <= 1),
        "nmi_label": nmi_with_label(numeric, train[label], edges),
        "class_means_train": {str(k): float(v) for k, v in numeric.groupby(train[label].astype(str)).mean().items()},
    }
    record.update(offering_statistics(numeric, train[offering_column] if offering_column else None))
    train_hist = bin_counts(numeric, edges)
    shifts: dict[str, Any] = {}
    for split_name, frame in evals.items():
        if name not in frame:
            shifts[split_name] = {"present": False}
            continue
        eval_numeric = pd.to_numeric(frame[name], errors="coerce")
        entry = {"present": True, "jsd_train_vs_eval": _jsd_base2(train_hist, bin_counts(eval_numeric, edges)),
                 "n_unique_eval": int(eval_numeric.nunique(dropna=True))}
        eval_offering = find_offering_column(frame)
        entry.update({f"eval_{k}": v for k, v in offering_statistics(eval_numeric, frame[eval_offering] if eval_offering else None).items()})
        shifts[split_name] = entry
    record["eval_splits"] = shifts
    record["allowlist_status"] = "DENIED" if name in deny else "ALLOWED" if name in allow else "UNLISTED"
    flags = []
    if record["constant"]:
        flags.append("CONSTANT")
    if record["offering_constant_share"] is not None and record["offering_constant_share"] >= THRESHOLDS["offering_constant_share"]:
        flags.append("OFFERING_ATTRIBUTE")
    if record["nmi_label"] is not None and record["nmi_label"] >= THRESHOLDS["nmi_label"]:
        flags.append("LABEL_ASSOCIATED")
    if any(isinstance(s, dict) and s.get("present") and (s.get("jsd_train_vs_eval") or 0) >= THRESHOLDS["jsd_shift"] for s in shifts.values()):
        flags.append("SHIFT_VS_TRAIN")
    if record["allowlist_status"] != "ALLOWED":
        flags.append(record["allowlist_status"])
    record["flags"] = flags
    return record


def audit(train: pd.DataFrame, task: str, evals: dict[str, pd.DataFrame], allowlist: dict[str, Any] | None,
          thresholds: dict[str, float] | None = None) -> dict[str, Any]:
    if thresholds:
        THRESHOLDS.update(thresholds)
    label = label_column(task)
    if label not in train:
        raise ValueError(f"TRAIN frame has no label column {label}")
    static_columns, mask_static_columns, mode = select_layout(train, task)
    offering_column = find_offering_column(train)
    allow = set((allowlist or {}).get("allowed", []))
    deny = set((allowlist or {}).get("denied", []))
    records = [profile_column(name, train, label, offering_column, evals, allow, deny) for name in static_columns]
    identity_present = sorted(c for c in train.columns if c in IDENTITY_OR_PROVENANCE)
    non_numeric_candidates = sorted(c for c in train.columns
                                    if c not in static_columns and c not in IDENTITY_OR_PROVENANCE and c != label
                                    and not c.startswith(("missing__", "phase_available_", "context__"))
                                    and not pd.api.types.is_numeric_dtype(train[c])
                                    and not any(c.endswith(f"_P{k}") for k in range(1, 5)))
    summary = {
        "task": task, "label_column": label, "layout_mode": mode, "n_rows_train": int(len(train)),
        "offering_column_used": offering_column,
        "n_static_columns": len(static_columns), "n_mask_static_columns": len(mask_static_columns),
        "static_columns": static_columns, "mask_static_columns": mask_static_columns,
        "identity_columns_present_in_frame": identity_present,
        "non_numeric_columns_outside_tensor": non_numeric_candidates,
        "thresholds": dict(THRESHOLDS),
        "flag_counts": {flag: sum(flag in r["flags"] for r in records)
                        for flag in ("CONSTANT", "OFFERING_ATTRIBUTE", "LABEL_ASSOCIATED", "SHIFT_VS_TRAIN", "UNLISTED", "DENIED")},
        "allowlist_note": (allowlist or {}).get("note"),
    }
    return {"summary": summary, "columns": records}


def registry_allowlist(task: str) -> dict[str, Any]:
    """Allowlist derived from the registry contract (LO today; CQ once its contract is written)."""
    if task != "LO":
        raise SystemExit("no STATIC_FEATURE_CONTRACT registered for CQ yet; pass --allowlist")
    from LO.registries import STATIC_FEATURE_CONTRACT
    fields = STATIC_FEATURE_CONTRACT["fields"]
    return {"task": task,
            "allowed": sorted(n for n, f in fields.items() if f["disposition"] == "IN_TENSOR"),
            "denied": sorted(n for n, f in fields.items() if f["disposition"] in {"EXCLUDE", "CONTEXT_ONLY"}),
            "note": STATIC_FEATURE_CONTRACT["contract_id"]}


def markdown_table(report: dict[str, Any]) -> str:
    lines = ["| column | n_unique | constant | offering_constant_share | icc_offering | nmi_label | status | flags |",
             "|---|---|---|---|---|---|---|---|"]
    for r in report["columns"]:
        def fmt(v: Any) -> str:
            return "—" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))
        lines.append(f"| {r['column']} | {r['n_unique_train']} | {r['constant']} | {fmt(r['offering_constant_share'])} | "
                     f"{fmt(r['icc_offering'])} | {fmt(r['nmi_label'])} | {r['allowlist_status']} | {', '.join(r['flags']) or '—'} |")
    return "\n".join(lines)


def _read(path: str, sample_rows: int | None, seed: int) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if sample_rows and len(frame) > sample_rows:
        frame = frame.sample(n=sample_rows, random_state=seed)
    return frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", required=True, choices=("CQ", "LO"))
    parser.add_argument("--train", required=True, help="TRAIN model-input parquet (the frame fit_layout sees)")
    parser.add_argument("--eval", action="append", default=[], metavar="NAME=PATH",
                        help="evaluation parquet(s), e.g. VALIDATION=... TEST_P1=...; repeatable")
    parser.add_argument("--allowlist", help="JSON allowlist {'task','allowed','denied','note'}")
    parser.add_argument("--allowlist-from-registry", action="store_true",
                        help="LO only: allowed = IN_TENSOR fields, denied = EXCLUDE/CONTEXT_ONLY fields of LO.registries.STATIC_FEATURE_CONTRACT")
    parser.add_argument("--sample-rows", type=int, default=None, help="random row sample per frame (default: all rows)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="audit_static_columns.json")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any selected column is UNLISTED or DENIED")
    args = parser.parse_args(argv)

    train = _read(args.train, args.sample_rows, args.seed)
    evals = {}
    for item in args.eval:
        name, _, path = item.partition("=")
        if not path:
            parser.error(f"--eval expects NAME=PATH, got {item!r}")
        evals[name] = _read(path, args.sample_rows, args.seed)
    allowlist = None
    if args.allowlist_from_registry:
        allowlist = registry_allowlist(args.task)
    if args.allowlist:
        allowlist = json.loads(Path(args.allowlist).read_text(encoding="utf-8"))
        if allowlist.get("task") not in (None, args.task):
            parser.error(f"allowlist task {allowlist.get('task')!r} does not match --task {args.task}")
    report = audit(train, args.task, evals, allowlist)
    report["inputs"] = {"train": args.train, "eval": dict(item.partition("=")[::2] for item in args.eval),
                        "allowlist": args.allowlist, "sample_rows": args.sample_rows}
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(markdown_table(report))
    print(json.dumps(report["summary"]["flag_counts"]))
    if args.strict and (report["summary"]["flag_counts"]["UNLISTED"] or report["summary"]["flag_counts"]["DENIED"]):
        print("STRICT: unlisted or denied static columns are selected by fit_layout", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
