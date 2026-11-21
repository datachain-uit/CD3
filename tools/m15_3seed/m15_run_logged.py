"""Progress logging around `python -m metamodel.cli run ...` WITHOUT touching the metamodel code (results are unchanged).

usage (replaces `python -m metamodel.cli`):  python m15_run_logged.py run --meta ... --out ... [same arguments]

It wraps metamodel.experiment._learner_cell and _negative_control, prints one line when a cell starts and ends (learner, feature set,
protocol, fold, seconds), keeps a counter done/total, and prints a heartbeat every 5 minutes. The total number of learner cells is
computed up front with the same prepare_frame / make_folds calls the run itself makes (cheap), so the log shows a real percentage.
Log lines go to stdout, flushed; metamodel's own output is untouched.
"""
import functools
import sys
import threading
import time

import metamodel.experiment as E
import metamodel.protocols as P

T0 = time.time()
STATE = {'done': 0, 'total': None, 'current': '-', 'last_cell_s': None}
LOCK = threading.Lock()


def log(msg):
    el = time.time() - T0
    print(f'[{el / 3600:6.2f} h] {msg}', flush=True)


def _arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def _multi(name):
    a = sys.argv
    if name not in a:
        return []
    out = []
    for x in a[a.index(name) + 1:]:
        if x.startswith('--'):
            break
        out.append(x)
    return out


def count_total():
    """number of learner cells the run will execute: for every non-empty (protocol, fold): learners x feature sets + extra learners"""
    import pandas as pd
    cfg = E.MMConfig(meta_release_id='COUNT', objective=_arg('--objective', E.C.DEFAULT_OBJECTIVE), table=_arg('--table', 'seed_agg'),
                     protocols=tuple(_multi('--protocols') or ['E1-A', 'E1-B']), learners=tuple(_multi('--learners') or ['L1', 'L2', 'L3', 'L4']),
                     extra_learners=tuple(_multi('--extra-learners') if '--extra-learners' in sys.argv else ['L5', 'L6']))
    meta = pd.read_parquet(_arg('--meta')) if _arg('--meta').endswith('.parquet') else pd.read_csv(_arg('--meta'))
    df, _ = E.prepare_frame(meta, cfg)
    grid = len(cfg.learners) * len(cfg.feature_sets) + len(cfg.extra_learners)
    total = 0
    detail = []
    for protocol in cfg.protocols:
        try:
            folds = P.make_folds(df, protocol)
        except ValueError as exc:
            detail.append(f'{protocol}: skipped ({exc})')
            continue
        n = sum(1 for f in folds if len(df[f.train]) and len(df[f.test]))
        total += n * grid
        detail.append(f'{protocol}: {n} folds x {grid} cells')
    return total, detail


_orig_cell, _orig_neg = E._learner_cell, E._negative_control


@functools.wraps(_orig_cell)
def cell(train, test, inner, df, learner, fs, *a, **k):
    t = time.time()
    with LOCK:
        STATE['current'] = f'{learner}-{fs}'
        i = STATE['done'] + 1
    log(f'cell {i}/{STATE["total"]} start {learner}-{fs} (train {len(train)} rows, test {len(test)} rows)')
    out = _orig_cell(train, test, inner, df, learner, fs, *a, **k)
    with LOCK:
        STATE['done'] += 1
        STATE['last_cell_s'] = time.time() - t
        done = STATE['done']
    log(f'cell {done}/{STATE["total"]} done {learner}-{fs} in {time.time() - t:.0f} s')
    return out


@functools.wraps(_orig_neg)
def neg(*a, **k):
    t = time.time()
    log('negative control start')
    out = _orig_neg(*a, **k)
    log(f'negative control done in {time.time() - t:.0f} s')
    return out


def heartbeat():
    while True:
        time.sleep(300)
        d, tot = STATE['done'], STATE['total']
        pct = f'{100 * d / tot:.1f}%' if tot else '?'
        log(f'heartbeat: {d}/{tot} cells ({pct}), current {STATE["current"]}, last cell {STATE["last_cell_s"]}')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'run':
        total, detail = count_total()
        STATE['total'] = total
        log(f'planned learner cells: {total} ({"; ".join(detail)})')
        E._learner_cell, E._negative_control = cell, neg
        threading.Thread(target=heartbeat, daemon=True).start()
    from metamodel.cli import main
    rc = main(sys.argv[1:])
    log(f'finished rc={rc}, {STATE["done"]}/{STATE["total"]} cells, total {time.time() - T0:.0f} s')
    sys.exit(rc)
