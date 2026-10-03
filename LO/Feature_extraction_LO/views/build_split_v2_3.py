"""V2.3 runner: V2.2 chronology plus the explicit two-tier evaluation QA."""
from __future__ import annotations

import os
import runpy
from pathlib import Path

os.environ["SPLIT_V2_RELEASE"] = "v2_3"
os.environ["SPLIT_V2_QA_SIZE_POLICY"] = "two_tier"
# Never inherit V2.2's reference-QA values from a shared notebook session.
os.environ["SPLIT_V2_MIN_EVAL_ARM_SHARE"] = "0.025"
os.environ["SPLIT_V2_MIN_EVAL_ARM_ROWS"] = "50000"
os.environ["SPLIT_V2_MIN_EVAL_TOTAL_SHARE"] = "0.05"
configured_output = os.environ.get("SPLIT_V2_OUTPUT", "").rstrip("/")
if configured_output and not configured_output.endswith("split_registry_v2_3"):
    raise ValueError("V2.3 must write to a split_registry_v2_3 output; clear or update SPLIT_V2_OUTPUT.")
runpy.run_path(str(Path(__file__).with_name("build_split_v2_2.py")), run_name="__main__")
