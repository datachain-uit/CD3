#!/usr/bin/env python3
"""Export existing seed-42 audit facts and verify temporal-slice confusion matrices.

This checks aggregate facts, not prediction-level uniqueness or missing flags.
It does not train or alter any source artifact.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_window_phase_tables import export

KEYS = ["task", "seed", "model_name", "window_id", "pipeline_id", "eval_split", "phase_id"]
METRICS = ["acctempo_m3", "macro_f1", "balanced_acc", "s_perf", "s_san_plus", "s_ent",
           "c0_recall", "c1_recall", "c2_recall", "c0_support", "c1_support", "c2_support"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["CQ", "LO"], required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    families = ("LSTM", "GRU", "BILSTM") if args.task == "CQ" else ("RNN", "LSTM", "GRU", "BILSTM")
    frames, slices, classes = [], [], []
    for family in families:
        root = args.audit_root / args.task / family / "seed=42"
        if args.task == "LO":
            root = root / "LO" / family / "seed=42"
        for name, dest in (("sanity_components", frames), ("evaluation_slices", slices), ("metrics_per_class", classes)):
            df = pd.read_parquet(root / (name + ".parquet"))
            if set(df.task) != {args.task} or set(df.seed) != {42} or set(df.model_name) != {family}:
                raise ValueError(f"Unexpected task, seed or family: {root / name}")
            dest.append(df)
    facts, slice_facts, class_facts = map(lambda x: pd.concat(x, ignore_index=True), (frames, slices, classes))
    if facts.duplicated(KEYS).any() or slice_facts.duplicated(KEYS + ["slice"]).any():
        raise ValueError("Duplicate fact keys")
    if len(facts) != len(families) * 408:
        raise ValueError(f"Unexpected number of sanity cells: {len(facts)}")
    audit = []
    for key, group in slice_facts.groupby(KEYS, dropna=False):
        rows = {r['slice']: r for _, r in group.iterrows()}
        if set(rows) != {'ALL', 'STRICT', 'OVERLAP'}:
            raise ValueError(f"Incomplete slices: {key}")
        matrices = {name: np.stack(row['confusion_matrix']).astype(np.int64) for name, row in rows.items()}
        equal = np.array_equal(matrices['ALL'], matrices['STRICT'] + matrices['OVERLAP'])
        counts_equal = rows['ALL'].n_eval_samples == rows['STRICT'].n_eval_samples + rows['OVERLAP'].n_eval_samples
        audit.append(dict(zip(KEYS, key), partition_ok=bool(equal and counts_equal),
                          n_all=int(rows['ALL'].n_eval_samples), n_strict=int(rows['STRICT'].n_eval_samples),
                          n_overlap=int(rows['OVERLAP'].n_eval_samples),
                          strict_share=float(rows['STRICT'].n_eval_samples / rows['ALL'].n_eval_samples)))
    checks = pd.DataFrame(audit)
    if len(checks) != len(facts):
        raise ValueError("Slice facts do not cover sanity cells")
    all_slices = slice_facts[slice_facts['slice'] == 'ALL']
    compare = facts[KEYS + ['acctempo_m3', 'macro_f1', 'balanced_acc']].merge(
        all_slices[KEYS + ['acctempo_m3', 'macro_f1', 'balanced_acc']], on=KEYS,
        suffixes=('_sanity', '_slice'), validate='one_to_one')
    if len(compare) != len(facts):
        raise ValueError('ALL slices do not cover sanity cells')
    for metric in ('acctempo_m3', 'macro_f1', 'balanced_acc'):
        compare[metric + '_abs_diff'] = (compare[metric + '_sanity'] - compare[metric + '_slice']).abs()
    args.out.mkdir(parents=True, exist_ok=True)
    export(facts, args.out / "tables", METRICS)
    facts.to_parquet(args.out / "sanity_long.parquet", index=False)
    class_facts.to_parquet(args.out / "per_class_long.parquet", index=False)
    checks.to_csv(args.out / "slice_partition_and_strict_share.csv", index=False)
    compare.to_csv(args.out / 'all_slice_vs_sanity.csv', index=False)
    class_facts[(class_facts.window_id == 'W1')].to_csv(args.out / "w1_per_class_by_phase.csv", index=False)
    summary = {"task": args.task, "seed": 42, "families": list(families), "sanity_cells": len(facts),
               "partition_cells": len(checks), "partition_violations": int((~checks.partition_ok).sum()),
               "all_slice_max_abs_diff": {m: float(compare[m + '_abs_diff'].max()) for m in ('acctempo_m3', 'macro_f1', 'balanced_acc')},
               "limitation": "Aggregate confusion-matrix check only; cannot prove prediction uniqueness or valid raw flags."}
    (args.out / "review_receipt.json").write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
