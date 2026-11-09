"""Read-only inventory of registry and input lineage on a Modal volume."""
import json
from pathlib import Path
import modal
app=modal.App('inspect-l0-20261029')
volume=modal.Volume.from_name('tempo-data-v1',create_if_missing=False)
@app.function(image=modal.Image.debian_slim(python_version='3.12'),volumes={'/data':volume},cpu=1,memory=1024,timeout=600)
def inspect():
    root=Path('/data')
    paths=[root/'meta_release=imputation-v1/L0_registry',root/'input']
    output={}
    for p in paths:
        output[str(p)]=[str(q.relative_to(p)) for q in p.rglob('*') if q.is_file() and ('manifest' in q.name.lower() or 'lineage' in str(q).lower() or 'registry' in str(q).lower())] if p.exists() else None
    return output
@app.local_entrypoint()
def main():
    print(json.dumps(inspect.remote(),ensure_ascii=False))
