#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CD3 - kiểm 48: chạy lại RIÊNG đối chứng âm (MQ08) của mười lần chạy pha C bằng gói metamodel 0.3.1.

Căn cứ: quyết định của tác giả ngày 26/11/2026, Q-48 (b) (registry: quyết định 59). Không fit lại gì ngoài đối chứng; không đọc, không
sửa bảng nào khác; thư mục run đã nghiệm thu chỉ được ĐỌC. Mọi sản phẩm ghi vào thư mục --out (thư mục mới).

Chạy từ thư mục gốc của gói bàn giao (thư mục chứa metamodel/, tempo_fix/ và file này), trong môi trường Python đã chạy pha C:

    python run_negative_control_r2.py check   --runs RUNS --release REL --out OUT
    python run_negative_control_r2.py run     --runs RUNS --release REL --out OUT [--only TÊN ...] [--permutations K] [--parallel N]
    python run_negative_control_r2.py verify  --runs RUNS --out OUT
    python run_negative_control_r2.py posthoc --runs RUNS --release REL --out OUT
    python run_negative_control_r2.py report  --runs RUNS --out OUT
    python run_negative_control_r2.py all     --runs RUNS --release REL --out OUT        (check, run, verify, posthoc, report)
    python run_negative_control_r2.py tests   --out OUT                                  (pytest của gói; 10-17 phút trong container của phía viết)

RUNS : thư mục chứa mười thư mục run đã nghiệm thu (bản accepted/mm_runs_phaseC_r2_20261124: full_main_cal_time, ...).
REL  : thư mục release năm subgroup r2 (chứa meta_dataset_seed_agg.parquet).
OUT  : thư mục mới cho sản phẩm, ví dụ phaseC_negative_control_r2_20261127. Không được nằm trong RUNS.

--permutations K (mặc định 0): CHỈ dùng khi tác giả đã xác nhận câu hỏi Q-51. K > 0 ghi thêm bảng thăm dò có nhãn
mm_negative_control_r2_permutations (K phép hoán vị x mọi seed learner); bảng chính không đổi.

Mã thoát: 0 = mọi tiêu chí của bước đạt; 1 = có tiêu chí không đạt (xem acceptance_report.json); 2 = sai tham số hoặc thiếu file.
Khi một tiêu chí không đạt: DỪNG, gửi nguyên thư mục OUT cho phía viết, không sửa mã và không chạy lại bằng cách khác.
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True                        # the package tree stays as delivered: no __pycache__ beside the listed files
HERE = Path(__file__).resolve().parent
FROZEN = HERE / "phaseC_frozen_configurations_r2.json"
TREE = HERE / "handoff_2026-11-26_tree_sha256.txt"
POST_HOC_SCRIPT = HERE / "checks" / "post_hoc_h7_cost_r34b.py"
POST_HOC_REFERENCE = HERE / "checks" / "post_hoc_reference_writing_side"
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "LOKY_MAX_CPU_COUNT")   # as the phase C driver
EXPECTED_FOLDS = {"var_task_pooled_main": 7}          # every other configuration: 12
EXPECTED_DELIVERED_PASSES_TOTAL = 57                  # sum of MQ08_pass over the ten accepted mm_negative_control tables (115 folds)
TOL_REPLAY, TOL_BOOT, TOL_POST_HOC = 1e-10, 1e-12, 1e-9


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def child_env() -> dict:
    env = os.environ.copy()
    for k in THREAD_VARS:
        env[k] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"                 # console text of the children goes to log files: never fail on a legacy code page
    return env


def frozen_runs() -> list:
    return json.loads(FROZEN.read_text(encoding="utf-8"))["runs"]


def log(out: Path, msg: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "progress.log", "a", encoding="utf-8") as fh:
        fh.write(f"{now()} {msg}\n")
    print(msg, flush=True)


def tree_hashes(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}


def write_hash_list(path: Path, hashes: dict) -> None:
    path.write_text("".join(f"{h}  {name}\n" for name, h in sorted(hashes.items())), encoding="utf-8")


def guard_dirs(runs: Path, out: Path) -> None:
    r, o = runs.resolve(), out.resolve()
    if o == r or r in o.parents:
        print(f"--out ({o}) không được là hoặc nằm trong --runs ({r}): bảng đã nghiệm thu chỉ được đọc", file=sys.stderr)
        sys.exit(2)


# ----------------------------------------------------------------------------------------------------------------------
def step_check(args) -> int:
    runs, out = Path(args.runs), Path(args.out)
    guard_dirs(runs, out)
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    # (1) package tree
    lines = []
    listed = {}
    for ln in TREE.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            h, name = ln.split(None, 1)
            listed[name.strip()] = h
    for name, h in listed.items():
        p = HERE / name
        if not p.is_file():
            lines.append(f"MISSING   {name}")
            bad += 1
        elif sha256(p) != h:
            lines.append(f"MISMATCH  {name}")
            bad += 1
    lines.append(f"package tree: {len(listed)} files listed, {bad} not equal")
    (out / "handoff_tree_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(out, f"CHECK package tree: {len(listed)} files, not equal: {bad}")
    # (2) the ten run directories carry the frozen digests
    sys.path.insert(0, str(HERE))
    from metamodel.experiment import MMConfig
    import metamodel
    if not str(metamodel.__version__).startswith("0.3.1"):
        log(out, f"CHECK FAIL metamodel version is {metamodel.__version__}, expected 0.3.1")
        bad += 1
    for r in frozen_runs():
        d = runs / r["name"]
        need = [d / "mm_config.json", d / "mm_config_sha256.txt", d / "mm_run_registry.parquet", d / "mm_negative_control.parquet",
                d / "mm_recommendations.parquet", d / "mm_hypotheses.parquet"]
        missing = [p.name for p in need if not p.is_file()]
        if missing:
            log(out, f"CHECK FAIL {r['name']}: missing {missing}")
            bad += 1
            continue
        stored = (d / "mm_config_sha256.txt").read_text(encoding="utf-8").split()[0].strip().lower()
        computed = MMConfig(**json.loads((d / "mm_config.json").read_text(encoding="utf-8"))).sha256()
        ok = stored == computed == r["mm_config_sha256"]
        log(out, f"CHECK {'OK  ' if ok else 'FAIL'} {r['name']} digest {computed}")
        bad += 0 if ok else 1
    # (3) the release table is the one the runs read
    if getattr(args, "release", None):
        meta = Path(args.release) / "meta_dataset_seed_agg.parquet"
        rec = runs / "input_sha256.json"
        if not meta.is_file():
            log(out, f"CHECK FAIL release table not found: {meta}")
            bad += 1
        elif rec.is_file():
            want = json.loads(rec.read_text(encoding="utf-8")).get("meta_seed_agg_sha256")
            got = sha256(meta)
            ok = want == got
            log(out, f"CHECK {'OK  ' if ok else 'FAIL'} release table sha256 {got} (input_sha256.json of the runs: {want})")
            bad += 0 if ok else 1
        else:
            log(out, f"CHECK NOTE input_sha256.json not found in {runs}; release table sha256 {sha256(meta)}")
    # (4) environment record
    rc = subprocess.call([sys.executable, "-m", "metamodel.cli", "env", "--out", str(out / "env_record.json")], cwd=str(HERE), env=child_env(),
                         stdout=subprocess.DEVNULL)
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, env=child_env())
    freeze_text = freeze.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")     # bytes decoded here: never fail on a legacy code page
    (out / "pip_freeze.txt").write_text(freeze_text, encoding="utf-8")
    if freeze.returncode != 0:
        log(out, f"CHECK NOTE pip freeze returned {freeze.returncode}: pip_freeze.txt may be empty; state the environment in README.md")
    old = runs / "pip_freeze.txt"
    if old.is_file():
        a = set(x.strip() for x in old.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip())
        b = set(x.strip() for x in freeze_text.splitlines() if x.strip())
        diff = [f"- {x}" for x in sorted(a - b)] + [f"+ {x}" for x in sorted(b - a)]
        (out / "pip_freeze_diff_vs_phaseC.txt").write_text(("\n".join(diff) + "\n") if diff else "IDENTICAL\n", encoding="utf-8")
        log(out, f"CHECK pip freeze against the phase C delivery: {'IDENTICAL' if not diff else str(len(diff)) + ' differing lines (see pip_freeze_diff_vs_phaseC.txt)'}")
    bad += 0 if rc == 0 else 1
    log(out, f"CHECK {'PASS' if bad == 0 else 'FAIL'}: {bad} item(s) not met")
    return 0 if bad == 0 else 1


def _run_one(job) -> int:
    name, cmd, out = job
    t0 = time.time()
    log(out, f"START {name}")
    with open(out / f"{name}.stdout.log", "w", encoding="utf-8") as so, open(out / f"{name}.stderr.log", "w", encoding="utf-8") as se:
        rc = subprocess.call(cmd, cwd=str(HERE), env=child_env(), stdout=so, stderr=se)
    log(out, f"END {name} rc={rc} seconds={time.time() - t0:.1f}")
    return rc


def step_run(args) -> int:
    runs, out, meta = Path(args.runs), Path(args.out), Path(args.release) / "meta_dataset_seed_agg.parquet"
    guard_dirs(runs, out)
    out.mkdir(parents=True, exist_ok=True)
    if not meta.is_file():
        print(f"không thấy {meta}", file=sys.stderr)
        return 2
    selected = [r for r in frozen_runs() if not args.only or r["name"] in args.only]
    before = {}
    for r in frozen_runs():
        before.update({f"{r['name']}/{k}": v for k, v in tree_hashes(runs / r["name"]).items()})
    if not (out / "accepted_runs_sha256_before.txt").exists():
        write_hash_list(out / "accepted_runs_sha256_before.txt", before)
    jobs = []
    for r in selected:
        cmd = [sys.executable, "-m", "metamodel.cli", "negative-control", "--meta", str(meta), "--run-dir", str(runs / r["name"]),
               "--out", str(out / r["name"]), "--expect-digest", r["mm_config_sha256"], "--progress"]
        if args.permutations > 0:
            cmd += ["--permutations", str(args.permutations)]
        jobs.append((r["name"], cmd, out))
    log(out, f"RUN START {len(jobs)} configuration(s), permutations={args.permutations}, parallel={args.parallel}, python={sys.version.split()[0]}")
    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        codes = list(pool.map(_run_one, jobs))
    after = {}
    for r in frozen_runs():
        after.update({f"{r['name']}/{k}": v for k, v in tree_hashes(runs / r["name"]).items()})
    write_hash_list(out / "accepted_runs_sha256_after.txt", after)
    log(out, f"RUN END exit codes {dict(zip([j[0] for j in jobs], codes))}; accepted runs unchanged: {before == after}")
    return 0 if all(c == 0 for c in codes) and before == after else 1


def step_verify(args) -> int:
    runs, out = Path(args.runs), Path(args.out)
    guard_dirs(runs, out)
    (out / "verify_bootstrap").mkdir(parents=True, exist_ok=True)
    codes = {}
    for r in frozen_runs():
        with open(out / "verify_bootstrap" / f"{r['name']}.stdout.log", "w", encoding="utf-8") as so:
            codes[r["name"]] = subprocess.call([sys.executable, "-m", "metamodel.cli", "verify-bootstrap", "--run-dir", str(runs / r["name"]),
                                                "--out", str(out / "verify_bootstrap" / f"{r['name']}.csv")], cwd=str(HERE), env=child_env(),
                                               stdout=so, stderr=subprocess.STDOUT)
    log(out, f"VERIFY-BOOTSTRAP exit codes {codes}")
    return 0 if all(c == 0 for c in codes.values()) else 1


def step_posthoc(args) -> int:
    """The two labelled post hoc analyses of the writing side (H7 as registered; cost at the decision moment), run again here and
    compared with the tables of the writing side. Nothing is fitted; the analyses read stored outputs of the accepted runs."""
    import pandas as pd
    runs, out = Path(args.runs), Path(args.out)
    guard_dirs(runs, out)
    dest = out / "post_hoc"
    dest.mkdir(parents=True, exist_ok=True)
    with open(dest / "stdout.log", "w", encoding="utf-8") as so:
        rc = subprocess.call([sys.executable, str(POST_HOC_SCRIPT), "--pkg", str(HERE), "--phasec", str(runs),
                              "--meta", str(Path(args.release) / "meta_dataset_seed_agg.parquet"), "--out", str(dest)],
                             cwd=str(HERE), env=child_env(), stdout=so, stderr=subprocess.STDOUT)
    rows, worst = [], 0.0
    for ref in sorted(POST_HOC_REFERENCE.glob("*.csv")):
        new = dest / ref.name
        if rc != 0 or not new.is_file():
            rows.append({"file": ref.name, "status": "MISSING"})
            continue
        a, b = pd.read_csv(ref), pd.read_csv(new)
        if list(a.columns) != list(b.columns) or len(a) != len(b):
            rows.append({"file": ref.name, "status": "SHAPE_DIFFERS"})
            continue
        num = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]) and a[c].dtype != bool]
        txt = [c for c in a.columns if c not in num]
        dmax = max([float((a[c].astype(float) - b[c].astype(float)).abs().max()) for c in num if a[c].notna().any()] or [0.0])
        nan_equal = all((a[c].isna() == b[c].isna()).all() for c in num)
        txt_equal = all((a[c].astype(str) == b[c].astype(str)).all() for c in txt)
        worst = max(worst, dmax)
        rows.append({"file": ref.name, "rows": len(a), "max_abs_diff": dmax, "text_columns_equal": bool(txt_equal), "missing_pattern_equal": bool(nan_equal),
                     "status": "EQUAL" if (dmax <= TOL_POST_HOC and txt_equal and nan_equal) else "DIFFERS"})
    ok = rc == 0 and bool(rows) and all(r["status"] == "EQUAL" for r in rows)
    (dest / "comparison_with_writing_side.json").write_text(json.dumps({"exit_code": rc, "tolerance": TOL_POST_HOC, "files": rows, "verdict": "PASS" if ok else "FAIL"},
                                                                       ensure_ascii=False, indent=1), encoding="utf-8")
    log(out, f"POSTHOC {'PASS' if ok else 'FAIL'}: script exit {rc}; largest difference to the tables of the writing side {worst:.2e}")
    return 0 if ok else 1


def step_report(args) -> int:
    import pandas as pd
    runs, out = Path(args.runs), Path(args.out)
    guard_dirs(runs, out)
    crit, tables, perms, rows = {}, [], [], []
    delivered_total = 0
    for r in frozen_runs():
        name, d = r["name"], out / r["name"]
        row = {"config": name, "frozen_digest": r["mm_config_sha256"]}
        sp = d / "negative_control_r2_summary.json"
        if not sp.is_file():
            row["status"] = "NO OUTPUT"
            rows.append(row)
            continue
        s = json.loads(sp.read_text(encoding="utf-8"))
        t = pd.read_parquet(d / "mm_negative_control_r2.parquet")
        delivered = pd.read_parquet(runs / name / "mm_negative_control.parquet")
        delivered_total += int(delivered["MQ08_pass"].astype(bool).sum())
        want_folds = EXPECTED_FOLDS.get(name, 12)
        checks = {"verdict_PASS": s.get("verdict") == "PASS", "folds": s.get("folds") == want_folds == len(delivered), "folds_ok": s.get("folds_ok") == want_folds,
                  "digest": s.get("config_sha256") == r["mm_config_sha256"],
                  "replay_control": s.get("replay_max_abs_diff") is not None and s["replay_max_abs_diff"] <= TOL_REPLAY,
                  "replay_model": s.get("replay_model_max_abs_diff") is not None and s["replay_model_max_abs_diff"] <= TOL_REPLAY,
                  "dtypes_kept": s.get("all_state_dtypes_kept") is True,
                  "delivered_mode": s.get("delivered_control_permutation") == "LEGACY_MIXED_BLOCK_UP_TO_0_3_0",
                  "delivered_passes_equal_accepted_table": s.get("delivered_passes") == int(delivered["MQ08_pass"].astype(bool).sum()),
                  "package_0_3_1": str(s.get("metamodel_version", "")).startswith("0.3.1")}
        row.update({"folds": s.get("folds"), "folds_ok": s.get("folds_ok"), "delivered_passes": s.get("delivered_passes"),
                    "dtype_preserved_passes": s.get("dtype_preserved_passes"), "flags_changed": len(s.get("flags_changed", [])),
                    "replay_max_abs_diff": s.get("replay_max_abs_diff"), "replay_model_max_abs_diff": s.get("replay_model_max_abs_diff"),
                    "status": "OK" if all(checks.values()) else "NOT MET: " + ", ".join(k for k, v in checks.items() if not v)})
        vb = out / "verify_bootstrap" / f"{name}.json"
        if vb.is_file():
            v = json.loads(vb.read_text(encoding="utf-8"))
            row.update({"verify_bootstrap": v.get("verdict"), "verify_bootstrap_rows": v.get("rows"), "verify_bootstrap_max_abs_diff": v.get("max_abs_diff")})
        else:
            row["verify_bootstrap"] = "NOT RUN"
        rows.append(row)
        tables.append(t.assign(config=name))
        pp = d / "mm_negative_control_r2_permutations.parquet"
        if pp.is_file():
            perms.append(pd.read_parquet(pp).assign(config=name))
    summary = pd.DataFrame(rows)
    summary.to_csv(out / "negative_control_r2_by_configuration.csv", index=False)
    if tables:
        allf = pd.concat(tables, ignore_index=True)
        allf = allf[["config"] + [c for c in allf.columns if c != "config"]]
        allf.to_csv(out / "negative_control_r2_all_folds.csv", index=False)
    if perms:
        pd.concat(perms, ignore_index=True).to_csv(out / "negative_control_r2_permutations_all_folds.csv", index=False)
    b, a = out / "accepted_runs_sha256_before.txt", out / "accepted_runs_sha256_after.txt"
    unchanged = b.is_file() and a.is_file() and b.read_text(encoding="utf-8") == a.read_text(encoding="utf-8")
    tree_ok = (out / "handoff_tree_check.txt").is_file() and (out / "handoff_tree_check.txt").read_text(encoding="utf-8").strip().endswith(", 0 not equal")
    ph = out / "post_hoc" / "comparison_with_writing_side.json"
    crit["a_package_tree"] = bool(tree_ok)
    crit["b_ten_controls"] = bool(len(summary) == 10 and "status" in summary and (summary["status"] == "OK").all() and int(summary["folds"].sum()) == 115)
    crit["c_delivered_passes_total"] = bool(delivered_total == EXPECTED_DELIVERED_PASSES_TOTAL)
    crit["d_verify_bootstrap"] = bool("verify_bootstrap" in summary and (summary["verify_bootstrap"] == "PASS").all()
                                      and (summary["verify_bootstrap_max_abs_diff"] <= TOL_BOOT).all())
    crit["e_accepted_runs_unchanged"] = bool(unchanged)
    crit["f_environment_record"] = (out / "env_record.json").is_file()
    crit["g_post_hoc_tables_equal"] = bool(ph.is_file() and json.loads(ph.read_text(encoding="utf-8")).get("verdict") == "PASS")
    tests_log = out / "pytest_metamodel_0.3.1.log"
    report = {"created": now(), "criteria": crit, "verdict": "PASS" if all(crit.values()) else "FAIL",
              "totals": {"folds": int(summary["folds"].sum()) if "folds" in summary else None,
                         "delivered_passes": int(summary["delivered_passes"].sum()) if "delivered_passes" in summary else None,
                         "dtype_preserved_passes": int(summary["dtype_preserved_passes"].sum()) if "dtype_preserved_passes" in summary else None,
                         "flags_changed": int(summary["flags_changed"].sum()) if "flags_changed" in summary else None},
              "pytest_log_present": tests_log.is_file(),
              "pytest_last_line": tests_log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1] if tests_log.is_file() and tests_log.stat().st_size else None,
              "note": "criterion (a) of the request also asks for the test suite of the package: python run_negative_control_r2.py tests --out OUT"}
    (out / "acceptance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    sums = {k: v for k, v in tree_hashes(out).items() if k != "SHA256SUMS.txt"}
    write_hash_list(out / "SHA256SUMS.txt", sums)
    pd.set_option("display.width", 220)
    show = [c for c in ("config", "folds", "folds_ok", "delivered_passes", "dtype_preserved_passes", "flags_changed", "replay_max_abs_diff",
                        "replay_model_max_abs_diff", "verify_bootstrap", "status") if c in summary.columns]
    print(summary[show].to_string(index=False))
    print(json.dumps({"criteria": crit, "verdict": report["verdict"], "totals": report["totals"]}, ensure_ascii=False, indent=1))
    return 0 if report["verdict"] == "PASS" else 1


def step_tests(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "pytest_metamodel_0.3.1.log", "w", encoding="utf-8") as so:
        rc = subprocess.call([sys.executable, "-m", "pytest", "metamodel/tests", "-q", "-p", "no:cacheprovider"], cwd=str(HERE), env=child_env(),
                             stdout=so, stderr=subprocess.STDOUT)
    log(out, f"TESTS exit {rc}")
    return 0 if rc == 0 else 1


def main() -> int:
    for stream in (sys.stdout, sys.stderr):          # the messages hold Vietnamese text: never fail on a console with a legacy code page
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["check", "run", "verify", "posthoc", "report", "all", "tests"])
    ap.add_argument("--runs")
    ap.add_argument("--release")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--permutations", type=int, default=0)
    ap.add_argument("--parallel", type=int, default=1)
    args = ap.parse_args()
    need = {"check": ("runs",), "run": ("runs", "release"), "verify": ("runs",), "posthoc": ("runs", "release"), "report": ("runs",),
            "all": ("runs", "release"), "tests": ()}[args.step]
    for k in need:
        if not getattr(args, k):
            print(f"bước {args.step} cần --{k}", file=sys.stderr)
            return 2
    if args.step == "all":
        worst = 0
        for f in (step_check, step_run, step_verify, step_posthoc):
            rc = f(args)
            worst = max(worst, rc)
            if rc == 2:
                return 2
        return max(worst, step_report(args))
    return {"check": step_check, "run": step_run, "verify": step_verify, "posthoc": step_posthoc, "report": step_report, "tests": step_tests}[args.step](args)


if __name__ == "__main__":
    sys.exit(main())
