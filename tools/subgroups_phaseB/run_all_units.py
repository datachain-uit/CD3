"""Run the 36 units of phase B (CQ and LO x RNN, LSTM, GRU, BILSTM, PATCHTST, MANTIS_V2 x seeds 42, 43, 44) with a few parallel workers; resumable (units whose summary.json is PASS* are skipped)."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import WORK

HERE = Path(__file__).resolve().parent
OUTD = Path(WORK) / 'phaseB' / 'units'
workers = int(sys.argv[1]) if len(sys.argv) > 1 else 3
units = [(t, m, s) for s in (42, 43, 44) for t in ('CQ', 'LO') for m in ('RNN', 'LSTM', 'GRU', 'BILSTM', 'PATCHTST', 'MANTIS_V2')]
units.sort(key=lambda u: (u != ('CQ', 'RNN', 42),))     # the pilot unit first


def done(u):
    f = OUTD / f'{u[0]}_{u[1]}_seed{u[2]}_subgroups_20261121' / 'summary.json'
    if not f.exists():
        return False
    try:
        return json.loads(f.read_text(encoding='utf-8')).get('status', '').startswith('PASS')
    except Exception:
        return False


STOP = []   # set when a builder failure (rc 5) happens: the cause is probably common to all units, so no further unit is started


def run(u):
    if done(u):
        return u, 'skip'
    if STOP:
        return u, 'not started (batch stopped after a builder failure)'
    r = subprocess.run([sys.executable, str(HERE / 'run_unit.py'), *map(str, u)], capture_output=True, text=True)
    if r.returncode == 5:
        STOP.append(u)
    return u, r.returncode


with ThreadPoolExecutor(workers) as ex:
    for u, rc in ex.map(run, units):
        print(u, rc, flush=True)
