"""Stage existing experiment results with original portable identities; no source data or secrets."""
from pathlib import Path
import hashlib
import json
import os
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path('\\\\?\\' + str(ROOT / 'upload_staging/drive2_results_20261029'))
FAMILIES = ('RNN', 'LSTM', 'GRU', 'BILSTM')
PREDICTIONS = {f'{split}_{phase}.parquet' for split in ('validation', 'test') for phase in ('P1', 'P2', 'P3', 'P4')}
ALLOWED = {'run_manifest.json', 'metadata_contract.json', 'feature_layout.json', 'train_history.parquet', 'metrics_overall.parquet', 'model.pt'}


def link(source, relative):
    target = STAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if os.path.samefile(source, target):
            return
        if source.stat().st_size != target.stat().st_size or hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
            raise ValueError(f'Collision: {target}')
        return
    os.link(source, target)


def run_dest(task, window, pipeline, family, meta):
    portable = meta.get('portable_run_id')
    if not portable or not portable.startswith('sha256:') or len(portable) != 71:
        raise ValueError(f'Missing/invalid portable_run_id: {task}/{window}/{pipeline}/{family}')
    regime = 'CQ_RAW_EARLY' if task == 'CQ' else 'LO_FULL_EARLY'
    return Path(task) / 'meta_release=imputation-v1' / 'L1_runs' / f'task={task}' / f'feature_regime={regime}' / f'window_id={window}' / f'pipeline_id={pipeline}' / f'model_name={family}' / 'seed=42' / f'portable_run_id=sha256-{portable[7:]}'


def stage_run(task, window, pipeline, family, source, extra_predictions=None):
    manifest = json.loads((source / 'run_manifest.json').read_text(encoding='utf-8'))
    meta = json.loads((source / 'metadata_contract.json').read_text(encoding='utf-8'))
    for key, value in {'task': task, 'window_id': window, 'pipeline_id': pipeline, 'model_name': family, 'seed': 42}.items():
        if manifest.get(key) != value:
            raise ValueError(f'Identity mismatch {source}: {key}')
    dest = run_dest(task, window, pipeline, family, meta)
    for name in ALLOWED:
        p = source / name
        if p.is_file(): link(p, dest / name)
    for pred_root in (source / 'predictions', extra_predictions):
        if pred_root and pred_root.is_dir():
            for name in PREDICTIONS:
                p = pred_root / name
                if p.is_file(): link(p, dest / 'predictions' / name)
    staged = STAGE / dest
    missing = sorted(name for name in ALLOWED if not (staged / name).is_file())
    missing_preds = sorted(name for name in PREDICTIONS if not (staged / 'predictions' / name).is_file())
    return {'task': task, 'window_id': window, 'pipeline_id': pipeline, 'model_name': family, 'portable_run_id': meta['portable_run_id'], 'runner_git_commit': manifest.get('runner_git_commit'), 'destination': str(dest).replace('\\', '/'), 'missing_artifacts': missing, 'missing_predictions': missing_preds}


def fact(task, family, source, table, regime):
    p = source / (table + '.parquet')
    if not p.is_file(): raise FileNotFoundError(p)
    dest = Path(task) / 'meta_release=imputation-v1/L2_facts' / f'fact_table={table}' / f'task={task}' / f'feature_regime={regime}' / f'model_name={family}' / 'seed=42' / p.name
    link(p, dest)


def main():
    STAGE.mkdir(parents=True, exist_ok=True)
    inventory = []
    cq = ROOT / 'CQ/resuilt/cq_f1_allfamilies_l2_ingest_r3_20261021'
    lo = ROOT / 'LO/resuilt/lo_static_v2_seed42_20261026'
    for task in ('CQ', 'LO'):
        regime = 'CQ_RAW_EARLY' if task == 'CQ' else 'LO_FULL_EARLY'
        for family in FAMILIES:
            audit = (cq / 'audits/CQ' / family / 'seed=42' if task == 'CQ' else
                     lo / '_closure_audit_temp/audits_seed42/LO/BILSTM/seed=42' if family == 'BILSTM' else
                     lo / family / 'audits/LO' / family / 'seed=42')
            for table in ('canonical_s_leak', 'sanity_components', 'evaluation_slices', 'metrics_per_class', 'bootstrap_metrics_per_class', 'checkpoint_selection'):
                fact(task, family, audit, table, regime)
            link(audit / 'audit_manifest.json', Path(task) / 'meta_release=imputation-v1/L0_registry/audit_manifests' / f'task={task}' / f'model_name={family}' / 'seed=42/audit_manifest.json')
            for window in ('W1', 'W2', 'W3'):
                for index in range(17):
                    pipeline = f'V{index}'
                    source = (cq / 'artifacts/CQ' / window / pipeline / family / 'seed=42' if task == 'CQ' else
                              lo / '_bilstm_metadata_20261029/LO' / window / pipeline / family / 'seed=42' if family == 'BILSTM' else
                              lo / family / 'LO' / window / pipeline / family / 'seed=42')
                    extra = lo / '_bilstm_predictions/LO' / window / pipeline / family / 'seed=42/predictions' if task == 'LO' and family == 'BILSTM' else None
                    inventory.append(stage_run(task, window, pipeline, family, source, extra))
    # CQ baseline complements its portable run when identities are exactly the same.
    baseline = ROOT / 'CQ/resuilt/cq_rnn_baseline_drive_20261029/V0/RNN/seed=42'
    stage_run('CQ', 'W1', 'V0', 'RNN', baseline)
    replay = ROOT / 'CQ/resuilt/cq_rnn_matched_historical_20261029/seed=42'
    replay_record = stage_run('CQ', 'W1', 'V0', 'RNN', replay)
    replay_record['purpose'] = 'MATCHED_REPLAY_EVIDENCE_NOT_AN_ADDITIONAL_PRIMARY_CELL'
    for window in ('W2', 'W3'):
        pilot = ROOT / 'CQ/resuilt/cq_patchtst_d23_stability_pilot_20261026/CQ' / window / 'V0/PATCHTST/seed=42'
        entry = stage_run('CQ', window, 'V0', 'PATCHTST', pilot)
        entry['purpose'] = 'D23_SENSITIVITY_NOT_PRIMARY_GRID'
        inventory.append(entry)
    pilot_root = ROOT / 'CQ/resuilt/cq_patchtst_v0_seed42_20261023'
    for window in ('W1', 'W2', 'W3'):
        source = pilot_root / window
        manifest = json.loads((source / 'run_manifest.json').read_text(encoding='utf-8'))
        if manifest.get('task') != 'CQ' or manifest.get('window_id') != window or manifest.get('model_name') != 'PATCHTST':
            raise ValueError(f'Invalid pilot identity: {source}')
        dest = Path('CQ/meta_release=imputation-v1/L1_runs/task=CQ/feature_regime=CQ_RAW_EARLY') / f'window_id={window}' / 'pipeline_id=V0/model_name=PATCHTST/seed=42/provenance=pilot_20261023_portable_id_not_recorded'
        for name in ALLOWED:
            if (source / name).is_file(): link(source / name, dest / name)
        inventory.append({'task':'CQ','window_id':window,'pipeline_id':'V0','model_name':'PATCHTST','portable_run_id':None,'runner_git_commit':manifest.get('runner_git_commit'),'destination':str(dest).replace('\\','/'),'purpose':'PILOT_PRIMARY_GRID_HISTORICAL_PROVENANCE'})
    inventory.append(replay_record)
    for pilot_name, audit in [('V0_PILOT', pilot_root / 'audits_v0_seed42/CQ/PATCHTST/seed=42'), ('D23_SENSITIVITY', ROOT / 'CQ/resuilt/cq_patchtst_d23_stability_pilot_20261026/audits/CQ/PATCHTST/seed=42')]:
        for name in ('audit_manifest.json','canonical_s_leak.parquet','sanity_components.parquet','evaluation_slices.parquet','metrics_per_class.parquet','bootstrap_metrics_per_class.parquet','checkpoint_selection.parquet'):
            source = audit / name
            if source.is_file(): link(source, Path('CQ/meta_release=imputation-v1/L2_facts') / f'fact_table={source.stem}' / 'task=CQ/feature_regime=CQ_RAW_EARLY/model_name=PATCHTST/seed=42' / f'evidence={pilot_name}' / name)
    for family in FAMILIES:
        for index in range(17):
            source = ROOT / 'LO/resuilt/lo_static_v2_cohort_audit_20261028' / family / f'V{index}'
            for name in ('seen_unseen_strict_overlap_metrics.parquet','prediction_invariants.parquet','summary.json'):
                if (source / name).is_file(): link(source / name, Path('LO/meta_release=imputation-v1/L2_facts') / f'fact_table={Path(name).stem}' / 'task=LO/feature_regime=LO_FULL_EARLY' / f'model_name={family}/pipeline_id=V{index}/seed=42' / name)
    for task, source in [('CQ',ROOT / 'CQ/resuilt/cq_rnn_matched_historical_20261029/paired_replay_equivalence.json'), ('LO',ROOT / 'LO/resuilt/lo_static_v2_cohort_audit_20261028/paired_replay_equivalence.json')]:
        link(source, Path(task) / 'meta_release=imputation-v1/L2_facts/fact_table=replay_equivalence' / f'task={task}/window_id=W1/pipeline_id=V0/model_name=RNN/seed=42' / source.name)
    prefix = ROOT / 'LO/resuilt/lo_prefix_source_audit_20261028'
    for name in ('summary_static13_full_scan.json','prefix_mask_full_scan.csv','static13_parity.csv'):
        link(prefix / name, Path('LO/meta_release=imputation-v1/L2_facts/fact_table=prefix_static_audit/task=LO') / name)
    cq_facts = ROOT / 'CQ/resuilt/cq_recurrent_allfamilies_grid_r4_20261023'
    for name in ('cq_family_pipeline_window_phase_metrics.parquet', 'cq_metrics_per_class_long.parquet', 'cq_bootstrap_metrics_per_class_long.parquet', 'cq_resource_per_run.parquet', 'cq_qa23_reviewed_behavioural_linkage.parquet'):
        source = cq_facts / name
        link(source, Path('CQ/meta_release=imputation-v1/L2_facts') / f'fact_table={source.stem}/task=CQ/feature_regime=CQ_RAW_EARLY/seed=42' / name)
    cq_prefix = ROOT / 'CQ/resuilt/cq_full_prefix_static_audit_20261017/full_scan.json'
    if cq_prefix.is_file(): link(cq_prefix, Path('CQ/meta_release=imputation-v1/L2_facts/fact_table=prefix_static_audit/task=CQ') / cq_prefix.name)
    resource_rows = []
    for entry in inventory:
        if entry['task'] != 'LO': continue
        staged = STAGE / entry['destination']
        m = json.loads((staged / 'run_manifest.json').read_text(encoding='utf-8'))
        history = pd.read_parquet(staged / 'train_history.parquet')
        resource_rows.append({'task':'LO','window_id':entry['window_id'],'pipeline_id':entry['pipeline_id'],'model_name':entry['model_name'],'seed':42,
            'portable_run_id':entry['portable_run_id'], 'train_seconds':float(history['train_seconds'].sum()),
            'elapsed_seconds':m.get('elapsed_seconds'),'peak_ram_mb':m.get('peak_ram_mb'), 'gpu':m.get('gpu'),
            'energy_gpu_estimated_kwh':m.get('energy_gpu_estimated_kwh'), 'energy_measurement_type':m.get('energy_measurement_type'),
            'energy_missing_sample_rate':m.get('energy_missing_sample_rate'), 'fact_source':'derived_from_run_manifest_and_train_history'})
    assert len(resource_rows) == 204
    resource_dest = STAGE / 'LO/meta_release=imputation-v1/L2_facts/fact_table=resource_usage/task=LO/feature_regime=LO_FULL_EARLY/seed=42'
    resource_dest.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(resource_rows).to_parquet(resource_dest / 'resource_usage_derived.parquet', index=False)
    for task, path in [('CQ', ROOT / 'CQ/docs/REPORT_CQ_CONSOLIDATED_EVIDENCE_2026-10-28_R20_DAY_DU.docx'), ('LO', ROOT / 'LO/docs/REPORT_LO_STATIC_V2_CONSOLIDATED_EVIDENCE_2026-10-28_R20_DAY_DU.docx')]:
        link(path, Path(task) / 'meta_release=imputation-v1/reports' / path.name)
    for record in inventory:
        staged = STAGE / record['destination']
        record['missing_artifacts'] = sorted(name for name in ALLOWED if not (staged / name).is_file())
        record['missing_predictions'] = sorted(name for name in PREDICTIONS if not (staged / 'predictions' / name).is_file())
    for task in ('CQ','LO'):
        rows = [x for x in inventory if x['task'] == task]
        dest = STAGE / task / 'meta_release=imputation-v1/L0_registry/run_inventory'
        dest.mkdir(parents=True, exist_ok=True)
        (dest / 'local_result_inventory.json').write_text(json.dumps({'task':task, 'runs':rows}, indent=2), encoding='utf-8')
        readme = STAGE / task / 'meta_release=imputation-v1/README.txt'
        readme.write_text('Research result export; L0 registry includes inventory/audit manifests, L1 contains actual VastAI portable_run_id and available artefacts, L2 contains facts partitioned by their true scope. Missing artifacts are reported in L0 inventory. No fake run_id or attempt_id is created. Source input, secrets, and historical LO 15-column grid are excluded. L3 is not claimed to exist. D23 and replay are evidence, not primary cells.\n', encoding='utf-8')
        l3 = STAGE / task / 'meta_release=imputation-v1/L3_meta'
        l3.mkdir(parents=True, exist_ok=True)
        (l3 / 'STATUS.txt').write_text('No finalized meta-dataset is included in this export. This placeholder is not an L3 completion claim.\n', encoding='utf-8')
        print(task, 'runs_including_evidence', len(rows), 'runs_missing_predictions', sum(bool(x['missing_predictions']) for x in rows), 'runs_missing_artifacts', sum(bool(x['missing_artifacts']) for x in rows))


if __name__ == '__main__': main()
