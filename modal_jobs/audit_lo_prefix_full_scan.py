"""Read-only, streamed scan of all LO V3.1 TEST-prefix future phase cells."""
import json
from pathlib import Path
import modal

app = modal.App('lo-v31-prefix-full-scan')
volume = modal.Volume.from_name('tempo-data-v1', create_if_missing=False)
image = modal.Image.debian_slim(python_version='3.12').pip_install('pyarrow>=16')

@app.function(image=image, volumes={'/data': volume}, cpu=2, memory=8192, timeout=7200)
def scan():
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    root = Path('/data/input/LO_v3_1/test_prefix_views_v3_1_scored_signal_excluded')
    output = []
    phases = ('P1','P2','P3','P4')
    for index, phase in enumerate(phases):
        files = sorted((root/phase).rglob('*.parquet'))
        if not files:
            raise FileNotFoundError(f'No parquet under {root/phase}')
        first = pq.ParquetFile(files[0]).schema_arrow.names
        future = [c for c in first if not c.startswith('phase_available_') and any(c.endswith('_'+p) for p in phases[index+1:])]
        rows = nonnull = groups = 0
        for path in files:
            pf = pq.ParquetFile(path)
            if pf.schema_arrow.names != first:
                raise ValueError(f'Inconsistent schema: {path}')
            groups += pf.num_row_groups
            rows += pf.metadata.num_rows
            if future:
                for batch in pf.iter_batches(batch_size=8192, columns=future):
                    nonnull += sum(len(col)-int(pc.sum(pc.is_null(col, nan_is_null=True)).as_py()) for col in batch.columns)
        output.append({'phase':phase,'files':len(files),'row_groups':groups,'rows':rows,'future_columns':len(future),'future_cells':rows*len(future),'non_null_future_cells':nonnull,'pass':nonnull==0})
    return {'task':'LO','release':'LO_V3_1','source':str(root),'scope':'all_files_all_row_groups','results':output,'passed':all(x['pass'] for x in output)}

@app.local_entrypoint()
def main():
    print(json.dumps(scan.remote(), indent=2))
