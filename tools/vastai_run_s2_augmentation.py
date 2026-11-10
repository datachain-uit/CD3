"""Run one S2 augmentation cell (balanced TRAIN, full P1-P4 sequence) outside Modal.

The cell logic is NOT re-implemented: ``run_augmentation`` and its helpers are taken from ``modal_jobs/augmentation_app.py``
by AST (decorator removed) and executed with ``MOUNT`` pointing at a local directory that mirrors the Modal volume layout,
so the algorithm, the manifests and the output paths are those of the seed-42 runs.

Usage:
    python tools/vastai_run_s2_augmentation.py --mount DIR --task CQ --window W1 --parent V1 --method CDSMOTE --seed 43

``DIR`` must hold the parent run (``meta_release=imputation-v1/L1_runs/task=T/feature_regime=R/window_id=W/pipeline_id=P/
model_name=IMPUTATION_ONLY/seed=20260922/run_id=*/attempt_id=*/{run_manifest.json,model_inputs/train.parquet}``);
the outputs are written below the same ``DIR``.
"""
import argparse
import ast
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ap = argparse.ArgumentParser()
ap.add_argument('--mount', type=Path, required=True)
ap.add_argument('--task', required=True, choices=('CQ', 'LO'))
ap.add_argument('--window', required=True)
ap.add_argument('--parent', required=True)
ap.add_argument('--method', required=True, choices=('CDSMOTE', 'SASMOTE', 'RADIUS_SMOTE'))
ap.add_argument('--seed', type=int, required=True)
ap.add_argument('--phase', default='P4')
ap.add_argument('--release-id', default='')
args = ap.parse_args()

source = (ROOT / 'modal_jobs' / 'augmentation_app.py').read_text(encoding='utf-8')
tree = ast.parse(source)
wanted_assign = {'PARENT', 'REGIME'}
body = []
for node in tree.body:
    if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) in wanted_assign for t in node.targets):
        body.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name in {'_augmentation_quality_metrics', '_label', '_pipeline',
                                                            '_latest_successful_canonical_train', '_resolve_parent_train', 'run_augmentation'}:
        node.decorator_list = []
        body.append(node)
module = ast.Module(body=body, type_ignores=[])
ast.fix_missing_locations(module)


class _Volume:
    def reload(self):
        return None

    def commit(self):
        return None


ns = {'__name__': 'augmentation_vast', 'MOUNT': str(args.mount), 'volume': _Volume(), 'Path': Path, 'hashlib': hashlib, 'json': json, 'time': time, 're': __import__('re')}
exec(compile(module, str(ROOT / 'modal_jobs' / 'augmentation_app.py'), 'exec'), ns)
manifest = ns['run_augmentation'](args.task, args.window, args.phase, args.parent, args.method, args.seed, args.release_id)
# environment sidecar next to the run manifest (library versions of this execution)
import platform  # noqa: E402
import numpy, pandas, pyarrow, sklearn  # noqa: E402
pipeline = ns['_pipeline'](args.parent, args.method)
run_dir = (args.mount / 'meta_release=imputation-v1/L1_runs' / f'task={args.task}' / f"feature_regime={ns['REGIME'][args.task]}" / f'window_id={args.window}' /
           f'phase_id={args.phase}' / f'pipeline_id={pipeline}' / 'model_name=BALANCED_TRAIN_ONLY' / f'seed={args.seed}' / f"run_id={manifest['run_id']}" / f"attempt_id={manifest['attempt_id']}")
(run_dir / 's2_environment.json').write_text(json.dumps({
    'executed_with': 'tools/vastai_run_s2_augmentation.py (run_augmentation of modal_jobs/augmentation_app.py, executed outside Modal)',
    'python': platform.python_version(), 'numpy': numpy.__version__, 'pandas': pandas.__version__, 'pyarrow': pyarrow.__version__,
    'scikit_learn': sklearn.__version__, 'platform': platform.platform(), 'cpu_count': __import__('os').cpu_count(),
    'note': 'resource_summary fields cpu_cores_allocated/memory_allocated_mb/energy_measurement_type keep the values hard-coded in the Modal runner'}, indent=1) + chr(10), encoding='utf-8')
print(json.dumps({'event': 'vast_run_done', 'run_id': manifest.get('run_id'), 'attempt_id': manifest.get('attempt_id'),
                  'rows_balanced': manifest.get('rows_balanced')}), flush=True)
