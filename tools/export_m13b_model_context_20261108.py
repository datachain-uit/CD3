"""Build a five-model context table from verified representative checkpoints."""
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
sources = root / 'sources'
paths = {name: sources / name for name in ('RNN', 'LSTM', 'GRU', 'BILSTM')}
paths['PATCHTST'] = Path('CQ/resuilt/cq_patchtst_v4_seed42_20261101_backup/cq_patchtst_v4_seed42_20261101/CQ/W1/V4/PATCHTST/seed=42')

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

rows, inventory = [], []
for name, path in paths.items():
    manifest = json.loads((path / 'run_manifest.json').read_text(encoding='utf8'))
    checkpoint = torch.load(path / 'model.pt', map_location='cpu', weights_only=False)
    layout = checkpoint['layout']
    if not isinstance(layout, dict):
        layout = layout.to_dict()
    phase_masks = sum(c.endswith('_P1') for c in layout['mask_dynamic_columns'])
    dynamic = len(layout['dynamic_bases']) + phase_masks + len(layout.get('mask_phase_bases', [])) + 2
    static = len(layout['static_columns']) + len(layout['mask_static_columns'])
    model = build_shared_phase_model(dynamic, static, len(checkpoint['classes']), name.lower(),
                                    hidden_size=int(manifest.get('hidden_size', 128)),
                                    num_layers=int(manifest.get('num_layers', 1)),
                                    dropout=float(manifest.get('dropout', .3)))
    model.load_state_dict(checkpoint['model_state_dict'], strict=True)
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    row = dict(model_name=name, model_tier='F2_TS_TRANSFORMER' if name == 'PATCHTST' else 'F1_RECURRENT',
               model_family='LSTM' if name == 'BILSTM' else name, param_count_total=total,
               param_count_trainable=trainable, log10_param_count=math.log10(total), uses_mask_channels=1,
               uses_delta_t=1, max_seq_len=4, patch_len=2 if name == 'PATCHTST' else None,
               patch_stride=1 if name == 'PATCHTST' else None, lr=manifest.get('learning_rate'),
               batch_size=manifest.get('batch_size'), max_epochs=manifest.get('max_epochs'),
               loss_name='CrossEntropyLoss', class_weighting='NONE', reference_task=manifest['task'],
               reference_window=manifest['window_id'], reference_pipeline=manifest['pipeline_id'],
               reference_layout_sha256=manifest.get('feature_layout_sha256'),
               reference_checkpoint_sha256=sha(path / 'model.pt'), reference_dynamic_channels=dynamic,
               reference_static_channels=static, model_revision=manifest.get('model_revision'))
    rows.append(row)
    for file in ('model.pt', 'run_manifest.json'):
        inventory.append(dict(model_name=name, artifact=file, source=str(path / file), sha256=sha(path / file)))
frame = pd.DataFrame(rows)
root.mkdir(parents=True, exist_ok=True)
frame.to_csv(root / 'model_context_representative.csv', index=False)
frame.to_parquet(root / 'model_context_representative.parquet', index=False)
pd.DataFrame(inventory).to_csv(root / 'checkpoint_inventory.csv', index=False)
(root / 'README.md').write_text('''# M-13b model context — representative checkpoints\n\nCounts come from strict checkpoint loading into the corresponding model and count named parameters, not arbitrary state tensors. The F1 checkpoint references are LO/W1/V0; PATCHTST is CQ/W1/V4. Counts vary with task, feature layout and model revision. This table is a representative partial candidate: do not use one count as the true value for every task/layout without validating the assembler contract. No missing task-specific count has been inferred.\n''', encoding='utf8')
with (root / 'sha256sums.txt').open('w', encoding='utf8') as f:
    for name in ('model_context_representative.csv', 'model_context_representative.parquet', 'checkpoint_inventory.csv', 'README.md'):
        f.write(f'{sha(root/name)}  {name}\n')
print(frame.to_string(index=False))
