"""Inspect checkpoint dimensions and parameter tensors without claiming cross-layout invariance."""
import json
from pathlib import Path
import torch

root = Path('CQ/resuilt/m13b_model_context_20261108/sources')
paths = {name: root / name for name in ('RNN', 'LSTM', 'GRU', 'BILSTM')}
paths['PATCHTST'] = Path('CQ/resuilt/cq_patchtst_v4_seed42_20261101_backup/cq_patchtst_v4_seed42_20261101/CQ/W1/V4/PATCHTST/seed=42')
for name, path in paths.items():
    manifest = json.loads((path / 'run_manifest.json').read_text(encoding='utf8'))
    checkpoint = torch.load(path / 'model.pt', map_location='cpu', weights_only=False)
    state = checkpoint['model_state_dict']
    print(name, 'task', manifest['task'], 'state_tensors', len(state), 'numel', sum(v.numel() for v in state.values()),
          'shapes', [(k, tuple(v.shape)) for k, v in list(state.items())[:5]], flush=True)
