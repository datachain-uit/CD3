"""Read-only audit of primary_risk_set in the CQ V0 input used by PatchTST."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'downloads/vastai/CQ_V2_2_clean_grain_seed42'
RUNS = ROOT / 'CQ/resuilt/cq_patchtst_v0_current_seed42_r21/CQ'
UPLOAD = ROOT / 'downloads/cq_f2_inputs_r21_upload_receipt.json'
SOURCE_SCAN = Path('G:/My Drive/Jobs/CQ/organized_moved_20261029/L2_facts/audits_and_evidence/cq_full_prefix_static_audit_20261017/full_scan.json')
OUT = ROOT / 'CQ/resuilt/cq_primary_risk_set_audit_20261031'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def profile(table, name):
    arr = table[name]
    distinct = pc.count_distinct(arr).as_py()
    return {'rows':len(arr), 'nulls':arr.null_count, 'distinct_nonnull':distinct,
            'min':pc.min(arr).as_py(), 'max':pc.max(arr).as_py(),
            'values':pc.unique(arr).to_pylist() if distinct <= 10 else None}


def main():
    receipt = json.loads(UPLOAD.read_text(encoding='utf-8'))
    assert receipt['release_id']=='CQ_V2_2' and len(receipt['files'])==126
    hashes = {x['path']:x['sha256'] for x in receipt['files']}
    manifest_hash = 'sha256:' + sha256(DATA/'download_manifest.json')
    records=[]; layouts=[]
    for window in ('W1','W2','W3'):
        run=RUNS/window/'V0/PATCHTST/seed=42'
        manifest=json.loads((run/'run_manifest.json').read_text(encoding='utf-8'))
        layout=json.loads((run/'feature_layout.json').read_text(encoding='utf-8'))
        assert manifest['release_id']=='CQ_V2_2' and manifest['input_download_manifest_sha256']==manifest_hash
        assert manifest['data_release_id']==receipt['data_release_id']
        layouts.append({'window':window,'layout_sha256':sha256(run/'feature_layout.json'),
                        'in_static':'primary_risk_set' in layout['static_columns'],
                        'mask_in_static':'missing__primary_risk_set' in layout['mask_static_columns']})
        assert layouts[-1]['in_static'] and layouts[-1]['mask_in_static']
        paths=[('TRAIN',f'train/{window}/V0/train.parquet'),
               ('VALIDATION',f'evaluation/{window}/V0/validation.parquet')]
        paths += [(f'TEST_P{i}',f'evaluation/{window}/V0/test_P{i}.parquet') for i in range(1,5)]
        for split,rel in paths:
            path=DATA/rel
            actual=sha256(path)
            assert actual==hashes[rel], f'Input hash differs from upload receipt: {rel}'
            t=pq.read_table(path,columns=['primary_risk_set','missing__primary_risk_set'])
            a=profile(t,'primary_risk_set'); b=profile(t,'missing__primary_risk_set')
            records.append({'window':window,'split':split,'source':rel,'sha256':actual,
                            'primary_risk_set':a,'missing_mask':b})
            print(window,split,'rows',a['rows'],'value',a['values'],'mask',b['values'],flush=True)
    source=json.loads(SOURCE_SCAN.read_text(encoding='utf-8'))
    source_profiles=[x for x in source['static_profiles'] if x['column']=='primary_risk_set']
    assert len(source_profiles)==5
    source_constant=all(x['nulls']==0 and x['values_if_small']==['1'] for x in source_profiles)
    input_constant=all(x['primary_risk_set']['nulls']==0 and x['primary_risk_set']['values']==[0.0]
                       and x['missing_mask']['nulls']==0 and x['missing_mask']['values']==[0] for x in records)
    result={'release_id':'CQ_V2_2','data_release_id':receipt['data_release_id'],
      'manifest_sha256':manifest_hash,'source_scan_path':str(SOURCE_SCAN),'source_profiles':source_profiles,
      'source_constant_one':source_constant,'v0_input_constant_zero':input_constant,
      'scope':'3 windows x TRAIN, VALIDATION, TEST P1-P4; V0 only',
      'layouts':layouts,'files':records}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('AUDIT_COMPLETE source_constant_one=',source_constant,'v0_input_constant_zero=',input_constant,flush=True)
    if not(source_constant and input_constant): raise SystemExit('Risk set constant check failed')


if __name__=='__main__': main()
