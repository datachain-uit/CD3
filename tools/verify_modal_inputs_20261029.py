"""Compute remote input MD5s and locate S2 lineage, without modifying Modal."""
import hashlib
import json
from pathlib import Path
import modal

app = modal.App('verify-inputs-20261029')
volume = modal.Volume.from_name('tempo-data-v1', create_if_missing=False)

@app.function(image=modal.Image.debian_slim(python_version='3.12'), volumes={'/data': volume}, cpu=2, memory=2048, timeout=7200)
def inspect(entries):
    result=[]
    for entry in entries:
        p=Path('/data')/entry['remote_path']
        row={'window':entry['window_id'],'pipeline':entry['pipeline_id'],'remote_path':entry['remote_path']}
        try:
            h=hashlib.md5()
            with p.open('rb') as f:
                for block in iter(lambda:f.read(8*1024*1024), b''): h.update(block)
            row.update(md5=h.hexdigest(),size=p.stat().st_size)
            if p.name=='balanced_train.parquet':
                for n in ('synthetic_ledger.parquet','run_manifest.json'):
                    q=p.parent/n
                    row[n]={'exists':q.is_file(),'size':q.stat().st_size if q.is_file() else None,'remote_path':str(q).removeprefix('/data/')}
        except OSError as e: row['error']=str(e)
        result.append(row)
    return result

@app.local_entrypoint()
def main(task: str='CQ'):
    name='CQ_V2_2_clean_grain_seed42' if task=='CQ' else 'LO_V3_1_clean_grain_seed42'
    manifest=json.loads((Path('downloads/vastai')/name/'download_manifest.json').read_text(encoding='utf-8'))
    entries=[x for x in manifest['files'] if x.get('kind')=='train']
    result=inspect.remote(entries)
    dest=Path('downloads')/f'modal_input_hashes_{task}_20261029.json'
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'task':task,'entries':len(result),'errors':sum('error' in x for x in result),'output':str(dest)}))
