"""V2.3 materializer runner with an explicit immutable release label."""
from __future__ import annotations

import os
import runpy
from pathlib import Path

os.environ["VIEW_RELEASE"] = "v2_3"
runpy.run_path(str(Path(__file__).with_name("materialize_label_stratified_views_v2_2.py")), run_name="__main__")
