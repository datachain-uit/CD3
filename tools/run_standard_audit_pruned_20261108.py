"""Run tools/vastai_audit_shared.py unchanged on an existing standard run tree, reading only the input columns it uses.

The audit loads whole TRAIN/evaluation parquet files (587 columns); only missing flags, availability masks and the label
are used, so reading just those keeps memory low.
Usage: --task CQ --data-root D --run-root R --audit-root A --model-name M [--allow-partial] [--bootstrap-repetitions N]
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
_original = pd.read_parquet
LABELS = ('CQ_label_final', 'LO_performance_label_3')
BACKSLASH = chr(92)


def _pruned(path, *a, **k):
    p = str(path).replace(BACKSLASH, '/')
    if k.get('columns') is None and not a and p.endswith('.parquet') and ('/train/' in p or '/evaluation/' in p):
        names = pq.ParquetFile(path).schema_arrow.names
        keep = [n for n in names if n in LABELS or n.startswith('missing__') or n.startswith('phase_available_')
                or n.endswith(tuple(f'_observed_mask_P{i}' for i in range(1, 5)))]
        return _original(path, columns=keep, **k)
    return _original(path, *a, **k)


pd.read_parquet = _pruned
import vastai_audit_shared
sys.argv = ['vastai_audit_shared'] + sys.argv[1:]
vastai_audit_shared.main()
