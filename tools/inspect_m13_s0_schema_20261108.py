from pathlib import Path
import json
import pandas as pd

root = Path('CQ/resuilt/s0_current_cq_20261108/L2_facts/task=CQ/window_id=W1/phase_id=P1')
for path in sorted(root.glob('*.parquet')):
    frame = pd.read_parquet(path)
    print('\n', path.name, 'rows', len(frame), 'columns', frame.columns.tolist())
    print(frame.head(2).to_json(orient='records', default_handler=str))
