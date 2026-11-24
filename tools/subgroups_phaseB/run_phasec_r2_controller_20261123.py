import hashlib,json,os,shlex,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path

root=Path(os.environ.get('TEMPO_REPO_ROOT', Path(__file__).resolve().parents[2])); pkg=Path(os.environ.get('TEMPO_METAMODEL_HANDOFF_ROOT', root/'tmp/metamodel_handoff_20261121'))
review=Path(os.environ.get('TEMPO_REVIEW_ROOT', root/'docs/23112026/review_moi_20261123')); spec=review/'phaseC_frozen_configurations_r2.json'
out=root/'CQ/resuilt/mm_runs_phaseC_r2_20261123'; rel=root/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2'
frozen=json.loads(spec.read_text(encoding='utf8')); rid=frozen['release_id']; meta=rel/'meta_dataset_seed_agg.parquet'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def log(s):
 with (out/'progress.log').open('a',encoding='utf8') as f:f.write(datetime.now(timezone.utc).isoformat()+' '+s+'\n')
if out.exists():raise FileExistsError(out)
assert len(frozen['runs'])==10 and meta.is_file()
tree=review/'_build/handoff_2026-11-21_tree_sha256.txt'; checked=0
for line in tree.read_text(encoding='utf8').splitlines():
 expected,path=line.split('  ',1)
 if path.startswith('metamodel/'):
  if sha(pkg/path)!=expected:raise ValueError('handoff hash mismatch: '+path)
  checked+=1
assert checked>0
env=os.environ.copy()
for x in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','LOKY_MAX_CPU_COUNT'):env[x]='1'
env['PYTHONNOUSERSITE']='1'
common=shlex.split(frozen['common_options'])
for c in frozen['runs']:
 cmd=[sys.executable,'-m','metamodel.cli','run','--meta','x','--out','x','--release-id',rid]+common+shlex.split(c['flags'])+['--digest-only']
 p=subprocess.run(cmd,cwd=pkg,env=env,capture_output=True,text=True,check=True)
 if json.loads(p.stdout)['mm_config_sha256']!=c['mm_config_sha256']:raise ValueError('digest mismatch '+c['name'])
manifest=json.loads((rel/'meta_release_manifest.json').read_text(encoding='utf8'))
assert manifest['meta_release_id']==rid and manifest['n_rows_seed_level']==73440
out.mkdir(parents=True)
(out/'input_sha256.json').write_text(json.dumps({'meta_seed_agg_sha256':sha(meta),'handoff_zip_sha256':sha(Path(os.environ['TEMPO_METAMODEL_HANDOFF_ZIP'])),'frozen_config_sha256':sha(spec),'metamodel_tree_files_verified':checked},indent=2),encoding='utf8')
(out/'frozen_configurations_r2.json').write_bytes(spec.read_bytes())
with (out/'pip_freeze.txt').open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pip','freeze'],stdout=f,check=True)
log('PREFLIGHT PASS: ten approved digests and metamodel tree verified')
def run(pair):
 i,c=pair; name=c['name']; log('START '+name); t=time.monotonic()
 cmd=[sys.executable,str(root/'tools/subgroups_phaseB/run_metamodel_single_core.py'),str(i),'run','--meta',str(meta),'--out',str(out/name),'--release-id',rid]+common+shlex.split(c['flags'])+['--expect-digest',c['mm_config_sha256'],'--progress']
 with (out/(name+'.stdout.log')).open('w',encoding='utf8') as so,(out/(name+'.stderr.log')).open('w',encoding='utf8') as se:
  p=subprocess.run(cmd,cwd=pkg,env=env,stdout=so,stderr=se)
 log(f'END {name} rc={p.returncode} seconds={time.monotonic()-t:.1f}')
 return p.returncode
for label,batch in (('PRIMARY',frozen['runs'][:6]),('VARIANTS',frozen['runs'][6:])):
 log('BATCH START '+label)
 with ThreadPoolExecutor(max_workers=len(batch)) as pool: codes=list(pool.map(run,enumerate(batch)))
 if any(codes):log(f'BATCH FAILED {label} {codes}');raise SystemExit(1)
 log('BATCH PASS '+label)
log('PHASE_C_ALL_COMPLETE; packaging and QA required')
