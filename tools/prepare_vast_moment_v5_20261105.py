"""Create isolated Vast versions of the CQ V5 sharded experiments."""
from pathlib import Path

out=Path('upload_staging/vast_moment_v5_20261105');out.mkdir(parents=True,exist_ok=True)
for window in ('w1','w2','w3'):
    text=Path(f'modal_jobs/moment_v5_{window}_sharded_20261105.py').read_text(encoding='utf8')
    start=text.index("app = modal.App(")
    end=text.index('def run_one_epoch():',start)
    text=text[:start]+'''class LocalVolume:
    def commit(self): pass
volume=LocalVolume()

'''+text[end:]
    text=text.replace('import modal\n','')
    marker=text.index('    root = Path(')
    marker_end=text.index('\n',marker)
    text=text[:marker]+f"    root = Path('/workspace/CD3/moment_v5_20261105/input/{window}')"+text[marker_end:]
    text=text.replace("'/data/model_cache/huggingface'", "'/workspace/CD3/moment_v5_20261105/model_cache/huggingface'")
    text=text.replace(f"/data/meta_release=imputation-v1/L3_meta/diagnostics/cq_moment_v5_{window}_sharded_20261105",f"/workspace/CD3/moment_v5_20261105/results/{window}")
    text=text.replace(f"/data/diagnostics/cq_moment_v5_{window}_test_20261105",f"/workspace/CD3/moment_v5_20261105/input/{window}/test")
    text=text[:text.index('@app.local_entrypoint()')]+"if __name__=='__main__': print(json.dumps(run_one_epoch(),indent=2,default=str))\n"
    (out/f'run_{window}.py').write_text(text,encoding='utf8',newline='\n')
