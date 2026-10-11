"""Locked CQ PatchTST experiment contract."""

MODEL_CONTRACT = {
    "task": "CQ", "release_id": "CQ_V2_2", "split_version": "v2_2",
    "phase_version": "wide_prefix_v2_2", "model_name": "PATCHTST",
    "architecture": "patchtst", "model_family": "F2_TS_TRANSFORMER",
    "model_revision": "patchtst_shared_phase_v1_prefixsafe",
    "classes": ("warning", "average", "good"), "seed": 42,
    "output_root": "runs/patchtst_seed42/CQ",
    "shared_implementation": "model.architectures.SharedPhasePatchTSTClassifier",
    "protocol": "shared_checkpoint_prefix_safe_v2_4",
}
