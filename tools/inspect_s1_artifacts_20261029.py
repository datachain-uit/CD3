"""Read-only S1 manifest/preprocessor/input inventory for an exact release."""
import json
from pathlib import Path
import modal
app=modal.App('inspect-s1-artifacts-20261029')
volume=modal.Volume.from_name('tempo-data-v1',create_if_missing=False)
@app.function(image=modal.Image.debian_slim(python_version='3.12'),volumes={'/data':volume},cpu=1,memory=1024,timeout=1200)
def inspect(task:str):
    regimes={'CQ':'CQ_RAW_EARLY','LO':'LO_FULL_EARLY'}
    root=Path('/data/meta_release=imputation-v1/L1_runs')/f'task={task}'/f"feature_regime={regimes[task]}"
    result=[]
    for window in ('W1','W2','W3'):
      for pipe in ('V0','V1','V5','V9','V13'):
        base=root/f'window_id={window}'/f'pipeline_id={pipe}'/'model_name=IMPUTATION_ONLY'/'seed=20260922'
        candidates=[]
        for mp in base.glob('run_id=*/attempt_id=*/run_manifest.json'):
          m=json.loads(mp.read_text(encoding='utf-8'))
          if m.get('run_status')=='SUCCESS' and m.get('release_id') in (('CQ_V2_2',) if task=='CQ' else ('LO_V3_1',)):
            candidates.append((mp,m))
        if not candidates:
          result.append({'window':window,'pipeline':pipe,'status':'NO_SUCCESS_RELEASE_MANIFEST'}); continue
        mp,m=max(candidates,key=lambda x:x[0].stat().st_mtime)
        d=mp.parent
        names={x.name for x in (d/'model_inputs').glob('*.parquet')}
        result.append({'window':window,'pipeline':pipe,'status':m.get('run_status'),'release_id':m.get('release_id'),'data_release_id':m.get('data_release_id'),'run_id':m.get('run_id'),'attempt_id':m.get('attempt_id'),'manifest':True,'preprocessor':(d/'fitted_preprocessors'/'fitted_pipeline.joblib').is_file(),'inputs':sorted(names),'required_inputs':all(x in names for x in ('train.parquet','validation.parquet','test_P1.parquet','test_P2.parquet','test_P3.parquet','test_P4.parquet')),'manifest_path':str(mp)})
    return result
@app.local_entrypoint()
def main(task:str='CQ'):
    rows=inspect.remote(task)
    p=Path('downloads')/f's1_artifacts_{task}_20261029.json'
    p.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'task':task,'expected':15,'complete':sum(x.get('preprocessor') and x.get('required_inputs') for x in rows),'missing':[x for x in rows if not(x.get('preprocessor') and x.get('required_inputs'))],'output':str(p)}))
