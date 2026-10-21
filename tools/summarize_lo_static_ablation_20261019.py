"""Compare LO W1 static ablations to their same-pipeline historical LSTM baselines."""
import json
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parents[1]
abl = root / 'LO/resuilt/lo_static_ablation_20261019'
base = root / 'LO/resuilt/vastai_f2_batch2048_seed42_20261013/lstm_seed42/LO/W1'
records = []
for pipeline in ('V0', 'V8'):
    for variant in ('baseline_historical', 'no_static', 'gender_duration'):
        path = (base / pipeline if variant == 'baseline_historical' else abl / variant / 'LO/W1' / pipeline) / 'LSTM/seed=42'
        manifest = json.loads((path / 'run_manifest.json').read_text(encoding='utf-8'))
        layout = json.loads((path / 'feature_layout.json').read_text(encoding='utf-8'))
        metrics = pd.read_parquet(path / 'metrics_overall.parquet')
        if len(metrics) != 8 or manifest.get('batch_size') != 2048:
            raise ValueError(f'Unexpected run completeness or batch size: {path}')
        for _, row in metrics.iterrows():
            records.append({'pipeline_id': pipeline, 'variant': variant, 'split': row['eval_split'],
                            'phase': row['phase_id'], 'macro_f1': row['f1_macro'],
                            'balanced_acc': row['balanced_accuracy'], 'best_epoch': manifest['best_epoch'],
                            'recall_c0': row['per_class_recall'][0], 'recall_c1': row['per_class_recall'][1],
                            'recall_c2': row['per_class_recall'][2],
                            'static_columns': ','.join(layout['static_columns']),
                            'static_mask_columns': ','.join(layout['mask_static_columns'])})
pd.DataFrame(records).to_csv(abl / 'ablation_comparison.csv', index=False)
print(pd.DataFrame(records).query("phase == 'P1'").to_string(index=False))
