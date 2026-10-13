"""Locked LO PatchTST experiment contract."""

MODEL_CONTRACT = {
    "task": "LO", "release_id": "LO_V3_1", "split_version": "v3_1",
    "phase_version": "wide_prefix_v3_1", "model_name": "PATCHTST",
    "architecture": "patchtst", "model_family": "F2_TS_TRANSFORMER",
    "model_revision": "patchtst_channel_independent_v2_1_math_sdp",
    "classes": ("I/D", "G", "E"), "seed": 42,
    "output_root": "runs/patchtst_seed42/LO",
    "shared_implementation": "model.architectures.SharedPhasePatchTSTClassifier",
    "channel_mixing": False,
    "channel_aggregation": "flatten_after_shared_encoder",
    "attention_backend": "math_sdp__flash_and_mem_efficient_disabled_for_large_BxC",
    "protocol": "shared_checkpoint_prefix_safe_v2_4",
}
