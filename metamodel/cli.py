# -*- coding: utf-8 -*-
"""Command-line entry points.

    python -m metamodel.cli assemble --facts F.parquet [--resources R.parquet] [--state S.parquet] [--model-context M.parquet]
                                     [--f0 F0.parquet] [--registry tempo_fix/examples/registries_v1.6] --out OUT_DIR
                                     [--key task=CQ --key label_rule_version=... --key feature_regime=PRIMARY ...]
                                     [--accept-energy-estimates] [--require-subgroups] [--compare-all-with ACCEPTED_RELEASE_DIR]
    python -m metamodel.cli run      --meta OUT_DIR/meta_dataset_seed_agg.parquet --out MM_DIR [--objective PAPER_COMPOSITE_CAL]
                                     [--protocols E1-A E1-B E2] [--learners L1 L2 L3 L4] [--n-trials 50] [--no-b7]
                                     [--design full] [--training-subgroups all-only|mandatory] [--e1-scope pooled|per-task]
                                     [--baseline-scope matched|all-rows] [--hypothesis-rows primary-only|registered]
                                     [--small-subgroups keep|drop-from-training] [--progress]
                                     [--expect-digest SHA256] [--digest-only]
    python -m metamodel.cli negative-control --meta SEED_AGG.parquet --run-dir DELIVERED_RUN --out NEW_DIR [--expect-digest SHA256]
                                     [--permutations K] [--progress]      (0.3.1: the control alone; nothing else is fitted again)
    python -m metamodel.cli verify-bootstrap --run-dir DELIVERED_RUN [--out ROWS.csv]      (0.3.1: H1-H4 rows from stored outcomes)
    python -m metamodel.cli env [--out ENV.json]         (0.3.1: versions and thread settings of the running environment)
    python -m metamodel.cli synthetic --out DIR          (SYNTHETIC fixture; never a source of reported numbers)

Facts may be CSV or Parquet. Several ``--facts`` files (one per task or family) are concatenated.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

from . import assemble as A
from . import contracts as C
from . import experiment as E
from . import synthetic as SY
from .schema import build_column_dictionary


def _read(path: Optional[str]) -> Optional[pd.DataFrame]:
    if path is None:
        return None
    p = Path(path)
    if p.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(p)
    return pd.read_csv(p)


def _read_many(paths: Optional[List[str]], normalise: bool = False) -> Optional[pd.DataFrame]:
    """``normalise=True`` (facts, F0; release 0.2.3) renames exporter metric names to the registered names in EVERY source
    before the concatenation, so that an export writing ``f1_macro`` and one writing ``macro_f1`` end in one column."""
    if not paths:
        return None
    frames = [_read(p) for p in paths]
    if normalise:
        frames = [A.normalise_fact_columns(f) for f in frames]
    return pd.concat(frames, ignore_index=True)


def cmd_assemble(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    reg = C.load_registry_overrides(Path(args.registry) if args.registry else None)
    if reg.get("imputer_only_ref_status"):
        print("registry imputer_only_ref:", reg["imputer_only_ref_status"])
    key_defaults = {}
    for kv in args.key or []:
        k, _, v = kv.partition("=")
        key_defaults[k] = v
    energy_types = C.ENERGY_MEASURED_TYPES_WITH_ESTIMATE if args.accept_energy_estimates else C.ENERGY_MEASURED_TYPES_STRICT
    facts = _read_many(args.facts, normalise=True)
    seed_level = A.assemble_seed_level(facts, resources=_read_many(args.resources), state_profile=_read_many(args.state),
                                       model_context=_read(args.model_context), f0_reference=_read_many(args.f0),
                                       key_defaults=key_defaults, provenance={"meta_release_id": args.release_id,
                                                                              "meta_schema_version": "1.1.0", "builder_version": "metamodel " + __import__("metamodel").__version__},
                                       objective_stem=C.OBJECTIVES[args.objective], energy_measured_types=energy_types)
    planned = tuple(args.planned_seeds) if args.planned_seeds else None
    agg = A.aggregate_seeds(seed_level, planned_seeds=planned, objective_stem=C.OBJECTIVES[args.objective], energy_measured_types=energy_types)
    for name, frame in (("meta_dataset_seed_level", seed_level), ("meta_dataset_seed_agg", agg)):
        frame.to_parquet(out / f"{name}.parquet", index=False)
        if args.csv:
            frame.to_csv(out / f"{name}.csv", index=False)
    build_column_dictionary(seed_level).to_csv(out / "meta_column_dictionary.csv", index=False)
    manifest = {
        "meta_release_id": args.release_id, "n_rows_seed_level": int(len(seed_level)), "n_rows_seed_agg": int(len(agg)),
        "row_status_counts": seed_level["row_status"].value_counts().to_dict(),
        "qa_pass_rates": {c: float(seed_level[c].mean()) for c in seed_level.columns if c.startswith("qa_")},
        "objective_stem": C.OBJECTIVES[args.objective], "energy_measured_types": list(energy_types),
        "has_state_profile": bool(args.state), "has_f0_reference": bool(args.f0),
        "planned_seeds": list(planned) if planned else sorted(int(x) for x in seed_level["seed"].unique()),
        "row_status_agg_counts": agg["row_status_agg"].value_counts().to_dict(),
        "synthetic": bool(seed_level.get(SY.SYNTHETIC_FLAG, pd.Series([False])).any()),
        "imputer_only_ref_definition": "imp(a) = a for imputation-only pipelines (N10, author decision 2026-10-24)",
        "registry_imputer_only_ref_status": reg.get("imputer_only_ref_status", "registry not checked"),
        "builder_version": "metamodel " + __import__("metamodel").__version__,
        "join_stats": seed_level.attrs.get("join_stats", {}),
        "rows_by_subgroup": {k: int(v) for k, v in (seed_level["subgroup_axis"].astype(str) + "/" + seed_level["subgroup_value"].astype(str))
                             .value_counts().sort_index().items()},
        "qa_definitions": {"qa_run_level_invariant_ok": "QA24 as registered: s_eff constant over the phases and splits of one run",
                           "qa_leak_probe_identity_ok": f"check 38: s_leak equal across pipelines and models of one situation within {A.TOL_LEAK_IDENTITY:g}"},
    }
    # 0.2.6: integrity of a release with subgroup rows, and the ALL slice against an accepted release
    failures = []
    if len(manifest["rows_by_subgroup"]) > 1 or args.require_subgroups:
        manifest["subgroup_report"] = A.subgroup_report(seed_level)
        if args.require_subgroups and not manifest["subgroup_report"]["ok"]:
            failures += manifest["subgroup_report"]["violations"]
    if args.compare_all_with:
        ref_dir = Path(args.compare_all_with)
        cmp_ = {}
        for name, frame in (("meta_dataset_seed_level", seed_level), ("meta_dataset_seed_agg", agg)):
            cmp_[name] = A.compare_main_slice(frame, pd.read_parquet(ref_dir / f"{name}.parquet"))
            if not cmp_[name]["ok"]:
                failures.append(f"{name}: the (ALL, ALL) rows differ from {ref_dir} "
                                f"(rows only here {cmp_[name]['rows_only_in_candidate']}, only there {cmp_[name]['rows_only_in_reference']}, "
                                f"columns differing {sorted(cmp_[name]['columns_differing'])[:8]})")
        manifest["all_slice_against_reference"] = {"reference": str(ref_dir), **cmp_}
    (out / "meta_release_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    if failures:
        print("ACCEPTANCE CHECKS FAILED (the tables and the manifest are written for inspection):", file=sys.stderr)
        for f_ in failures:
            print("  -", f_, file=sys.stderr)
        return 2
    return 0


DESIGNS = {   # 0.3.0: (training subgroups, E1 scope, hypothesis rows) of the two presets; the other options default to the registered ones
    "legacy": ("all-only", "pooled", "primary-only"),      # the analysis of 0.2.x: (ALL, ALL) rows, one model for both tasks (Appendix E.4)
    "full": ("mandatory", "per-task", "registered"),       # the registered primary set: Table 42, §10.10, §10.8 (decisions 52-54)
}


def design_options(args: argparse.Namespace) -> dict:
    ts, scope, rows = DESIGNS[args.design]
    ts, scope, rows = args.training_subgroups or ts, args.e1_scope or scope, args.hypothesis_rows or rows
    return {"training_subgroups": C.MANDATORY_SUBGROUPS if ts == "mandatory" else None,
            "e1_scope": C.E1_SCOPE_PER_TASK if scope == "per-task" else C.E1_SCOPE_POOLED,
            "hypothesis_rows": C.HYP_ROWS_REGISTERED if rows == "registered" else C.HYP_ROWS_PRIMARY_ONLY,
            "baseline_scope": C.BASELINE_SCOPE_ALL_ROWS if args.baseline_scope == "all-rows" else C.BASELINE_SCOPE_MATCHED,
            "small_subgroup_policy": C.SMALL_SUBGROUP_DROP if args.small_subgroups == "drop-from-training" else C.SMALL_SUBGROUP_KEEP}


def cmd_run(args: argparse.Namespace) -> int:
    E.PROGRESS = bool(args.progress)
    meta = None if args.digest_only else _read(args.meta)
    cfg = E.MMConfig(**design_options(args), meta_release_id=args.release_id, objective=args.objective, table=args.table,
                     protocols=tuple(args.protocols), learners=tuple(args.learners), extra_learners=tuple(args.extra_learners),
                     n_trials=args.n_trials, include_b7=not args.no_b7, b7_default_repair=args.b7_repair, conservative=args.conservative,
                     learner_seeds=tuple(range(args.learner_seeds)),
                     energy_measured_types=C.ENERGY_MEASURED_TYPES_WITH_ESTIMATE if args.accept_energy_estimates else C.ENERGY_MEASURED_TYPES_STRICT,
                     notes=args.notes or "")
    cfg.validate()
    if args.digest_only:        # 0.3.0: the digest of the plan, computed without reading any table
        print(json.dumps({"mm_config_sha256": cfg.sha256(), "mm_config": cfg.to_dict()}, indent=1, ensure_ascii=False))
        return 0
    if meta.get(SY.SYNTHETIC_FLAG, pd.Series([False])).any():
        cfg.notes = (cfg.notes + " | SYNTHETIC INPUT: results are not experimental evidence").strip(" |")
    if args.expect_digest and cfg.sha256() != args.expect_digest.strip().lower():
        print(f"the configuration digest {cfg.sha256()} is not the frozen digest {args.expect_digest.strip().lower()}; nothing was run", file=sys.stderr)
        return 3
    res = E.run_experiment(meta, cfg, Path(args.out))
    m = res["mm_metrics"]
    cols = [c for c in ("protocol", "fold_id", "strategy", "n_groups", "mean_regret", "harm_rate", "top1_hit_rate", "gap_closure_vs_B3") if c in m.columns]
    print(m[cols].to_string(index=False) if len(m) else "no metrics produced")
    j = res.get("mm_metrics_joint")
    if j is not None and len(j):
        jc = [c for c in ("protocol", "fold_id", "task_scope", "strategy", "n_groups", "mean_regret", "harm_rate", "top1_hit_rate") if c in j.columns]
        print("\nevaluation units on the main report slice (mm_metrics_joint):")
        print(j[jc].to_string(index=False))
    return 0


def cmd_negative_control(args: argparse.Namespace) -> int:
    """0.3.1: the negative control alone, on the folds and hyper-parameters of a delivered run (decision 59, Q-48 (b))."""
    from . import experiment as E_
    if Path(args.out).resolve() == Path(args.run_dir).resolve():
        print("--out must not be the directory of the delivered run: the tables of record are never overwritten", file=sys.stderr)
        return 2
    if args.permutations < 0:
        print("--permutations must be 0 (registered control only) or a positive number", file=sys.stderr)
        return 2
    E_.PROGRESS = bool(args.progress)
    meta = _read(args.meta)
    try:
        res = E_.negative_control_only(meta, Path(args.run_dir), Path(args.out), expect_digest=args.expect_digest, tol=args.tol,
                                       permutations=args.permutations)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    s_ = res["summary"]
    print(json.dumps({k: v for k, v in s_.items() if k not in ("flags_changed", "environment", "exploratory_permutations")}, ensure_ascii=False))
    print("flags changed:", s_["flags_changed"])
    if "exploratory_permutations" in s_:
        print("exploratory permutations (labelled, not the registered control):")
        print(pd.DataFrame(s_["exploratory_permutations"]["per_fold"]).to_string(index=False))
    return 0 if s_["verdict"] == "PASS" else 1


def cmd_verify_bootstrap(args: argparse.Namespace) -> int:
    """0.3.1: recompute the paired bootstrap rows of H1-H4 from the stored outcomes of a delivered run and compare with mm_hypotheses."""
    from . import verify as V_
    res = V_.verify_bootstrap(Path(args.run_dir), tol=args.tol)
    record = {k: v for k, v in res.items() if k != "table"}
    record["environment"] = E.environment_record()
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        res["table"].to_csv(args.out, index=False)
        Path(args.out).with_suffix(".json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k != "environment"}, ensure_ascii=False))
    return 0 if res["verdict"] == "PASS" else 1


def cmd_env(args: argparse.Namespace) -> int:
    """0.3.1: versions and thread settings of the running environment (no host name, user name or path)."""
    record = E.environment_record()
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=1))
    return 0


def cmd_synthetic(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frames = SY.make_synthetic(seeds=tuple(C.MASTER_SEEDS[: args.n_seeds]), models=tuple(args.models),
                               subgroups=C.MANDATORY_SUBGROUPS if args.five_subgroups else (("ALL", "ALL"),))
    for name, frame in frames.items():
        frame.to_parquet(out / f"synthetic_{name}.parquet", index=False)
    print(f"SYNTHETIC fixture written to {out} (facts rows: {len(frames['facts'])}). Not experimental evidence.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="metamodel", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("assemble", help="long facts -> meta_dataset_seed_level / seed_agg")
    a.add_argument("--facts", nargs="+", required=True)
    a.add_argument("--resources", nargs="*")
    a.add_argument("--state", nargs="*", help="S0 state-profile table(s) with Z_D/Z_DQ/Z_T columns")
    a.add_argument("--model-context")
    a.add_argument("--f0", nargs="*", help="deterministic tier-F0 reference metrics")
    a.add_argument("--registry", help="tempo_fix/examples/registries_v1.6 to verify the constants")
    a.add_argument("--out", required=True)
    a.add_argument("--release-id", default="UNRELEASED")
    a.add_argument("--objective", default=C.DEFAULT_OBJECTIVE, choices=list(C.OBJECTIVES))
    a.add_argument("--key", action="append", help="constant key component, e.g. --key feature_regime=CQ_RAW_EARLY")
    a.add_argument("--accept-energy-estimates", action="store_true", help="treat NVML power-sampling estimates as measured (D-15)")
    a.add_argument("--planned-seeds", nargs="+", type=int, help="registered master seeds (default: the seeds present); rows with fewer seeds are PARTIAL")
    a.add_argument("--csv", action="store_true")
    a.add_argument("--require-subgroups", action="store_true",
                   help="0.2.6: fail (exit code 2) unless the five mandatory subgroups are present and pass assemble.subgroup_report")
    a.add_argument("--compare-all-with", metavar="RELEASE_DIR",
                   help="0.2.6: fail (exit code 2) unless the (ALL, ALL) rows equal those of the accepted release in RELEASE_DIR")
    a.set_defaults(func=cmd_assemble)
    r = sub.add_parser("run", help="meta-model experiment on a meta-dataset table")
    r.add_argument("--meta", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--release-id", default="UNRELEASED")
    r.add_argument("--objective", default=C.DEFAULT_OBJECTIVE, choices=list(C.OBJECTIVES))
    r.add_argument("--table", default="seed_agg", choices=["seed_agg", "seed_level"])
    r.add_argument("--protocols", nargs="+", default=["E1-A", "E1-B"], choices=list(C.PROTOCOLS))
    r.add_argument("--learners", nargs="+", default=["L1", "L2", "L3", "L4"])
    r.add_argument("--extra-learners", nargs="*", default=["L5", "L6"])
    r.add_argument("--n-trials", type=int, default=50)
    r.add_argument("--learner-seeds", type=int, default=5)
    r.add_argument("--no-b7", action="store_true", help="drop B7 (TEMPO-DQ diagnosis policy; in the contract since 2026-10-24, on by default)")
    r.add_argument("--b7-repair", default=C.B7_DEFAULT_REPAIR, choices=list(C.PIPELINE_IDS), help="pipeline B7 prescribes in Q3/Q4 (default V2)")
    r.add_argument("--conservative", action="store_true")
    r.add_argument("--accept-energy-estimates", action="store_true")
    r.add_argument("--notes")
    r.add_argument("--design", default="legacy", choices=list(DESIGNS),
                   help="0.3.0: 'full' = the registered primary set (training on the five mandatory subgroups, one model per task and fold, "
                        "registered hypothesis rows); 'legacy' (default) = the analysis of 0.2.x, unchanged")
    r.add_argument("--training-subgroups", choices=["all-only", "mandatory"], help="0.3.0: override the preset (all-only = robustness variant of Table 42)")
    r.add_argument("--e1-scope", choices=["pooled", "per-task"], help="0.3.0: override the preset (pooled = Appendix E.4, sensitivity)")
    r.add_argument("--hypothesis-rows", choices=["primary-only", "registered"], help="0.3.0: override the preset")
    r.add_argument("--baseline-scope", default="matched", choices=["matched", "all-rows"],
                   help="0.3.0: baselines and inner selection on the slice they score (registered) or on every training row (sensitivity)")
    r.add_argument("--small-subgroups", default="keep", choices=["keep", "drop-from-training"],
                   help="0.3.0: keep the secondary rows flagged small_subgroup_flag in the fits (registered) or drop them (sensitivity)")
    r.add_argument("--progress", action="store_true", help="0.3.0: print one line per learner cell (results unchanged)")
    r.add_argument("--expect-digest", metavar="SHA256",
                   help="0.3.0: refuse to run (exit code 3) unless the sha256 of the configuration equals this frozen digest")
    r.add_argument("--digest-only", action="store_true",
                   help="0.3.0: print the configuration and its sha256 and exit; no table is read (--meta and --out are not opened)")
    r.set_defaults(func=cmd_run)
    n = sub.add_parser("negative-control", help="0.3.1: re-run the negative control alone on the folds and hyper-parameters of a delivered run")
    n.add_argument("--meta", required=True, help="seed-aggregated meta-dataset table the delivered run read (parquet or csv)")
    n.add_argument("--run-dir", required=True, help="directory of the delivered run (mm_config.json, mm_run_registry.parquet, mm_negative_control.parquet)")
    n.add_argument("--out", required=True, help="output directory (mm_negative_control_r2.parquet/.csv, negative_control_r2_summary.json)")
    n.add_argument("--expect-digest", metavar="SHA256", help="refuse to run unless the configuration of the run directory has this digest")
    n.add_argument("--tol", type=float, default=1e-10, help="largest admitted difference between a replay (delivered control, model of record) and the delivered table")
    n.add_argument("--permutations", type=int, default=0, metavar="K",
                   help="0 (default): the registered control only. K > 0: also write the LABELLED EXPLORATORY table of K permutations, "
                        "each fitted with every learner seed of the configuration (mm_negative_control_r2_permutations)")
    n.add_argument("--progress", action="store_true", help="one line per fold on stdout")
    n.set_defaults(func=cmd_negative_control)
    v = sub.add_parser("verify-bootstrap", help="0.3.1: recompute the paired bootstrap rows of H1-H4 from a delivered run and compare with its mm_hypotheses")
    v.add_argument("--run-dir", required=True)
    v.add_argument("--out", help="optional csv of the recomputed rows; a .json with the verdict and the environment is written next to it")
    v.add_argument("--tol", type=float, default=1e-12)
    v.set_defaults(func=cmd_verify_bootstrap)
    e = sub.add_parser("env", help="0.3.1: print the versions and thread settings of the running environment")
    e.add_argument("--out", help="optional json file")
    e.set_defaults(func=cmd_env)
    s = sub.add_parser("synthetic", help="write the SYNTHETIC fixture")
    s.add_argument("--out", required=True)
    s.add_argument("--n-seeds", type=int, default=3)
    s.add_argument("--models", nargs="+", default=["RNN", "LSTM", "GRU", "BILSTM", "PATCHTST"])
    s.add_argument("--five-subgroups", action="store_true", help="0.2.6: also write the four SEEN/UNSEEN subgroup slices")
    s.set_defaults(func=cmd_synthetic)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
