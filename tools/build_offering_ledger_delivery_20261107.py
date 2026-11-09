from pathlib import Path
import hashlib,json,shutil
from datetime import datetime,timezone
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def hashes(out):
    files=sorted(p for p in out.rglob('*') if p.is_file() and p.name!='sha256sums.txt')
    (out/'sha256sums.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(out).as_posix()}\n' for p in files),encoding='utf8')
def main():
    src=ROOT/'LO/resuilt/lo_offering_bootstrap_grid_20261106/cells'
    support=ROOT/'LO/resuilt/lo_offering_support_20261106'
    out=ROOT/'LO/resuilt/lo_offering_bootstrap_delivery_20261107';out.mkdir(parents=True,exist_ok=True)
    files=sorted(src.rglob('*.json'));records=[];seen=set()
    for f in files:
        x=json.loads(f.read_text(encoding='utf8'))
        keys=['task','window_id','eval_split','model_name','pipeline_id','phase_id','seed']
        key=tuple(x[k] for k in keys)
        if key in seen or x['task']!='LO' or x['seed']!=42 or x['bootstrap_replicates']!=2000 or x['prediction_join']!='ONE_TO_ONE_LABELS_MATCH':raise ValueError(f'bad cell {f}')
        seen.add(key)
        if {z['class_code'] for z in x['class_recall']}!={'c0','c1','c2'}:raise ValueError(f'bad class coverage {f}')
        for c in x['class_recall']:
            records.append({**{k:x[k] for k in keys},'bootstrap_seed':x['bootstrap_seed'],'bootstrap_replicates':x['bootstrap_replicates'],'offering_count':x['offering_count'],'prediction_rows':x['prediction_rows'],'prediction_join':x['prediction_join'],**c,'cell_source_sha256':sha(f)})
    if len(files)!=1632 or len(records)!=4896:raise ValueError('bootstrap coverage incomplete')
    frame=pd.DataFrame(records)
    classes=pd.read_csv(support/'class_offering_support.csv');classes['class_code']=classes['class_code'].map({'I/D':'c0','G':'c1','E':'c2'})
    chk=frame.merge(classes[['window_id','eval_split','class_code','n_support','n_offerings_with_class']],on=['window_id','eval_split','class_code'],how='left',validate='many_to_one')
    if chk.n_support.isna().any() or not chk.support.eq(chk.n_support).all() or not chk.offering_count.eq(chk.n_offerings_with_class).all():raise ValueError('support/offering mismatch')
    for name in ('class_offering_support.csv','cell_flags.csv'):
        shutil.copy2(support/name,out/name)
    frame.to_csv(out/'offering_cluster_bootstrap_per_class.csv',index=False)
    frame.to_parquet(out/'offering_cluster_bootstrap_per_class.parquet',index=False)
    meta={'task':'LO','release':'LO_V3_1 static-v2','seed':42,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'cell_count':len(files),'class_rows':len(frame),'bootstrap_repetitions':2000,'unique_cell_keys':len(seen),'source_support_match':'PASS','prediction_join':'ONE_TO_ONE_LABELS_MATCH','class_ci_status':frame.ci_status.value_counts(dropna=False).to_dict(),'limits':['This is source-generated post-hoc bootstrap evidence; per-cell input/source digests included, not a new independent re-execution.','Single-offering intervals not estimable.','Receipt is for this package, not proof of official L2 ingest.']}
    (out/'summary.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (out/'README.md').write_text('# LO offering support and cluster bootstrap — seed 42\n\nSource: local LO static-v2 post-hoc cell JSON and offering support. 1,632 unique model/window/pipeline/split/phase cells and 4,896 class rows. Bootstrap samples offering_id × timeline_source clusters, B=2,000; each source cell reports one-to-one matching of hashed predictions and labels. Per-class support and number of offering clusters are checked against support table. CI conditions on class being present in the bootstrap sample; a single-offering class is not estimable. cell_source_sha256 fingerprints each original cell JSON. No salt is included. These are post-hoc facts, not official L2 ingest.\n',encoding='utf8')
    hashes(out)
    ledger=ROOT/'CQ/resuilt/cq_release_identity_partial_20261103/ledger_modal_current.json'
    x=json.loads(ledger.read_text(encoding='utf8')); bad=x['manifest_scan']['by_identity']
    if x['task']!='CQ' or x['release_id']!='CQ_V2_2' or any(bad.get(k,0) for k in ('UNMATCHED','ABSENT','UNREADABLE')):raise ValueError('ledger identity invalid')
    lo=ROOT/'CQ/resuilt/cq_release_identity_modal_20261107';lo.mkdir(parents=True,exist_ok=True);shutil.copy2(ledger,lo/'ledger.json')
    (lo/'README.md').write_text('# CQ V2.2 release identity ledger — Modal snapshot\n\nCopied read-only from Modal workspace sghqvbg, volume tempo-data-v1, meta_release=imputation-v1/L2_facts/release_identity_ledger/task=CQ/release_id=CQ_V2_2/ledger.json. App generated it on 2026-10-22; it is a historical scan, not a fresh 2026-11-07 scan. The scan records CURRENT, OTHER_RELEASE and UNVERSIONED_S2_PARENT classifications. The unversioned S2 entries require parent lineage interpretation. This package is not the LO ledger.\n',encoding='utf8')
    hashes(lo)
    print(json.dumps({'offering':meta,'ledger_scan':bad,'outputs':[str(out),str(lo)]},indent=2))
if __name__=='__main__':main()
