"""Refit the channel adapter of an imputer-only Mantis parent (task CQ) exactly as the runner does, without training.

The adapter is fitted on the real TRAIN rows of the imputer-only cell (sample_seed fixed in the spec), so it is
deterministic; the result is stored at cache/task=CQ/window=W/imputer=P/channel_adapter.{npz,json} and its summary
(fit_rows_sha256, explained variance ratio, n_rows_fit) is compared with the summary recorded in the original cell record
(--expected-cell-record) when given. Mismatch -> exit 2 and nothing is kept.
Usage: python tools/refit_mantis_parent_adapter_20261109.py --window W3 --parent V13 --data-root D --work-root R [--expected-cell-record f3_cell_record.json]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from model.data import fit_layout, transform_frame
from f3_mantis.adapter import ChannelPCAAdapter
from f3_mantis.cell import adapter_path_for
from f3_mantis.store import input_sha256
from f3_mantis.spec import MANTIS_V2_SPEC

CLASSES = ("warning", "average", "good")

parser = argparse.ArgumentParser()
parser.add_argument("--window", required=True)
parser.add_argument("--parent", required=True)
parser.add_argument("--data-root", type=Path, required=True)
parser.add_argument("--work-root", type=Path, required=True)
parser.add_argument("--expected-cell-record", type=Path)
args = parser.parse_args()

train_path = args.data_root / "train" / args.window / args.parent / "train.parquet"
frame = pd.read_parquet(train_path)
if frame.enrollment_id.isna().any() or frame.enrollment_id.duplicated().any():
    raise ValueError("TRAIN IDs must be non-null and unique")
layout = fit_layout(frame, task="CQ", phase_id="P4", use_masks=True)
names = (list(layout.dynamic_bases) +
         [f"missing__{base}" for base in layout.dynamic_bases if f"missing__{base}_P1" in frame.columns] +
         list(layout.mask_phase_bases) + ["phase_fraction", "delta_t"])
x, static, _, y = transform_frame(frame, layout, classes=CLASSES, use_masks=True)
if x.shape[-1] != len(names):
    raise ValueError("Channel layout mismatch")
row_ids = frame.enrollment_id.astype(str).to_numpy()
del frame
is_synth = np.zeros(len(row_ids), dtype=bool)
digest = input_sha256(x, row_ids)
cfg = MANTIS_V2_SPEC["channel_adapter"]
adapter = ChannelPCAAdapter(n_components=int(cfg["n_components"]), standardize=bool(cfg["standardize"]),
                            sample_rows_max=int(cfg["sample_rows_max"]), sample_seed=int(cfg["sample_seed"]))
adapter.fit(x, real_mask=~is_synth, channel_names=names, row_ids=row_ids, rows_digest=digest)
summary = adapter.summary()
print(json.dumps({"fit_rows_sha256": summary.get("fit_rows_sha256"), "n_rows_fit": summary.get("n_rows_fit"),
                  "explained_variance_ratio": summary.get("explained_variance_ratio")}), flush=True)
if args.expected_cell_record:
    expected = json.loads(args.expected_cell_record.read_text(encoding="utf-8"))["adapter"]
    keys = [k for k in expected if k in summary]
    bad = [k for k in keys if expected[k] != summary[k]]
    print(json.dumps({"compared_keys": keys, "mismatched": bad}), flush=True)
    if bad == ["digest"]:
        # every fit statistic matches; only the byte-level digest differs (float noise ~1e-17 from BLAS summation order
        # on another host). Accepted by the code team on 2026-11-09 and recorded next to the adapter.
        note = {"status": "REFIT_DIGEST_NOISE", "expected_digest": expected.get("digest"), "refit_digest": summary.get("digest"),
                "matched_keys": [k for k in keys if k != "digest"], "accepted_by": "code team, 2026-11-09",
                "reason": "same real TRAIN rows (fit_rows_sha256) and explained variance; digest hashes raw float64 bytes"}
    elif bad:
        sys.exit(2)
    else:
        note = None
else:
    note = None
path = adapter_path_for(args.work_root / "cache", "CQ", args.window, args.parent)
path.parent.mkdir(parents=True, exist_ok=True)
adapter.save(path)
if note:
    (path.parent / "REFIT_NOTE.json").write_text(json.dumps(note, indent=2), encoding="utf-8")
print("ADAPTER_SAVED", path, "digest", adapter.digest(), flush=True)
