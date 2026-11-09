"""Count CQ F1 checkpoint parameters alongside the representative context table."""
import hashlib
import json
import math
from pathlib import Path
import sys

import pandas as pd
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.architectures import build_shared_phase_model

root = Path('CQ/resuilt/m13b_model_context_20261108')
rows = []
for name in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
    path = root / 'sources_cq' / name
    manifest = json.loads((path / 'run_manifest.json').read_text(encoding='utf8'))
    checkpoint = torch.load(path / 'model.pt', map_location='cpu', weights_only=False)
    layout = checkpoint['layout']
    if not isinstance(layout, dict):
        layout = layout.to_dict()
    dynamic = len(layout['dynamic_bases']) + sum(c.endswith('_P1') for c in layout['mask_dynamic_columns']) + len(layout.get('mask_phase_bases', [])) + 2
    static = len(layout['static_columns']) + len(layout['mask_static_columns'])
    model = build_shared_phase_model(dynamic, static, len(checkpoint['classes']), name.lower(),
                                    hidden_size=int(manifest.get('hidden_size', 128)),
                                    num_layers=int(manifest.get('num_layers', 1)), dropout=float(manifest.get('dropout', .3)))
    model.load_state_dict(checkpoint['model_state_dict'], strict=True)
    total = sum(p.numel() for p in model.parameters())
    rows.append({'model_name': name, 'reference_task': 'CQ', 'reference_window': manifest['window_id'],
                 'reference_pipeline': manifest['pipeline_id'], 'param_count_total': total,
                 'param_count_trainable': sum(p.numel() for p in model.parameters() if p.requires_grad),
                 'log10_param_count': math.log10(total), 'dynamic_channels': dynamic, 'static_channels': static,
                 'reference_layout_sha256': manifest.get('feature_layout_sha256'),
                 'reference_checkpoint_sha256': hashlib.sha256((path / 'model.pt').read_bytes()).hexdigest(),
                 'runner_git_commit': manifest.get('runner_git_commit')})
frame = pd.DataFrame(rows)
frame.to_csv(root / 'model_context_cq_f1_checkpoints.csv', index=False)
frame.to_parquet(root / 'model_context_cq_f1_checkpoints.parquet', index=False)
(root / 'README.md').write_text('''# M-13b model context — representative checkpoints\n\nCounts come from strict checkpoint loading into the matching model and named-parameter counts. The five-row representative table uses LO/W1/V0 F1 checkpoints and CQ/W1/V4 PatchTST. The CQ F1 supplementary table uses CQ/W1/V0 historical-layout checkpoints. Counts vary by task, input layout and model revision; the CQ F1 examples here have 23 static channels for RNN/LSTM and 22 for GRU/BiLSTM. Their manifest layout hash and runner commit are absent; their checkpoint file hashes are recorded. This is a partial candidate, not a universal five-row context for all task/layout cells.\n''', encoding='utf8')
files = ('model_context_representative.csv', 'model_context_representative.parquet', 'checkpoint_inventory.csv',
         'model_context_cq_f1_checkpoints.csv', 'model_context_cq_f1_checkpoints.parquet', 'README.md')
with (root / 'sha256sums.txt').open('w', encoding='utf8') as out:
    for name in files:
        out.write(f'{hashlib.sha256((root/name).read_bytes()).hexdigest()}  {name}\n')
print(frame.to_string(index=False))
