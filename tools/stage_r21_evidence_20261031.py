"""Stage identifiable local evidence and record hashes; never claim completeness."""
from pathlib import Path
import hashlib, json, shutil

ROOT = Path(__file__).resolve().parents[1]
DRIVE = Path('G:/My Drive/Jobs')
DEST = ROOT/'CQ/resuilt/input/results/R21_evidence_20261031'

def main():
    sources = []
    for task, name in [('CQ','cq_recurrent_allfamilies_grid_r4_20261023'),('LO','lo_recurrent_allfamilies_grid_r2_20261021')]:
        path=DRIVE/task/'organized_moved_20261029/L2_facts/fact_exports'/name
        sources.extend((x,Path(task)/'facts'/x.name) for x in path.iterdir() if x.is_file() and x.suffix in ('.json','.parquet'))
    d23=DRIVE/'CQ/organized_moved_20261029/L1_runs/S3_model/run_bundles/cq_patchtst_d23_stability_pilot_20261026'
    sources.extend((x,Path('CQ/D23')/x.relative_to(d23)) for x in d23.rglob('train_history.parquet'))
    s2=DRIVE/'CQ/organized_moved_20261029/L1_runs/S2_augmentation/provenance_seed42'
    sources.extend((x,Path('CQ/S2_seed42')/x.relative_to(s2)) for x in s2.rglob('run_manifest.json'))
    qa=DRIVE/'CQ/organized_moved_20261029/L2_facts/fact_exports/qa23_v2_2'
    for phase in ('P1','P2','P3','P4'):
        for kind in ('qa23_summary','feature_dictionary_v1','imputer_predictors_cq_raw_early'):
            sources.extend((x,Path('CQ/QA23')/x.relative_to(qa)) for x in (qa/f'phase_id={phase}'/kind).rglob('*.parquet'))
    lo=DRIVE/'LO/organized_moved_20261029/L1_runs/S3_model/run_bundles/lo_static_v2_seed42_20261026/audits/closure_seed42'
    sources.extend((x,Path('LO/audit_seed42')/x.relative_to(lo)) for x in lo.rglob('*') if x.is_file() and x.suffix in ('.parquet','.json'))
    lo_models=DRIVE/'LO/organized_moved_20261029/L1_runs/S3_model/run_bundles/lo_static_v2_seed42_20261026/models'
    for family in ('RNN','LSTM','GRU'):
        audit=lo_models/family/'audits'
        sources.extend((x,Path('LO/audit_seed42')/family/x.relative_to(audit)) for x in audit.rglob('*') if x.is_file() and x.suffix in ('.parquet','.json'))
    for task, rel in [('CQ','cq_full_prefix_static_audit_20261017/full_scan.json'),('LO','lo_prefix_source_audit_20261028/summary.json')]:
        path=DRIVE/task/'organized_moved_20261029/L2_facts/audits_and_evidence'/rel
        if path.exists(): sources.append((path,Path(task)/'prefix_audit'/path.name))
    for source,relative in [('CQ/resuilt/cq_rnn_matched_historical_20261029/paired_replay_equivalence.json','CQ/replay/rnn_matched.json'),('CQ/resuilt/cq_patchtst_v0_current_seed42_r21_report/current_epoch1_replay_receipt.json','CQ/replay/patchtst_current_epoch1.json'),('CQ/resuilt/cq_label_view_consistency_20261031.json','CQ/labels/label_view_consistency.json')]:
        sources.append((ROOT/source,Path(relative)))
    for name in ('REPORT_CQ_PATCHTST_V0_CURRENT_2026-10-31.docx','REPORT_CQ_PATCHTST_V0_CURRENT_2026-10-31_STATIC_PROVENANCE.docx','BAO_CAO_CQ_PATCHTST_V0_HIEU_SUAT_REPLAY_2026-10-31.docx'):
        sources.append((ROOT/'CQ/docs'/name,Path('CQ/V0_reports')/name))
    for name in ('run_contracts.csv','training_history.csv','metrics_and_sanity.csv','per_class_recall_ci.csv'):
        sources.append((ROOT/'CQ/resuilt/cq_patchtst_v0_current_seed42_r21_report'/name,Path('CQ/V0_reports')/name))
    receipts=[]
    for src,rel in sources:
        if not src.is_file():
            receipts.append({'source':str(src),'destination':str(rel),'status':'MISSING'}); continue
        dst=DEST/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
        with src.open('rb') as f: source_digest=hashlib.file_digest(f,'sha256').hexdigest()
        with dst.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
        if source_digest != digest: raise ValueError(f'Copy checksum mismatch: {src}')
        receipts.append({'source':str(src),'destination':rel.as_posix(),'bytes':dst.stat().st_size,'sha256':digest,'status':'COPIED_VERIFIED'})
    manifest={'status':'PARTIAL_NOT_RELEASED','warning':'Selected facts only; not complete R21 checklist. Verify source release identity before use.','files':receipts}
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (DEST/'README.md').write_text('# R21 evidence — partial staging\n\nSelected CQ/LO facts, D23 histories and replay receipts. See manifest.json for original Drive/local path and SHA-256. This is not the complete R21 evidence package and is not a scientific approval.\n',encoding='utf-8')
    (DEST/'LO/facts/README_HISTORICAL_R2.md').write_text('# Historical LO R2 export\n\nThese facts are historical R2, not the current static-v2 grid. Current static-v2 audit facts are in LO/audit_seed42/. Do not combine the two releases.\n',encoding='utf-8')
    print(json.dumps({'staged':len(receipts),'d23_histories':len(list((DEST/'CQ/D23').rglob('train_history.parquet'))),'missing':sum(x['status']=='MISSING' for x in receipts),'destination':str(DEST)},ensure_ascii=False))

if __name__=='__main__': main()
