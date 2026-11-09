"""Short, synthetic MantisV2 cost pilot; no project outcomes or model selection."""
from pathlib import Path
import json
import modal
import sys

PKG=Path(__file__).resolve().parents[1]/'docs/06112026/mantis_review/f3_mantis_v0.1.0_2026-11-06/f3_mantis'
if PKG.is_dir(): sys.path.insert(0,str(PKG.parent))
image=(modal.Image.debian_slim(python_version='3.12')
    .pip_install('torch==2.5.1','numpy>=1.26','scikit-learn>=1.5','einops>=0.8,<0.9','huggingface-hub>=0.23','safetensors>=0.4')
    .run_commands('pip install --no-deps mantis-tsfm==1.1.0')
    .add_local_python_source('f3_mantis',copy=True))
app=modal.App('cd3-mantis-v2-synthetic-bench-20261106')

@app.function(image=image,gpu='L4',cpu=4,memory=16384,timeout=1200)
def run_bench(rows:int=512,channels:int=274):
 import subprocess,sys,tempfile,os
 from pathlib import Path
 with tempfile.TemporaryDirectory() as temp:
  p=Path(temp); pin=p/'pin.json'; bench=p/'bench.json'
  subprocess.run([sys.executable,'-m','f3_mantis.cli','pin','--out',str(pin)],check=True)
  info=json.loads(pin.read_text())
  subprocess.run([sys.executable,'-m','f3_mantis.cli','bench','--device','cuda','--rows',str(rows),'--channels',str(channels),'--precision','bf16','--microbatch-sequences','2048','--snapshot',info['snapshot_dir'],'--out',str(bench)],check=True)
  return {'scope':'synthetic_cost_benchmark_only','protocol_deviation':'microbatch 2048 instead of registered 4096, user requested','pin':info,'bench':json.loads(bench.read_text())}

@app.local_entrypoint()
def main(rows:int=512,channels:int=274):
 result=run_bench.remote(rows,channels)
 out=Path('CQ/resuilt/mantis_v2_modal_synthetic_bench_20261106');out.mkdir(parents=True,exist_ok=True)
 (out/'result.json').write_text(json.dumps(result,indent=2,default=str)+'\n',encoding='utf8')
 print(json.dumps(result,indent=2,default=str))
