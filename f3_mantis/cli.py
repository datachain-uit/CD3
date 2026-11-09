# -*- coding: utf-8 -*-
"""Command line of the F3 package.

    python -m f3_mantis.cli selftest                       # installation check, random weights, CPU, ~1 min
    python -m f3_mantis.cli pin --out backbone_pin.json     # download the pinned snapshot, hash its files, strict load
    python -m f3_mantis.cli bench --device cuda --channels 274 --rows 20000 [--snapshot DIR]
    python -m f3_mantis.cli estimate --train-rows 1609276 --val-rows 250000 --test-rows 250000

``selftest`` never reads project data. ``bench`` encodes random tensors only (cost pilot of check 37 (c));
the determinism pilot on CQ/W1/V0/seed 42 runs through the team's runner (see the guide, step M-19).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

from .spec import MANTIS_V2_SPEC, spec_digest


def _cmd_selftest(args) -> int:
    import torch

    from .adapter import ChannelPCAAdapter
    from .determinism import configure_determinism
    from .encoder import MantisPrefixEncoder, load_frozen_mantis
    from .probe import predict_probe, train_probe
    from .store import CacheKey, EmbeddingStore

    configure_determinism(42)
    rng = np.random.default_rng(0)
    n_train, n_val, channels, static_dim = 600, 200, 24, 5

    def make(n):
        y = rng.integers(0, 3, size=n)
        base = rng.normal(size=(n, 1, channels)).astype(np.float32)
        steps = np.cumsum(np.abs(rng.normal(size=(n, 4, channels))).astype(np.float32), axis=1)
        dynamic = base + 0.3 * steps + y[:, None, None].astype(np.float32) * np.linspace(0.2, 0.8, 4)[None, :, None]
        dynamic[:, :, -3:] = 1.0                                   # constant channels, as the mask bases often are
        static = rng.normal(size=(n, static_dim)).astype(np.float32)
        return dynamic.astype(np.float32), static, y

    tr_dyn, tr_sta, tr_y = make(n_train)
    va_dyn, va_sta, va_y = make(n_val)
    adapter = ChannelPCAAdapter(n_components=8).fit(tr_dyn)
    backbone = load_frozen_mantis(pretrained=False)
    encoder = MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=2048)
    with tempfile.TemporaryDirectory() as tmp:
        store = EmbeddingStore(tmp)
        key_tr = CacheKey("SELFTEST", "W1", "V0", adapter.digest(), encoder.fingerprint_digest, "REAL_TRAIN")
        key_va = CacheKey("SELFTEST", "W1", "V0", adapter.digest(), encoder.fingerprint_digest, "VALIDATION")
        store.write(key_tr, encoder, tr_dyn, np.arange(n_train))
        store.write(key_va, encoder, va_dyn, np.arange(n_val))
        z_tr, _, _ = store.open(key_tr, verify=True)
        z_va, _, _ = store.open(key_va, verify=True)
        result = train_probe(z_tr, tr_sta, tr_y, z_va, va_sta, va_y, num_classes=3, seed=42)
        probs = predict_probe(result["model"], z_va, va_sta)
        prefix_k = 2
        z_k = encoder.encode(va_dyn[:, :prefix_k], prefixes=(prefix_k,))
        prefix_ok = bool(np.array_equal(z_k[:, 0], np.asarray(z_va[:, prefix_k - 1])))
    report = {"backbone_parameters_used": int(backbone.f3_param_count_used), "embedding_dim": encoder.embedding_dim,
              "max_abs_embedding": encoder.last_timing.get("max_abs_embedding"),
              "best_epoch": result["best_epoch"], "validation_macro_f1_mean": round(result["selection_key"]["validation_macro_f1_mean_p1_p4"], 4),
              "probabilities_shape": list(probs.shape), "prefix_truncation_identical": prefix_ok,
              "torch": torch.__version__, "spec_digest": spec_digest()}
    print(json.dumps(report, indent=2))
    return 0 if prefix_ok and np.isfinite(probs).all() else 1


def _cmd_pin(args) -> int:
    from huggingface_hub import HfApi, snapshot_download

    from .encoder import load_frozen_mantis

    repo, revision = args.repo, args.revision
    info = HfApi().model_info(repo, revision=revision)
    local = snapshot_download(repo_id=repo, revision=revision, cache_dir=args.cache_dir)
    files = {}
    for path in sorted(Path(local).rglob("*")):
        if path.is_file():
            files[str(path.relative_to(local))] = hashlib.sha256(path.read_bytes()).hexdigest()
    pin = {"repo_id": repo, "requested_revision": revision, "resolved_sha": info.sha, "snapshot_dir": str(local),
           "files_sha256": files, "last_modified": str(getattr(info, "last_modified", "")),
           "card_licence": (getattr(info, "card_data", None) or {}).get("license") if getattr(info, "card_data", None) else None}
    code = 0
    if info.sha != revision:
        print(f"WARNING: resolved sha {info.sha} differs from the registered revision {revision}", file=sys.stderr)
        code = 2
    try:   # strict key-by-key load of the snapshot, truncation, parameter count, weights fingerprint (check 37 (a))
        net = load_frozen_mantis(device="cpu", snapshot_dir=str(local))
        pin.update({"strict_load": True, "param_count_backbone_used": int(net.f3_param_count_used),
                    "weights_sha256_truncated": net.f3_weights_sha256})
    except Exception as error:     # report and fail; never fall back to a non-strict load
        pin.update({"strict_load": False, "load_error": f"{type(error).__name__}: {error}"})
        print(f"ERROR: the snapshot does not load strictly: {error}", file=sys.stderr)
        code = 3
    Path(args.out).write_text(json.dumps(pin, indent=2), encoding="utf-8")
    print(json.dumps(pin, indent=2))
    return code


def _cmd_bench(args) -> int:
    import torch

    from .adapter import ChannelPCAAdapter
    from .determinism import configure_determinism, library_versions
    from .encoder import MantisPrefixEncoder, cache_bytes, count_sequences, load_frozen_mantis

    configure_determinism(42)
    rng = np.random.default_rng(1)
    dynamic = np.cumsum(np.abs(rng.normal(size=(args.rows, 4, args.channels))), axis=1).astype(np.float32)
    adapter = ChannelPCAAdapter(n_components=args.components).fit(dynamic)
    backbone = load_frozen_mantis(device=args.device, pretrained=bool(args.snapshot), snapshot_dir=args.snapshot)
    encoder = MantisPrefixEncoder(backbone, adapter, device=args.device, precision=args.precision,
                                  microbatch_sequences=args.microbatch_sequences)
    encoder.encode(dynamic[: min(256, args.rows)])                  # warm-up
    encoder.encode(dynamic)
    rate = encoder.last_timing["sequences_per_second"]
    report = {"rows": args.rows, "channels": args.channels, "components": args.components, "timing": encoder.last_timing,
              "microbatch_sequences": encoder.microbatch_sequences, "encoder_fingerprint": encoder.fingerprint(),
              "pretrained": bool(args.snapshot), "precision": encoder.precision, "libraries": library_versions()}
    if torch.cuda.is_available() and str(args.device).startswith("cuda"):
        report["peak_cuda_memory_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 3)
    for n in args.extrapolate:
        seq = count_sequences(n, args.components)
        report.setdefault("extrapolation", []).append({"rows": n, "sequences": seq, "hours": round(seq / rate / 3600, 3),
                                                       "cache_gb_float16": round(cache_bytes(n, args.components) / 1e9, 2)})
    seq_all = count_sequences(args.rows, args.channels)
    report["all_channels_hours_for_bench_rows"] = round(seq_all / rate / 3600, 3)
    print(json.dumps(report, indent=2, default=str))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return 0


def _cmd_estimate(args) -> int:
    from .encoder import cache_bytes, count_sequences

    q = args.components
    rows = {"REAL_TRAIN": args.train_rows, "VALIDATION": args.val_rows, "TEST": args.test_rows}
    report = {"components": q, "per_imputer_level_A": {}, "note": "one pass per (task, window, imputer); synthetic rows "
              "of each balanced pipeline x seed are encoded separately (level B)"}
    for split, n in rows.items():
        report["per_imputer_level_A"][split] = {"sequences": count_sequences(n, q),
                                                "cache_gb_float16": round(cache_bytes(n, q) / 1e9, 2)}
    if args.rate:
        total = sum(count_sequences(n, q) for n in rows.values())
        report["hours_per_imputer_at_rate"] = round(total / args.rate / 3600, 3)
    print(json.dumps(report, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="f3_mantis")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    p_pin = sub.add_parser("pin")
    p_pin.add_argument("--repo", default=MANTIS_V2_SPEC["pretrained_repo"])
    p_pin.add_argument("--revision", default=MANTIS_V2_SPEC["pretrained_revision"])
    p_pin.add_argument("--cache-dir", default=None)
    p_pin.add_argument("--out", default="backbone_pin.json")
    p_bench = sub.add_parser("bench")
    p_bench.add_argument("--device", default="cuda")
    p_bench.add_argument("--rows", type=int, default=20000)
    p_bench.add_argument("--channels", type=int, default=274)
    p_bench.add_argument("--components", type=int, default=int(MANTIS_V2_SPEC["channel_adapter"]["n_components"]))
    p_bench.add_argument("--precision", default=None, choices=[None, "bf16", "fp32"])
    p_bench.add_argument("--snapshot", default=None, help="local snapshot from 'pin' (random weights if omitted)")
    p_bench.add_argument("--microbatch-sequences", type=int, default=int(MANTIS_V2_SPEC["microbatch_sequences"]))
    p_bench.add_argument("--extrapolate", type=int, nargs="*", default=[1609276])
    p_bench.add_argument("--out", default=None)
    p_est = sub.add_parser("estimate")
    p_est.add_argument("--train-rows", type=int, required=True)
    p_est.add_argument("--val-rows", type=int, required=True)
    p_est.add_argument("--test-rows", type=int, required=True)
    p_est.add_argument("--components", type=int, default=int(MANTIS_V2_SPEC["channel_adapter"]["n_components"]))
    p_est.add_argument("--rate", type=float, default=None, help="measured sequences per second from 'bench'")
    args = parser.parse_args(argv)
    return {"selftest": _cmd_selftest, "pin": _cmd_pin, "bench": _cmd_bench, "estimate": _cmd_estimate}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
