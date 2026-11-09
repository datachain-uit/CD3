"""Build reusable, prefix-safe BF16 MOMENT test caches after training."""
import hashlib,json,os,shutil,time
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch
from model.data import FeatureLayout,fit_layout,transform_frame
from model.architectures import prepare_moment_snapshot,SharedPhaseMomentClassifier

ROOT=Path(os.environ.get('MOMENT_ROOT','/workspace/CD3/moment_v1_20261105'))
CLASSES=('warning','average','good')
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    if not torch.cuda.is_available():raise RuntimeError('CUDA GPU required')
    device=torch.device('cuda');snapshot=prepare_moment_snapshot('moment_small',cache_dir=str(ROOT/'model_cache/huggingface'))
    for window in ('w1','w2','w3'):
        inp=ROOT/'input'/window
        train=next(pq.ParquetFile(inp/'model_inputs/train.parquet').iter_batches(batch_size=8)).to_pandas()
        layout=fit_layout(train,task='CQ',phase_id='P4',use_masks=True)
        x,s,_,_=transform_frame(train.iloc[:8],layout,classes=CLASSES,use_masks=True)
        del train
        model=SharedPhaseMomentClassifier(x.shape[2],s.shape[1],len(CLASSES),variant='moment_small',resolved_snapshot=snapshot['snapshot'],backbone_batch_rows=1024).to(device)
        # Head only supplies numerical verification; the reusable cache does
        # not depend on or contain fitted head predictions.
        model.eval()
        for index,phase in enumerate(('P1','P2','P3','P4'),1):
            path=inp/'test'/f'test_{phase}.parquet';frame=pd.read_parquet(path)
            prefix=FeatureLayout(layout.task,phase,layout.dynamic_bases,layout.static_columns,
                                 layout.mask_dynamic_columns,layout.mask_static_columns,layout.mask_phase_bases)
            dynamic,static,_,labels=transform_frame(frame,prefix,classes=CLASSES,use_masks=True)
            identity={'window':window.upper(),'phase':phase,'test_input_sha256':sha(path),'layout':prefix.as_dict(),
                      'backbone_revision':snapshot['resolved_revision'],'torch_version':torch.__version__,
                      'precision':'BF16','storage':'sharded_npz_float16_embedding_float32_stats_v1',
                      'row_alignment':'immutable_test_parquet_row_order','shard_rows':16384}
            key=hashlib.sha256(json.dumps(identity,sort_keys=True,default=str).encode()).hexdigest()
            directory=ROOT/'results'/'test_cache'/window/phase/key;directory.mkdir(parents=True,exist_ok=True)
            existing=directory/'identity.json'
            if existing.exists() and json.loads(existing.read_text())!=json.loads(json.dumps(identity,default=str)):
                raise RuntimeError('Test cache identity mismatch')
            existing.write_text(json.dumps(identity,indent=2,default=str))
            for offset in range(0,len(labels),16384):
                end=min(offset+16384,len(labels));shard=directory/f'{offset:09d}.npz';marker=directory/f'{offset:09d}.json'
                if marker.exists():
                    record=json.loads(marker.read_text())
                    if not shard.is_file() or sha(shard)!=record['sha256'] or record['rows']!=end-offset:
                        raise RuntimeError(f'Test cache mismatch: {shard}')
                    continue
                embeddings=[];stats=[]
                if shutil.disk_usage(directory).free < 512*1024*1024:
                    raise RuntimeError('Less than 512 MiB free; stop before writing cache shard')
                with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
                    for i in range(offset,end,1024):
                        dx=torch.as_tensor(dynamic[i:min(i+1024,end)],device=device)
                        emb,st=model._embedding(dx[:,:index])
                        if not torch.isfinite(emb).all() or torch.any(emb.abs()>65504):raise ValueError('Nonfinite/out-of-range embedding')
                        embeddings.append(emb.half().cpu().numpy());stats.append(st.float().cpu().numpy())
                temporary=directory/f'{offset:09d}.tmp.npz'
                np.savez_compressed(temporary,embedding=np.concatenate(embeddings),statistics=np.concatenate(stats),
                                    static=static[offset:end].astype(np.float32),labels=labels[offset:end])
                os.replace(temporary,shard)
                marker.write_text(json.dumps({'start':offset,'rows':end-offset,'sha256':sha(shard),'bytes':shard.stat().st_size}))
            # Compare cached and direct logits in eval mode before publishing.
            n=min(64,len(labels));dx=torch.as_tensor(dynamic[:n],device=device);sx=torch.as_tensor(static[:n],device=device)
            with np.load(directory/'000000000.npz',allow_pickle=False) as saved:
                saved_features=torch.as_tensor(np.concatenate((saved['embedding'][:n].astype(np.float32),saved['statistics'][:n]),axis=1),device=device)
            with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
                direct=model(dx,sx)[:,-1].float();cached=model.head(torch.cat((saved_features,sx),dim=1)).float()
            diff=float((direct-cached).abs().max());disagreements=int((direct.argmax(-1)!=cached.argmax(-1)).sum())
            if not torch.allclose(direct,cached,atol=1e-2,rtol=1e-2) or disagreements:raise ValueError(f'Test cache parity failed {window}/{phase}: {diff}, {disagreements}')
            (directory/'CACHE_VERIFIED').write_text(json.dumps({'sample_rows':n,'max_logit_difference':diff,'prediction_disagreements':disagreements}))
            print(json.dumps({'event':'test_cache_verified','window':window,'phase':phase,'rows':len(labels),'identity_sha256':key}),flush=True)
            del frame,dynamic,static,labels
    (ROOT/'TEST_CACHE_COMPLETE').write_text('verified\n')
    print('ALL V1 TEST CACHES VERIFIED',flush=True)
if __name__=='__main__':main()
