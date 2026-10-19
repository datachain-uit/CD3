"""Stage small verified CQ external run facts without moving full artifacts."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
base = root/'CQ/resuilt/cq_recurrent_batch2048_seed42_20261019'
dest = root/'CQ/resuilt/cq_recurrent_batch2048_slice_r2_20261019/artifacts'
sources = [root/'CQ/resuilt/cq_lstm_batch2048_full_20261018/lstm', base/'gru', base/'bilstm']
if dest.exists(): raise FileExistsError(f'Refusing to overwrite {dest}')
for source in sources:
    for contract in source.rglob('metadata_contract.json'):
        target = dest/source.name/contract.parent.relative_to(source)
        target.mkdir(parents=True,exist_ok=False)
        for name in ('metadata_contract.json','run_manifest.json','train_history.parquet','metrics_overall.parquet'):
            shutil.copy2(contract.parent/name,target/name)
print('contracts',len(list(dest.rglob('metadata_contract.json'))),'artifact_root',dest)
