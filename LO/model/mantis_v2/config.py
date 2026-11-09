"""Locked LO MANTIS_V2 experiment contract (exploratory F3 tier, decision 37 of 2026-11-06)."""

MODEL_CONTRACT = {
    "task": "LO", "release_id": "LO_V3_1", "split_version": "v3_1",
    "phase_version": "wide_prefix_v3_1",
    "model_name": "MANTIS_V2", "architecture": "mantis_v2", "model_family": "F3_TS_FOUNDATION",
    "variant_role": "EXPLORATORY", "model_revision": "mantisv2_frozen_linear_probe_v1_pca8_interp512",
    "input_encoding": "PCA8_PER_PHASE_THEN_LINEAR_RESIZE_512_v1", "channel_adapter": "PCA8_REAL_TRAIN_ROWS_STANDARDISED",
    "constant_series_guard": "exact_zero_instance_norm_when_std_below_1e-6_relative",
    "shared_implementation": "f3_mantis.cell.run_cell",
    "backbone": {"repo_id": "paris-noah/MantisV2", "revision": "8f6ca35cb54ab14b120618943c6fca5ddf5a76a6",
                 "mode": "frozen_linear_probe", "library": "mantis-tsfm==1.1.0", "return_transf_layer": 2, "output_token": "combined"},
    "protocol": "shared_checkpoint_prefix_safe_v2_4",
    "classes": ("I/D", "G", "E"), "seed": 42,
    "output_root": "runs/mantis_v2_seed42/LO",
}
