from pathlib import Path
import hashlib,io,json,shutil,zipfile
from datetime import datetime,timezone
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(z,key):
    matches=[n for n in z.namelist() if f'/{key}/' in n and n.endswith('.parquet')]
    if not matches:raise ValueError(f'missing parquet {key}')
    return pd.concat([pd.read_parquet(io.BytesIO(z.read(n))) for n in matches],ignore_index=True)
def save(frame,out,name):
    frame.to_csv(out/(name+'.csv'),index=False)
    frame.to_parquet(out/(name+'.parquet'),index=False)
def hashes(out):
    (out/'sha256sums.txt').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='sha256sums.txt'),encoding='utf8')
def main():
    lozip=ROOT/'LO/resuilt/m07_label_coverage_audit_v3_1_20261107.zip'
    cqzip=ROOT/'CQ/resuilt/split_registry_v2_2_overlap_audit_v1_r2.zip'
    loout=ROOT/'LO/resuilt/m07_split_evidence_received_20261107_r2';loout.mkdir(parents=True,exist_ok=True)
    cqout=ROOT/'CQ/resuilt/m07_split_evidence_received_20261107';cqout.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(lozip) as z:
        manifest=read(z,'audit_manifest');a=read(z,'assignment_coverage_qa');x=read(z,'slice_exclusion_reason_summary');coverage=read(z,'slice_timeline_summary')
    row=manifest.iloc[0]
    if row['audit_release']!='v3_1_scored_signal_excluded' or not str(row['parent_manifest_source']).endswith('/split_registry_v3_1_scored_signal_excluded_overlap_audit_v1/manifest'):raise ValueError('LO release mismatch')
    assigned=x.groupby('temporal_slice',dropna=False).n_enrollments.sum().to_dict();qa=a.set_index('temporal_slice').n_enrollments.to_dict()
    for s in ('A','T1','T2','T3'):
        if int(assigned[s])!=int(qa[s]):raise ValueError(f'LO assigned mismatch {s}')
    old=pd.read_csv(ROOT/'LO/resuilt/lo_split_evidence_20261106/block_class_counts.csv').groupby('block').block_n.first().to_dict()
    expected={'A':int(old['A']),'T1':int(old['B']+old['C']),'T2':int(old['D']+old['E']),'T3':int(old['F']+old['G'])}
    got=x[x.proxy_status=='ELIGIBLE'].groupby('temporal_slice').n_enrollments.sum().to_dict()
    if got!=expected:raise ValueError(f'LO eligible cohort mismatch: {got} {expected}')
    pivot=x.pivot_table(index='proxy_status',columns='temporal_slice',values='n_enrollments',aggfunc='sum',fill_value=0).reset_index()
    save(x,loout,'slice_exclusion_reason_detail');save(pivot,loout,'slice_exclusion_reason_pivot');save(a,loout,'assignment_coverage_qa');save(coverage,loout,'slice_timeline_summary');save(manifest,loout,'audit_manifest')
    sums=x[(x.proxy_status!='ELIGIBLE')&(x.temporal_slice!='UNASSIGNED')].groupby('temporal_slice').n_enrollments.sum().to_dict()
    missing=int(qa.get('UNASSIGNED',0));observed=int(x[x.temporal_slice!='UNASSIGNED'].n_enrollments.sum())
    unassigned=int(x[x.temporal_slice=='UNASSIGNED'].n_enrollments.sum())
    if unassigned!=missing or int(x.n_enrollments.sum())!=int(a.n_enrollments.sum()):raise ValueError('LO exclusion table does not cover the full assignment QA population')
    summary={'task':'LO','status':'PARTIAL_RAW_SOURCE_AND_MANIFEST_IDENTITY_UNVERIFIED','zip_sha256':digest(lozip),'audit_release':str(row['audit_release']),'parent_manifest_source':str(row['parent_manifest_source']),'eligible_by_slice':expected,'excluded_by_assigned_slice':sums,'excluded_assigned_total':sum(map(int,sums.values())),'assigned_total':observed,'unassigned_enrollments_in_qa':missing,'unassigned_exclusion_reasons_covered':True,'label_artifact_total':int(a.n_enrollments.sum()),'note':'Exclusion counts now cover UNASSIGNED and reconcile to assignment QA. Label artifact population is not an independent raw cohort; manifest path is not a content hash.'}
    (loout/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (loout/'README.md').write_text('# LO M-07 received audit — rerun r2, partial\n\nCounts for A/T1/T2/T3 agree with the assignment QA and eligible counts agree with V3.1 block cohorts. Exclusion detail now includes UNASSIGNED and reconciles to the full assignment QA population. UNASSIGNED denotes an enrollment without an assigned unit in the parent manifest; it must not be treated as a split block. Label artifact population is not an independent raw cohort. The manifest pathname is recorded, not verified content identity.\n',encoding='utf8');hashes(loout)
    with zipfile.ZipFile(cqzip) as z:
        reg=read(z,'split_registry');overlap=read(z,'temporal_overlap_audit_v1');block=read(z,'block_label_audit');qa22=read(z,'qa22_v2_2');calendar=read(z,'calendar_boundaries')
    if set(reg.task)!= {'CQ'} or set(reg.split_version)!={'v2.2'} or not qa22.qa22_ok.all():raise ValueError('CQ release or QA mismatch')
    if set(reg.ev_train_overlap_definition)!={'test_offering_start_date_lt_date(tau_w)'}:raise ValueError('wrong overlap definition')
    if not reg.ev_train_overlap_share.equals(reg.test_offering_start_overlap_share):raise ValueError('overlap mismatch')
    previous=pd.read_csv(ROOT/'CQ/resuilt/cq_split_evidence_partial_20261103/blocks.csv')
    merged=block.merge(previous,left_on='rolling_block',right_on='block',validate='one_to_one')
    for left,right in [('enrollment_count','enrollments'),('offering_count','offering_units'),('warning_count','warning'),('average_count','average'),('good_count','good')]:
        if not merged[left].eq(merged[right]).all():raise ValueError('CQ block mismatch '+left)
    for name,df in [('split_registry',reg),('temporal_overlap',overlap),('block_label_audit',block),('qa22',qa22),('calendar_boundaries',calendar)]:save(df,cqout,name)
    meta={'task':'CQ','status':'PARTIAL_RAW_PRE_LABEL_POPULATION_UNVERIFIED','zip_sha256':digest(cqzip),'qa22_all_pass':bool(qa22.qa22_ok.all()),'block_counts_match_v0_inputs':True,'ev_train_overlap_definition':'test_offering_start_date_lt_date(tau_w)','ev_train_overlap_share':{str(r.window_id):float(r.ev_train_overlap_share) for r in reg.itertuples()},'note':'The overlap share is descriptive offering-start overlap and is distinct from cutoff-based P1 overlap. Original raw cohort remains unverified.'}
    (cqout/'summary.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8');(cqout/'README.md').write_text('# CQ M-07 received registry — partial\n\nCQ V2.2 overlap audit r2: QA22 passes; block enrollment, offering and label counts match independently materialized V0 inputs. ev_train_overlap_share is TEST offering start before tau, not the P1 cutoff overlap. Raw population before labels remains unverified. ZIP SHA-256 identifies the downloaded artifact, not independent provenance.\n',encoding='utf8');hashes(cqout)
    print(json.dumps({'LO':summary,'CQ':meta},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
