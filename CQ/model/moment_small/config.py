"""Locked CQ MOMENT-Small experiment contract."""

MODEL_CONTRACT = {
    "task": "CQ", "release_id": "CQ_V2_2", "split_version": "v2_2",
    "phase_version": "wide_prefix_v2_2", "model_name": "MOMENT_SMALL",
    "architecture": "moment_small", "model_family": "F3_TS_FOUNDATION",
    "model_revision": "moment_frozen_linear_probe_v1_prefixsafe",
    "classes": ("warning", "average", "good"), "seed": 42,
    "output_root": "runs/moment_small_seed42/CQ",
    "shared_implementation": "model.architectures.SharedPhaseMomentClassifier",
    "backbone": {"repo_id": "AutonLab/MOMENT-1-small", "revision": "43ee05b", "mode": "frozen_linear_probe"},
    "protocol": "shared_checkpoint_prefix_safe_v2_4",
}
