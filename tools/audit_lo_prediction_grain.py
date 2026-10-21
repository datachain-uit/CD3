"""Full prediction-file scan for null/duplicate hash and invalid active strict flag."""
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

base = Path('LO/resuilt/vastai_f2_batch2048_seed42_20261013')
output = Path('LO/resuilt/lo_prediction_grain_20261019')
rows = []
for family in ('rnn', 'lstm', 'gru', 'bilstm'):
    for window in ('W1', 'W2', 'W3'):
        for pipeline in (f'V{i}' for i in range(17)):
            root = base / f'{family}_seed42' / 'LO' / window / pipeline / family.upper() / 'seed=42' / 'predictions'
            for split in ('validation', 'test'):
                for phase in ('P1', 'P2', 'P3', 'P4'):
                    path = root / f'{split}_{phase}.parquet'
                    try:
                        frame = pq.read_table(path, columns=['enrollment_id_hash', f'temporal_strict_{phase}']).to_pandas()
                        hashes = frame['enrollment_id_hash']
                        flags = pd.to_numeric(frame[f'temporal_strict_{phase}'], errors='coerce')
                        rows.append({'family': family.upper(), 'window': window, 'pipeline': pipeline, 'split': split,
                                     'phase': phase, 'rows': len(frame), 'null_id': int(hashes.isna().sum()),
                                     'duplicate_rows': int(hashes.duplicated(keep=False).sum()),
                                     'null_or_invalid_flag': int((flags.isna() | ~flags.isin([0, 1])).sum()), 'error': ''})
                    except Exception as exc:
                        rows.append({'family': family.upper(), 'window': window, 'pipeline': pipeline, 'split': split,
                                     'phase': phase, 'error': f'{type(exc).__name__}: {exc}'})
            if len(rows) % 136 == 0:
                print(f'scanned={len(rows)}/1632', flush=True)
output.mkdir(parents=True, exist_ok=True)
result = pd.DataFrame(rows)
result.to_csv(output / 'file_audit.csv', index=False)
print('files=', len(result), 'errors=', int(result.error.ne('').sum()),
      'duplicate_files=', int(result.duplicate_rows.fillna(0).gt(0).sum()),
      'null_id_files=', int(result.null_id.fillna(0).gt(0).sum()),
      'invalid_flag_files=', int(result.null_or_invalid_flag.fillna(0).gt(0).sum()))
