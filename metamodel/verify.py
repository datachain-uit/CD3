# -*- coding: utf-8 -*-
"""Reproduction checks on a delivered run directory (0.3.1).

``bootstrap_rows_from_run`` recomputes, from the stored per-group outcomes (mm_recommendations), the paired cluster-bootstrap rows of
H1 to H4 for the four unit roles of the registered table and compares them with the stored mm_hypotheses. Nothing is fitted. The
check exists because the enumeration of the clusters is part of a bootstrap result: with the explicit order of first appearance
(metrics.clusters_by_first_appearance) the rows of the runs of record are reproduced under any pandas version.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from . import contracts as C
from . import metrics as M

_PAIRS = (("H1", "L3-FS3", "B3", "regret"), ("H2", "L3-FS3", "L3-FS2", "regret"), ("H3", "L3-FS3", "B2", "harm"), ("H4", "L3-FS4", "L3-FS3", "regret"))


def _units(rec: pd.DataFrame, protocol: str, strategy: str, tasks: List[str]) -> Dict[str, pd.DataFrame]:
    """task scope -> outcomes of ``strategy`` on ``protocol``, rows in stored order; the joint unit as experiment.evaluation_units builds it."""
    sub = rec[(rec["protocol"] == protocol) & (rec["strategy"] == strategy)]
    if sub.empty:
        return {}
    joint = "+".join(tasks)
    folds = list(pd.unique(sub["fold_id"]))
    out: Dict[str, pd.DataFrame] = {}
    if all(":" in f and f.split(":", 1)[0] in tasks for f in folds):        # one fold per task (E1_SCOPE_PER_TASK)
        for t in tasks:
            part = sub[sub["fold_id"].astype(str).str.startswith(t + ":")]
            if len(part):
                out[t] = part.reset_index(drop=True)
        if len(out) == len(tasks):
            out[joint] = pd.concat([out[t] for t in tasks], ignore_index=True)
    else:                                                                    # one fold for every task (pooled scope)
        out[joint] = sub.reset_index(drop=True)
        if len(tasks) > 1:
            for t in tasks:
                part = sub[sub["task"].astype(str) == t]
                if len(part):
                    out[t] = part.reset_index(drop=True)
    return out


def bootstrap_rows_from_run(run_dir: Path) -> pd.DataFrame:
    """Recomputed rows of H1-H4 (estimate, limits, p, clusters) next to the stored ones, one row per (analysis_role, task_scope, hypothesis)."""
    run_dir = Path(run_dir)
    cfg = json.loads((run_dir / "mm_config.json").read_text(encoding="utf-8"))
    rec = pd.read_parquet(run_dir / "mm_recommendations.parquet")
    hyp = pd.read_parquet(run_dir / "mm_hypotheses.parquet")
    fields, b = list(cfg.get("cluster_fields", C.CLUSTER_FIELDS)), int(cfg.get("bootstrap_b", C.BOOTSTRAP_B))
    tasks = sorted(rec["task"].astype(str).unique())
    joint = "+".join(tasks)
    rows: List[Dict[str, Any]] = []
    for hyp_id, sa, sb, col in _PAIRS:
        ua = {p: _units(rec, p, sa, tasks) for p in (C.PRIMARY_PROTOCOL, C.REPLICATION_PROTOCOL)}
        ub = {p: _units(rec, p, sb, tasks) for p in (C.PRIMARY_PROTOCOL, C.REPLICATION_PROTOCOL)}
        plan = [(C.ROLE_PRIMARY, C.PRIMARY_PROTOCOL, joint)] + [(C.ROLE_PER_TASK, C.PRIMARY_PROTOCOL, t) for t in tasks if len(tasks) > 1] \
            + [(C.ROLE_REPLICATION, C.REPLICATION_PROTOCOL, joint), (C.ROLE_POOLED_2FOLD, None, joint)]
        for role, protocol, scope in plan:
            if protocol is None:
                parts_a = [ua[p].get(joint) for p in (C.REPLICATION_PROTOCOL, C.PRIMARY_PROTOCOL)]
                parts_b = [ub[p].get(joint) for p in (C.REPLICATION_PROTOCOL, C.PRIMARY_PROTOCOL)]
                if any(x is None for x in parts_a + parts_b):
                    continue
                fa, fb = pd.concat(parts_a, ignore_index=True), pd.concat(parts_b, ignore_index=True)
            else:
                fa, fb = ua[protocol].get(scope), ub[protocol].get(scope)
                if fa is None or fb is None:
                    continue
            r = M.paired_cluster_bootstrap(fa, fb, col, cluster_fields=fields, b=b)
            st = hyp[(hyp["analysis_role"] == role) & (hyp["task_scope"] == scope) & (hyp["hypothesis"] == hyp_id)]
            row = {"analysis_role": role, "task_scope": scope, "hypothesis": hyp_id, "comparison": f"{sa} - {sb} ({col})", **{k: r[k] for k in ("estimate", "ci_low", "ci_high", "p_boot", "n_clusters")}}
            if len(st) == 1:
                st = st.iloc[0]
                row.update({f"stored_{k}": float(st[k]) for k in ("estimate", "ci_low", "ci_high", "p_boot")})
                row["stored_n_clusters"] = int(st["n_clusters"])
                row["max_abs_diff"] = float(max(abs(row[k] - row[f"stored_{k}"]) for k in ("estimate", "ci_low", "ci_high", "p_boot")))
            else:
                row["max_abs_diff"] = np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def verify_bootstrap(run_dir: Path, tol: float = 1e-12) -> Dict[str, Any]:
    """PASS when every recomputed row has a stored counterpart and differs from it by at most ``tol``."""
    t = bootstrap_rows_from_run(run_dir)
    matched = t["max_abs_diff"].notna() if len(t) else pd.Series([], dtype=bool)
    worst: Optional[float] = float(t.loc[matched, "max_abs_diff"].max()) if matched.any() else None
    ok = bool(len(t) and matched.all() and worst is not None and worst <= tol and (t["n_clusters"] == t["stored_n_clusters"]).all())
    # "run_dir" is the directory name only: no machine path in a result file
    return {"run_dir": Path(run_dir).name, "rows": int(len(t)), "rows_without_stored_counterpart": int((~matched).sum()) if len(t) else 0,
            "max_abs_diff": worst, "tolerance": tol, "pandas": pd.__version__, "numpy": np.__version__, "verdict": "PASS" if ok else "FAIL", "table": t}
