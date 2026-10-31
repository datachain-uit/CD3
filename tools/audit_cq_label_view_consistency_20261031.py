"""Compare the downloaded CQ labels with release views, without writing inputs."""
import io, json, zipfile, glob
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('G:/My Drive/Jobs/CQ/organized_moved_20261029/input_archives/source_inputs_20261029/_checked_feature_v2')
OUT = ROOT / 'CQ/resuilt/cq_label_view_consistency_20261031.json'

def one(pattern):
    found = glob.glob(str(BASE / pattern), recursive=True)
    if len(found) != 1:
        raise RuntimeError(f'Expected one file for {pattern}, found {len(found)}')
    return found[0]

def main():
    with zipfile.ZipFile(ROOT / 'CQ/resuilt/cq_labels_v1.zip') as z:
        files = [x for x in z.namelist() if x.endswith('.parquet')]
        if len(files) != 1: raise ValueError('Expected one label parquet')
        labels = pq.read_table(io.BytesIO(z.read(files[0])), columns=['enrollment_id','CQ_label_final','cq_exclusion_reason']).to_pandas()
    if labels.enrollment_id.isna().any() or labels.enrollment_id.duplicated().any(): raise ValueError('Invalid label grain')
    labels = labels.rename(columns={'CQ_label_final':'source_label'})
    output = {'source_zip':'CQ/resuilt/cq_labels_v1.zip','results':[]}
    sources = [('train_validation','phase_views_v2_2/**/*.parquet')] + [(f'test_p{p}',f'test_prefix_views_v2_2/P{p}/*.parquet') for p in range(1,5)]
    for kind, pattern in sources:
        file = one(pattern)
        v = pq.read_table(file, columns=['enrollment_id','window','split','CQ_label_final']).to_pandas()
        j = v.merge(labels, on='enrollment_id', how='left', validate='many_to_one', indicator=True)
        for (window, split), group in j.groupby(['window','split'], observed=True):
            mismatch = group['CQ_label_final'].fillna('<NULL>') != group['source_label'].fillna('<NULL>')
            output['results'].append({'input':kind,'window':window,'split':split,'rows':len(group),'distinct_enrollments':int(group.enrollment_id.nunique()),'source_missing':int((group['_merge']!='both').sum()),'source_excluded':int(group.cq_exclusion_reason.notna().sum()),'label_mismatches':int(mismatch.sum()),'label_counts':{str(k):int(v) for k,v in group['CQ_label_final'].value_counts(dropna=False).items()}})
        del v,j
    for window in ('W1','W2','W3'):
        phases = [x for x in output['results'] if x['window']==window and x['split']=='test']
        if len(phases)!=4: raise ValueError(f'Missing test phase: {window}')
        if len({(x['rows'], tuple(sorted(x['label_counts'].items()))) for x in phases})!=1:
            raise ValueError(f'Test phase counts or labels differ: {window}')
    OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False,indent=2))

if __name__ == '__main__': main()
