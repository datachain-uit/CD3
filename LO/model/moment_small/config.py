"""Locked LO MOMENT-Small experiment contract."""

MODEL_CONTRACT = {
    "task": "LO", "release_id": "LO_V3_1", "split_version": "v3_1",
    "phase_version": "wide_prefix_v3_1", "model_name": "MOMENT_SMALL",
    "architecture": "moment_small", "model_family": "F3_TS_FOUNDATION",
    "model_revision": "moment_frozen_linear_probe_v1_prefixsafe",
    "classes": ("I/D", "G", "E"), "seed": 42,
    "output_root": "runs/moment_small_seed42/LO",
    "shared_implementation": "model.architectures.SharedPhaseMomentClassifier",
    "backbone": {"repo_id": "AutonLab/MOMENT-1-small", "revision": "43ee05b", "mode": "frozen_linear_probe"},
    "protocol": "shared_checkpoint_prefix_safe_v2_4",
}
