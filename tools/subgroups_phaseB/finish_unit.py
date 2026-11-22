"""Finish a unit whose builder passed but whose run_unit process stopped before the upload (checksums, upload, temp cleanup). usage: finish_unit.py CQ RNN 42"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import WORK

t, m, s = sys.argv[1], sys.argv[2], sys.argv[3]
unit = f'{t}_{m}_seed{s}'
out = Path(WORK) / 'phaseB' / 'units' / f'{unit}_subgroups_20261121'
qa = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
assert qa['status'].startswith('PASS'), qa['status']
assert (out / 'README.md').exists()
files = [p for p in sorted(out.iterdir()) if p.name != 'sha256sums.txt']
(out / 'sha256sums.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in files), encoding='utf-8')
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
dest = f'gdrive:cross_task_meta/work_in_progress/subgroups_phaseB_20261121/{out.name}'
subprocess.run(RC + ['copy', str(out), dest, '-q'], capture_output=True)
chk = subprocess.run(RC + ['check', str(out), dest, '--one-way'], capture_output=True, text=True)
line = f'{time.strftime("%F %T")} [{unit}] upload ' + ('OK (finish_unit)' if chk.returncode == 0 else 'CHECK FAILED ' + chk.stderr[-200:])
with (Path(WORK) / 'phaseB' / 'units' / 'run_units.log').open('a', encoding='utf-8') as h:
    h.write(line + '\n')
print(line)
if chk.returncode == 0:
    shutil.rmtree(Path(sys.argv[4] if len(sys.argv) > 4 else f'{WORK}/phaseB_tmp') / unit, ignore_errors=True)
