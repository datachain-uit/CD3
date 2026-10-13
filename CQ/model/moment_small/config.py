"""Locked CQ MOMENT-Small experiment contract."""

MODEL_CONTRACT = {
    "task": "CQ", "release_id": "CQ_V2_2", "split_version": "v2_2",
    "phase_version": "wide_prefix_v2_2", "model_name": "MOMENT_SMALL",
    "architecture": "moment_small", "model_family": "F3_TS_FOUNDATION",
    "model_revision": "moment_frozen_linear_probe_v2_1_phase_patch",
    "input_encoding": "PHASE_AS_PATCH_REPEAT_v1_1", "revin_statistics_fusion": True,
    "constant_channel_guard": "zero_input_when_prefix_std_below_1e-6_relative",
    "classes": ("warning", "average", "good"), "seed": 42,
    "output_root": "runs/moment_small_seed42/CQ",
    "shared_implementation": "model.architectures.SharedPhaseMomentClassifier",
    "backbone": {"repo_id": "AutonLab/MOMENT-1-small", "revision": "43ee05b", "mode": "frozen_linear_probe",
                 "library": "momentfm @ 38f7310"},
    "protocol": "shared_checkpoint_prefix_safe_v2_4",
}
