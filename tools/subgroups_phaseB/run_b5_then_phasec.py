"""Run registered B.5 and then frozen phase C only after all gates pass."""
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
PKG=ROOT/'tmp/metamodel_handoff_20261121'
RID=os.environ.get('TEMPO_5SUBGROUP_RELEASE_ID','CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r1')
if RID not in ('CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r1','CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2'):
    raise ValueError('unregistered release ID')
REV=RID.rsplit('_',1)[-1]
REL=ROOT/'CQ/resuilt'/('meta_release_'+RID)
CHILD=ROOT/'tmp/s0_v5_inputs'/('children_5subgroups_'+REV)
BASE=ROOT/'CQ/resuilt/mm_runs_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026'
B5=ROOT/'CQ/resuilt'/('mm_runs_CQ_LO_5subgroups_'+REV+'_B5_parallel_20261122')
PHASEC=ROOT/'CQ/resuilt/mm_runs_CQ_LO_5subgroups_r1_phaseC_20261122'
B5_ONLY=os.environ.get('TEMPO_B5_ONLY')=='1'
COMMON=['--protocols','E1-A','E1-B','E2','E3','--learners','L1','L2','L3','L4','--extra-learners','L5','L6','--n-trials','50','--learner-seeds','5']
CONFIGS=[('main_cal_time',[]),('sens_v1',['--objective','META_PRIMARY_M3_V1']),('sens_energy',['--accept-energy-estimates']),
         ('sens_conservative',['--conservative']),('obj_perf',['--objective','PAPER_PERF_AXIS']),('obj_macrof1',['--objective','SECONDARY_MACRO_F1'])]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def write_log(path,text):
    with path.open('a',encoding='utf8') as f:f.write(datetime.now(timezone.utc).isoformat()+' '+text+'\n')


def run(name,args,out,log,core=0):
    t=time.monotonic(); write_log(log,'START '+name)
    with (out/f'{name}.stdout.log').open('w',encoding='utf8') as stdout,(out/f'{name}.stderr.log').open('w',encoding='utf8') as stderr:
        p=subprocess.run([sys.executable,str(ROOT/'tools/subgroups_phaseB/run_metamodel_single_core.py'),str(core),'run','--meta',str(REL/'meta_dataset_seed_agg.parquet'),'--out',str(out/name),'--release-id',RID]+COMMON+args,cwd=PKG,stdout=stdout,stderr=stderr)
    write_log(log,f'END {name} exit={p.returncode} seconds={time.monotonic()-t:.3f}')
    if p.returncode: raise RuntimeError(f'{name} exited {p.returncode}; see logs')


def main():
    if B5.exists() or (not B5_ONLY and PHASEC.exists()): raise FileExistsError('result folder already exists; refusing overwrite')
    m=json.loads((REL/'meta_release_manifest.json').read_text(encoding='utf8'))
    if m['meta_release_id']!=RID or m['n_rows_seed_level']!=73440: raise ValueError('combined release identity or row gate failed')
    for task in ('CQ','LO'):
        c=json.loads((CHILD/f'{task}_3seed/meta_release_manifest.json').read_text(encoding='utf8'))
        if not c['subgroup_report']['ok'] or not all(c['all_slice_against_reference'][t]['ok'] for t in ('meta_dataset_seed_level','meta_dataset_seed_agg')):
            raise ValueError(f'{task} subgroup/all parity gate failed')
    configs=None
    if not B5_ONLY:
        configs=json.loads((PKG/'phaseC_frozen_configurations.json').read_text(encoding='utf8'))
        if configs['release_id']!=RID or len(configs['runs'])!=10: raise ValueError('frozen phase C config mismatch')
        for c in configs['runs']:
            cmd=[sys.executable,'-m','metamodel.cli','run','--meta','x','--out','x','--release-id',RID]+COMMON+shlex.split(c['flags'])+['--digest-only']
            p=subprocess.run(cmd,cwd=PKG,capture_output=True,text=True,encoding='utf8')
            if p.returncode or json.loads(p.stdout)['mm_config_sha256']!=c['mm_config_sha256']:
                raise ValueError(f'digest preflight failed for {c["name"]}: {p.stderr}')
    B5.mkdir(parents=True); log=B5/'progress.log'
    handoff=Path(os.environ.get('TEMPO_HANDOFF_ZIP', ROOT/'tmp/metamodel_handoff_2026-11-21.zip'))
    (B5/'input_sha256.json').write_text(json.dumps({'release_seed_agg_sha256':sha(REL/'meta_dataset_seed_agg.parquet'),'handoff_sha256':sha(handoff)},indent=2),encoding='utf8')
    with (B5/'pip_freeze.txt').open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pip','freeze'],stdout=f,check=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs=[pool.submit(run,name,flags,B5,log,i) for i,(name,flags) in enumerate(CONFIGS)]
        for job in jobs: job.result()
    with (B5/'comparison.log').open('w',encoding='utf8') as f:
        cmp=subprocess.run([sys.executable,str(PKG/'compare_mm_dirs_r30b.py'),str(BASE),str(B5),'--json',str(B5/'comparison.json')],cwd=PKG,stdout=f,stderr=subprocess.STDOUT)
    rep=json.loads((B5/'comparison.json').read_text(encoding='utf8'))
    if cmp.returncode or rep['tables_different'] or len(rep['configurations_compared'])!=6 or rep['configurations_on_one_side_only']:
        raise RuntimeError('B.5 parity failed; phase C not started')
    write_log(log,'B5 PASS; all six configurations match phase A')
    if B5_ONLY:
        write_log(log,'B5_ONLY_COMPLETE; phase C requires newly approved r2 digests')
        return
    PHASEC.mkdir(parents=True); clog=PHASEC/'progress.log'
    (PHASEC/'frozen_configurations.json').write_text(json.dumps(configs,indent=2)+'\n',encoding='utf8')
    (PHASEC/'input_sha256.json').write_text((B5/'input_sha256.json').read_text(encoding='utf8'),encoding='utf8')
    with (PHASEC/'pip_freeze.txt').open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pip','freeze'],stdout=f,check=True)
    for c in configs['runs']:
        run(c['name'],shlex.split(c['flags'])+['--expect-digest',c['mm_config_sha256'],'--progress'],PHASEC,clog)
    (PHASEC/'README.md').write_text('# Phase C\n\nSix full_* configurations are primary; four var_* configurations are labelled sensitivity variants. All ten use the frozen digests and the gated five-subgroup release.\n',encoding='utf8')
    (PHASEC/'RUN_LOG.md').write_text('# RUN_LOG\n\nSee progress.log for actual UTC start/end and wall time of every run; input_sha256.json identifies input and handoff.\n',encoding='utf8')
    write_log(clog,'PHASE_C_COMPLETE')
    files=sorted(p for p in PHASEC.rglob('*') if p.is_file() and p.name!='sha256sums.txt')
    (PHASEC/'sha256sums.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(PHASEC).as_posix()}\n' for p in files),encoding='utf8')


if __name__=='__main__': main()
