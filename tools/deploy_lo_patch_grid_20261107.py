import hashlib, json, subprocess, sys, tarfile, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST, PORT, V = sys.argv[1:4]
PARENT = 'V1' if V in ('V1','V2','V3','V4') else 'V5' if V in ('V5','V6','V7','V8') else 'V9' if V in ('V9','V10','V11','V12') else 'V13'
TARGET = f'root@{HOST}'
DATA = ROOT/'downloads/vastai/LO_V3_1_clean_grain_seed42'
SALT = ROOT/'downloads/private/lo_grid_prediction_salt'
STATE = ROOT/f'logs/lo_patch_{V}_{PORT}.json'
STATE.parent.mkdir(parents=True, exist_ok=True)
def status(s, **extra):
    STATE.write_text(json.dumps({'status':s,'host':HOST,'port':PORT,'version':V,**extra}, indent=2), encoding='utf8')
def run(args, **kw):
    return subprocess.run(args, check=True, **kw)
ssh = ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=20','-p',PORT,TARGET]
scp = ['scp','-q','-o','BatchMode=yes','-o','ConnectTimeout=20','-P',PORT]
remote = '/workspace/CD3'
try:
    status('PACKING')
    with tempfile.TemporaryDirectory(dir=ROOT/'upload_staging') as td:
        td=Path(td)
        archive=td/'inputs.tar'
        with tarfile.open(archive,'w') as tar:
            tar.add(DATA/'download_manifest.json',arcname='download_manifest.json')
            for w in ('W1','W2','W3'):
                rels = {f'train/{w}/{V}', f'train/{w}/{PARENT}', f'evaluation/{w}/{PARENT}'}
                for rel in sorted(rels):
                    p=DATA/rel
                    if not p.exists(): raise FileNotFoundError(p)
                    tar.add(p,arcname=rel)
        digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
        status('UPLOADING',bytes=archive.stat().st_size,sha256=digest)
        run(ssh+['mkdir -p /workspace/CD3/data/LO_V3_1_clean_grain_seed42 /workspace/CD3/lo_patchtst_seed42_code /workspace/CD3/runs'])
        run(scp+[str(archive),TARGET+':/workspace/CD3/input_new.tar'])
        remotehash=subprocess.check_output(ssh+['sha256sum /workspace/CD3/input_new.tar'],text=True).split()[0]
        if digest!=remotehash: raise RuntimeError('input archive checksum mismatch')
        run(ssh+['tar -xf /workspace/CD3/input_new.tar -C /workspace/CD3/data/LO_V3_1_clean_grain_seed42'])
        salt_hash=hashlib.sha256(SALT.read_bytes()).hexdigest()
        existing=subprocess.run(ssh+['sha256sum /workspace/CD3/lo_static_v2_prediction_salt'],capture_output=True,text=True)
        if existing.returncode==0:
            if existing.stdout.split()[0]!=salt_hash: raise RuntimeError('existing prediction salt differs; refusing to overwrite')
        else:
            run(scp+[str(SALT),TARGET+':/workspace/CD3/lo_static_v2_prediction_salt'])
        code=td/'code.tar'
        with tarfile.open(code,'w') as tar:
            for name in ('model','metrics_core','release_core','augmentation_core','imputation_core'):
                tar.add(ROOT/name,arcname=name,filter=lambda i: None if '__pycache__' in i.name else i)
            for name in ('vastai_train_shared.py','vastai_audit_shared.py','vastai_metadata_contract.py'):
                tar.add(ROOT/'tools'/name,arcname='tools/'+name)
            tar.add(ROOT/'LO/registries.py',arcname='LO/registries.py')
            tar.add(ROOT/'tools/run_lo_patchtst_one_pipeline_20261106.sh',arcname='launch.sh')
        run(scp+[str(code),TARGET+':/workspace/CD3/code_new.tar'])
        run(ssh+['tar -xf /workspace/CD3/code_new.tar -C /workspace/CD3/lo_patchtst_seed42_code'])
        # New instances install dependencies in the background before the training loop.
        wrapper=ROOT/'tools/lo_patch_complete_20261107.sh'
        run(scp+[str(wrapper),TARGET+':/workspace/CD3/lo_patchtst_seed42_code/complete.sh'])
        cmd='nohup bash /workspace/CD3/lo_patchtst_seed42_code/complete.sh '+V+' > /workspace/CD3/lo_patchtst_seed42_code/complete_'+V+'.log 2>&1 < /dev/null &'
        run(ssh+[cmd])
        time.sleep(5)
        run(ssh+['pgrep -af complete.sh'])
        status('LAUNCHED',sha256=digest,parent=PARENT)
except Exception as e:
    status('FAILED',error=str(e)); raise
