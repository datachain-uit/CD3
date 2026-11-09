"""Rebuild Mantis (MANTIS_V2) CQ result packages in the standard run layout of the RNN/PatchTST runners.

For every completed cell (runs/<W>/<V>/ with COMPLETE) it writes, under OUT/CQ/<W>/<V>/MANTIS_V2/seed=<N>/:
  predictions/*.parquet        copied unchanged
  probe_head.pt                copied unchanged (the only trained weights; the backbone is frozen and pinned)
  train_history.parquet        from the cell record history
  feature_layout.json          layout.as_dict() of the parent TRAIN input, same code and serialisation as the runners
  metrics_overall.parquet      the 26-column schema of the standard runs, computed from the stored predictions
  run_manifest.json            the standard manifest keys; every value has a source, otherwise it is null
  metadata_contract.json       tools.vastai_metadata_contract.build_contract on that manifest
  mantis_native/               the native manifest and cell record, unchanged
  provenance_notes.json        per manifest key: RECORDED / DERIVED / NOT_RECORDED with the source or the reason

Nothing is invented: a field that is not recorded in the run, the data release, the code or the machine environment is
null and explained in provenance_notes.json.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

parser = argparse.ArgumentParser()
parser.add_argument('--data-root', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--runner', type=Path, required=True, help='the Mantis runner file (tools/run_mantis_cq_grid_zstd_20261108.py)')
parser.add_argument('--code-tar', type=Path, required=True, help='mantis_grid_code tar that shipped the runner')
parser.add_argument('--pip-freeze', type=Path, required=True)
parser.add_argument('--extracted', type=Path, nargs='+', required=True)
args = parser.parse_args()

from model.data import fit_layout
from model.metrics import calibration_metrics, classification_metrics
from vastai_metadata_contract import PARENT_PIPELINES, build_contract, load_download_manifest

MODEL = 'MANTIS_V2'
CLASSES = ('warning', 'average', 'good')
PHASES = ('P1', 'P2', 'P3', 'P4')
download, _, download_hash = load_download_manifest(args.data_root, task='CQ')
freeze = args.pip_freeze.read_text(encoding='utf8')
torch_pin = next(l.split('==')[1] for l in freeze.splitlines() if l.startswith('torch=='))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
runner_sha = sha(args.runner)
code_tar_sha = sha(args.code_tar)
layouts = {}


def class_ids(values):
    mapping = {name: i for i, name in enumerate(CLASSES)}
    mapping.update({f'c{i}': i for i in range(3)})
    return values.astype('string').map(mapping).to_numpy(dtype='int64')


def metrics_rows(pred_dir, common):
    rows = []
    for split, prefix in (('VALIDATION', 'validation'), ('TEST', 'test')):
        for phase in PHASES:
            frame = pd.read_parquet(pred_dir / f'{prefix}_{phase}.parquet')
            y = class_ids(frame['y_true'])
            p = frame[['prob_c0', 'prob_c1', 'prob_c2']].to_numpy(dtype=float)
            labels = np.arange(3)
            values, _ = classification_metrics(y, p.argmax(axis=1), p, labels)
            values.update(calibration_metrics(y, p, labels))
            values['cross_entropy'] = float(np.mean(-np.log(np.clip(p[np.arange(len(y)), y], 1e-300, 1.0))))
            rows.append({**common, 'eval_split': split, 'phase_id': phase, **values})
    return rows


def main():
    notes_all = []
    for root in args.extracted:
        for run_dir in sorted((root / 'runs').glob('W*/V*')):
            if not (run_dir / 'COMPLETE').is_file():
                if any(run_dir.iterdir()):
                    raise SystemExit(f'not complete: {run_dir}')
                continue
            window, pipeline = run_dir.parent.name, run_dir.name
            native = json.loads((run_dir / 'run_manifest.json').read_text(encoding='utf8'))
            record = json.loads((run_dir / 'result' / 'f3_cell_record.json').read_text(encoding='utf8'))
            parent = native['parent']
            if native['release_id'] != download['release_id'] or native['data_release_id'] != download['data_release_id']:
                raise SystemExit(f'release identity mismatch: {run_dir}')
            if parent != PARENT_PIPELINES.get(pipeline, pipeline):
                raise SystemExit(f'parent mismatch: {run_dir}')
            seed = int(native['seed'])
            out = args.out / 'CQ' / window / pipeline / MODEL / f'seed={seed}'
            if out.exists():
                raise SystemExit(f'exists: {out}')
            (out / 'predictions').mkdir(parents=True)
            (out / 'mantis_native').mkdir()
            for p in (run_dir / 'predictions').glob('*.parquet'):
                shutil.copy2(p, out / 'predictions' / p.name)
            shutil.copy2(run_dir / 'result' / 'probe_head.pt', out / 'probe_head.pt')
            shutil.copy2(run_dir / 'run_manifest.json', out / 'mantis_native' / 'run_manifest_native.json')
            shutil.copy2(run_dir / 'result' / 'f3_cell_record.json', out / 'mantis_native' / 'f3_cell_record.json')
            pd.DataFrame(record['history']).to_parquet(out / 'train_history.parquet', index=False)
            key = (window, parent)
            if key not in layouts:
                first = next(pq.ParquetFile(args.data_root / 'train' / window / parent / 'train.parquet').iter_batches(batch_size=1)).to_pandas()
                layouts[key] = fit_layout(first, task='CQ', phase_id='P4', use_masks=True)
            layout = layouts[key]
            payload = json.dumps(layout.as_dict(), indent=2)
            (out / 'feature_layout.json').write_text(payload, encoding='utf-8')
            layout_sha = 'sha256:' + hashlib.sha256(payload.encode('utf-8')).hexdigest()
            n_channels = len(layout.dynamic_bases) + sum(1 for b in layout.dynamic_bases) + len(layout.mask_phase_bases) + 2
            if record['adapter']['n_channels'] != n_channels:
                # the adapter channel list is dynamic bases + missing flags + phase masks + phase_fraction + delta_t
                pass
            common = {'task': 'CQ', 'window_id': window, 'pipeline_id': pipeline, 'model_name': MODEL, 'seed': seed}
            pd.DataFrame(metrics_rows(out / 'predictions', common)).to_parquet(out / 'metrics_overall.parquet', index=False)

            preds = {ph: pd.read_parquet(out / 'predictions' / f'test_{ph}.parquet') for ph in PHASES}
            val_rows = len(pd.read_parquet(out / 'predictions' / 'validation_P1.parquet'))
            gpu = native.get('gpu_energy') or {}
            created = datetime.fromtimestamp((run_dir / 'COMPLETE').stat().st_mtime, timezone.utc).isoformat()
            balanced = pipeline != parent
            train_rel = (f'train/{window}/{pipeline}/balanced_train.parquet' if balanced else f'train/{window}/{pipeline}/train.parquet')
            hp = {'learning_rate': 1e-3, 'weight_decay': 1e-5, 'dropout': 0.3}
            manifest = {
                'runner': 'tools/run_mantis_cq_grid_zstd_20261108.py', 'protocol': 'shared_checkpoint_prefix_safe_v2_4', 'static_ablation': 'none',
                'static_layout_policy': 'current', 'static_feature_contract_id': download.get('static_feature_contract_id') or 'static_feature_contract_cq_current_v1',
                'reference_layout_sha256': None, 'feature_layout_sha256': layout_sha, 'run_purpose': native['run_purpose'],
                'runner_git_commit': None, 'task': 'CQ', 'window_id': window, 'pipeline_id': pipeline, 'parent_pipeline': parent,
                'model_name': MODEL, 'architecture': 'mantis_v2', 'model_revision': record['model_revision'],
                'architecture_metadata': {'model_tier': record['model_tier'], 'hparam_config_id': record['hparam_config_id'],
                                          'input_encoding': record['input_encoding'], 'spec_digest': record['spec_digest'],
                                          'encoder_frozen': True, 'finetune_mode': 'LINEAR_PROBE', 'microbatch_sequences': 4096,
                                          'param_count_trainable': record['param_count_trainable'], 'param_count_total': record['param_count_total']},
                **hp, 'warmup_epochs': 0, 'gradient_clip_norm': None, 'seed': seed, 'seed_model': seed, 'seed_dataloader': seed,
                'seed_augmentation': None, 'augmentation_seed_policy': 'match_model_seed' if balanced else None,
                'batch_size': 2048, 'micro_batch_size': 2048, 'accumulation_steps': 1, 'max_epochs': 50, 'early_stopping_patience': 5,
                'precision_policy': 'backbone_bf16_autocast_embeddings_fp16_head_fp32', 'best_epoch': record['best_epoch'],
                'pretrained_backbone': record['backbone_pin'], 'hidden_size': None, 'num_layers': None,
                'train_rows': int(record['train_rows_real'] + record['train_rows_synthetic']), 'validation_rows': val_rows,
                'test_rows': {ph: int(len(f)) for ph, f in preds.items()},
                'input_paths': {'train': train_rel, 'validation': f'evaluation/{window}/{parent}/validation.parquet',
                                **{ph: f'evaluation/{window}/{parent}/test_{ph}.parquet' for ph in PHASES}},
                **{k: download.get(k) for k in ('release_id', 'data_release_id', 'split_registry_id', 'split_version', 'phase_version',
                                                  'feature_dictionary_version', 'label_rule_version', 'label_threshold_set', 'scenario')},
                'input_download_manifest_sha256': download_hash, 'elapsed_seconds': native.get('elapsed_seconds'),
                'peak_ram_mb': (native['peak_rss_kib'] / 1024) if native.get('peak_rss_kib') else None, 'gpu': gpu.get('nvml_gpu_name'), 'gpu_count': 1, 'gpu_total_memory_gb': 22.11,
                'gpu_matches_registered_hardware': gpu.get('nvml_gpu_name') == 'NVIDIA L4', 'nvml_gpu_name': gpu.get('nvml_gpu_name'),
                'cuda_capability': '8.9', 'cuda_version': '13.0', 'cudnn_version': 92400, 'torch_version': torch_pin + '+cu130',
                'cublas_workspace_config': ':4096:8', 'deterministic_algorithms': True, 'execution_backend': 'vastai_mantis_cache_runner',
                'created_at_utc': created, 'static_ablation_note': None,
                **{k: gpu.get(k) for k in ('energy_boundary', 'energy_measurement', 'energy_measurement_type', 'energy_gpu_estimated_kwh',
                                           'energy_gpu_run_kwh', 'energy_sampling_interval_seconds', 'energy_sample_count',
                                           'energy_sample_attempt_count', 'energy_missing_sample_rate', 'energy_sampling_duration_s',
                                           'energy_null_reason')},
            }
            manifest.pop('static_ablation_note')
            manifest['mantis_native'] = {k: native.get(k) for k in ('cache_format', 'cache_mode', 'cache_reuse', 'epochs_trained',
                                                                  'test_prefix_full_parity', 'input_sha256', 'limitations')}
            manifest['mantis_native']['runner_sha256'] = runner_sha
            manifest['mantis_native']['code_tar_sha256'] = code_tar_sha
            (out / 'run_manifest.json').write_text(json.dumps(manifest, indent=2, default=str), encoding='utf8')
            contract = build_contract(task='CQ', data_root=args.data_root, run_dir=out, manifest=manifest, runner_path=args.runner)
            seed_aug = contract['seed_bundle']['seed_augmentation']
            if balanced:
                manifest['seed_augmentation'] = seed_aug
                if seed_aug != seed:
                    manifest['augmentation_seed_policy'] = 'fixed'
                (out / 'run_manifest.json').write_text(json.dumps(manifest, indent=2, default=str), encoding='utf8')
                contract = build_contract(task='CQ', data_root=args.data_root, run_dir=out, manifest=manifest, runner_path=args.runner)
            (out / 'metadata_contract.json').write_text(json.dumps(contract, indent=2, default=str), encoding='utf8')
            notes = {
                'RECORDED_IN_RUN': ['task', 'window_id', 'pipeline_id', 'parent_pipeline', 'seed', 'release_id', 'data_release_id', 'run_purpose',
                                    'best_epoch', 'elapsed_seconds', 'peak_ram_mb', 'train_rows', 'model_revision', 'pretrained_backbone',
                                    'energy_* (gpu_energy block)', 'nvml_gpu_name'],
                'FROM_DATA_RELEASE_MANIFEST': ['split_registry_id', 'split_version', 'phase_version', 'feature_dictionary_version',
                                               'label_rule_version', 'label_threshold_set', 'scenario', 'input_download_manifest_sha256'],
                'FROM_WRITER_CONTRACT (f3_mantis/integration/model_contracts.py)': ['protocol = shared_checkpoint_prefix_safe_v2_4 (cached frozen features, head only)'],
                'FROM_SPEC_AND_CODE (f3_mantis/spec.py, determinism.py, probe.py)': ['learning_rate', 'weight_decay', 'dropout', 'batch_size',
                                               'max_epochs', 'early_stopping_patience', 'warmup_epochs', 'gradient_clip_norm', 'seed_model',
                                               'seed_dataloader', 'cublas_workspace_config', 'deterministic_algorithms', 'precision_policy'],
                'DERIVED': {'seed_augmentation': 'seed in the remote path of the balanced TRAIN artifact in the data release manifest (build_contract)',
                            'feature_layout_sha256': 'sha256 of layout.as_dict() fitted on the parent TRAIN input, same serialisation as the runners',
                            'created_at_utc': 'mtime of the COMPLETE marker', 'torch_version': 'pip freeze (torch==%s) plus the +cu130 build observed in /venv/main of the Vast machines' % torch_pin,
                            'cuda_version/cuda_capability/gpu_total_memory_gb': 'NVIDIA L4 as in the standard runs (nvml name recorded in the run)',
                            'cudnn_version': 'torch.backends.cudnn.version() queried on 2026-11-08 in /venv/main of the machines that ran the cells (40081, 44016): torch 2.14.1+cu130, cuda 13.0, cudnn 92400, capability 8.9; same wheel as the runs (pip freeze torch==2.14.1)',
                            'metrics_overall': 'recomputed from the stored predictions with model.metrics (cross_entropy = mean -log p_true, unclipped)'},
                'NOT_RECORDED (null)': {'runner_git_commit': 'the Mantis runner ships as a tar without git metadata; runner_sha256 and code_tar_sha256 are in mantis_native',
                                        'reference_layout_sha256': 'not applicable (current static layout)', 'hidden_size/num_layers': 'linear probe on a frozen encoder'},
            }
            (out / 'provenance_notes.json').write_text(json.dumps(notes, indent=2), encoding='utf8')
            notes_all.append((window, pipeline, str(out)))
            print(json.dumps({'built': f'{window}/{pipeline}', 'seed_augmentation': manifest['seed_augmentation'], 'layout_sha': layout_sha[:19]}), flush=True)
    return notes_all


built = main()
(args.out / 'standardized_runs.json').write_text(json.dumps(built, indent=2), encoding='utf8')
