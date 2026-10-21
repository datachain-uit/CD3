"""Read only audited layout columns and run a reproducible LO W1 static probe."""
import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.probe_static_only import run, summary_table
from tools.audit_static_columns import profile_column, registry_allowlist

base = ROOT / 'downloads/vastai/LO_V3_1_clean_grain_seed42'
layout = ROOT / 'LO/resuilt/vastai_f2_batch2048_seed42_20261013/rnn_seed42/LO/W1/V0/RNN/seed=42/feature_layout.json'
out = ROOT / 'LO/resuilt/static_probe_w1_v0_20261019'
out.mkdir(parents=True, exist_ok=True)
columns = json.loads(layout.read_text(encoding='utf-8'))['static_columns']
paths = {'TRAIN': base/'train/W1/V0/train.parquet', 'VALIDATION': base/'evaluation/W1/V0/validation.parquet', 'TEST': base/'evaluation/W1/V0/test_P1.parquet'}
frames = {}
for name, path in paths.items():
    schema = pq.read_schema(path).names
    wanted = list(dict.fromkeys(['LO_performance_label_3'] + columns + [c for c in ('offering_id','course_id','course_id_code') if c in schema]))
    absent = set(wanted) - set(schema)
    if absent:
        raise ValueError(f'{path}: missing {sorted(absent)}')
    frame = pd.read_parquet(path, columns=wanted)
    if name == 'TRAIN' and len(frame) > 400000:
        frame = frame.sample(n=400000, random_state=42)
    frames[name] = frame
    print(name, len(frame), flush=True)
report = run(frames['TRAIN'], {k: frames[k] for k in ('VALIDATION','TEST')}, 'LO', layout, 42)
report['inputs'] = {'paths': {k: str(v.relative_to(ROOT)) for k,v in paths.items()}, 'train_sampling': '400000 uniform rows, seed 42', 'evaluation_sampling': 'none', 'layout': str(layout.relative_to(ROOT))}
(out/'probe.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
(out/'probe_summary.md').write_text(summary_table(report)+'\n', encoding='utf-8')
allow = registry_allowlist('LO')
train = frames['TRAIN']
offering = next((c for c in ('offering_id','course_id','course_id_code') if c in train), None)
records = [profile_column(c, train, 'LO_performance_label_3', offering, {k:frames[k] for k in ('VALIDATION','TEST')}, set(allow['allowed']), set(allow['denied'])) for c in columns]
audit = {'scope': report['inputs'], 'offering_column_used': offering, 'allowlist': allow, 'columns': records}
(out/'static_audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
print('OUTPUT', out, flush=True)
