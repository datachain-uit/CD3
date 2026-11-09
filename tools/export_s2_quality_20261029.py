"""Export quality/resource facts tied to exact balanced artifacts, read-only."""
import base64
import hashlib
import json
from pathlib import Path
import modal

app=modal.App('export-s2-quality-20261029')
volume=modal.Volume.from_name('tempo-data-v1',create_if_missing=False)

@app.function(image=modal.Image.debian_slim(python_version='3.12'),volumes={'/data':volume},cpu=1,memory=1024,timeout=1200)
def inspect(entries):
    output=[]
    for e in entries:
        parent=(Path('/data')/e['remote_path']).parent
        m=json.loads((parent/'run_manifest.json').read_text(encoding='utf-8'))
        plan=(m.get('algorithm_config') or {}).get('sampling_plan')
        item={'window':e['window_id'],'pipeline':e['pipeline_id'],'run_id':m.get('run_id'),'attempt_id':m.get('attempt_id'),'sampling_plan':plan,'facts':{}}
        for kind,key in [('augmentation_quality','augmentation_quality_path'),('resource_usage','resource_usage_path')]:
            path=Path(m[key]) if m.get(key) else None
            if path and path.is_file():
                data=path.read_bytes()
                item['facts'][kind]={'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'data':base64.b64encode(data).decode('ascii')}
            else: item['facts'][kind]={'missing':True,'path':str(path) if path else None}
        output.append(item)
    return output

@app.local_entrypoint()
def main(task:str='CQ'):
    name='CQ_V2_2_clean_grain_seed42' if task=='CQ' else 'LO_V3_1_clean_grain_seed42'
    manifest=json.loads((Path('downloads/vastai')/name/'download_manifest.json').read_text(encoding='utf-8'))
    entries=[e for e in manifest['files'] if e.get('kind')=='train' and e['remote_path'].endswith('/balanced_train.parquet')]
    rows=inspect.remote(entries)
    root=Path('downloads')/'s2_facts_20261029'/task
    for row in rows:
        for kind,obj in row['facts'].items():
            if 'data' not in obj: continue
            data=base64.b64decode(obj.pop('data'))
            if hashlib.sha256(data).hexdigest()!=obj['sha256']: raise RuntimeError('Fact checksum mismatch')
            target=root/kind/row['window']/row['pipeline']/'part-00000.parquet'
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
    (root/'coverage.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'task':task,'runs':len(rows),'sampling_plans':sum(bool(x['sampling_plan']) for x in rows),'quality':sum('sha256' in x['facts']['augmentation_quality'] for x in rows),'resource':sum('sha256' in x['facts']['resource_usage'] for x in rows)}))
