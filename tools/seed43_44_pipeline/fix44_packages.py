"""Seed-44 facts packages on Drive: fix README title (seed), duplicate '## r2', probe_seed (= seed of the reference probe fit, 42; s_leak is copied, not refitted), record the builder commit.
Each Drive folder is first copied server-side to the superseded folder (the verified version stays), then the fixed files overwrite the originals; rclone check at the end.
usage: fix44_packages.py BUILDER_COMMIT [--only SUBSTRING]"""
from tempo_paths import A44
import hashlib, json, re, shutil, subprocess, sys
from pathlib import Path
import pandas as pd
COMMIT = sys.argv[1]; ONLY = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else ''
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
FE = 'L2_facts/fact_exports'
PK = {'CQ': ['cq_f1_recurrent_v0_v16_full_facts_seed44_20261118', 'cq_patchtst_v0_v16_full_facts_seed44_20261119', 'cq_mantis_v2_v0_v16_full_facts_seed44_20261119'],
      'LO': ['lo_f1_recurrent_v0_v16_full_facts_seed44_20261118', 'lo_patchtst_v0_v16_full_facts_seed44_20261119', 'lo_mantis_v2_v0_v16_full_facts_seed44_20261119']}
WORK = Path(f'{A44}/fix'); WORK.mkdir(parents=True, exist_ok=True)
NOTE = ('\n## r2 fix 2026-11-19\n\nThe title of this README now names seed 44. `probe_seed` in `sanity_components` is 42, the seed of the reference probe fit: `s_leak` of this package is copied from the reference table '
        '(audit mode COPY_REFERENCE, no probe refit at seed 44), so no probe was fitted with seed 44. The numbers of the package are unchanged. Builder: tools/build_facts_package_mantis_lo_20261109.py at commit `' + COMMIT + '`.\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(c, **k): return subprocess.run(RC + c, capture_output=True, text=True, **k)
for task, names in PK.items():
    for name in names:
        if ONLY and ONLY not in name: continue
        src = f'gdrive:{task}/{FE}/{name}'; sup = f'gdrive:{task}/{FE}_superseded_20261119/{name}'; loc = WORK / name
        if (WORK / (name + '.FIXED')).exists(): print(name, 'already fixed'); continue
        shutil.rmtree(loc, ignore_errors=True)
        r = run(['copy', src, str(loc), '--transfers', '4', '-q']); assert r.returncode == 0, r.stderr
        if not run(['lsf', sup]).stdout.strip():
            r = run(['copy', src, sup, '-q']); assert r.returncode == 0, r.stderr
        dirs = sorted({p.parent for p in loc.rglob('summary.json') if 'cohort_audit' not in p.parts})
        for d in dirs:
            rd = d / 'README.md'; t = rd.read_text(encoding='utf-8').split('\n')
            t[0] = re.sub(r'seed 4[23]', 'seed 44', t[0]); txt = '\n'.join(t)
            parts = txt.split('\n## r2\n')
            if len(parts) > 2: txt = parts[0] + '\n## r2\n' + parts[1]          # keep the first r2 section only
            if 'r2 fix 2026-11-19' not in txt: txt = txt.rstrip('\n') + '\n' + NOTE
            rd.write_text(txt, encoding='utf-8', newline='\n')
            sc = pd.read_csv(d / 'sanity_components.csv', low_memory=False)
            if 'probe_seed' in sc.columns:
                sc['probe_seed'] = 42
                sc.to_parquet(d / 'sanity_components.parquet', index=False); sc.to_csv(d / 'sanity_components.csv', index=False, lineterminator='\n')
            s = json.loads((d / 'summary.json').read_text(encoding='utf-8'))
            s['builder_commit'] = COMMIT; s['probe_seed'] = 42
            s.setdefault('r2_changes', []).append('2026-11-19 fix: README title names seed 44; probe_seed = 42 (seed of the reference probe fit; s_leak copied, not refitted); builder commit recorded')
            (d / 'summary.json').write_text(json.dumps(s, indent=2) + '\n', encoding='utf-8')
            files = sorted(p for p in d.rglob('*') if p.is_file() and p.name != 'sha256sums.txt')
            (d / 'sha256sums.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(d).as_posix()}\n' for p in files), encoding='utf-8', newline='\n')
        r = run(['copy', str(loc), src, '--transfers', '4', '-q']); assert r.returncode == 0, r.stderr
        ck = run(['check', str(loc), src, '--one-way']); print(name, 'dirs fixed', len(dirs), 'check rc', ck.returncode, (ck.stderr or ck.stdout)[-120:].replace('\n', ' '), flush=True)
        if ck.returncode == 0: (WORK / (name + '.FIXED')).write_text('ok'); shutil.rmtree(loc)
