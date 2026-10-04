"""Single executable hyperparameter contract for the locked CQ/LO releases."""
from __future__ import annotations

MICE = {"max_iter": 3, "tol": 1e-3, "fit_sample_rows": 1_000_000,
        "initial_strategy": "constant", "fill_value": 0.0, "sample_posterior": False}
EXTRA_TREES = {"n_estimators": 1, "max_depth": 5, "max_iter": 1, "n_jobs": -1,
               "initial_strategy": "median"}
BALANCERS = {
    "CDSMOTE": {"n_clusters": 5},
    "SASMOTE": {"visible_k": 16, "max_inspectors": 4, "inspector_trees": 16,
                 "inspector_n_jobs": 8, "uncertainty_threshold": 0.5,
                 "candidate_batch_size": 262_144, "max_candidate_rounds": 32},
    "RADIUS_SMOTE": {"radius": 0.092, "radius_space": "scaled_numeric_model_input"},
}
SAMPLING = {"sampling_strategy_id": "IR10_K10", "ir_target": 10, "max_expansion_per_class": 10}
MODEL = {"hidden_size": 128, "num_layers": 1, "dropout": 0.3, "batch_size": 2048,
         "max_epochs": 50, "patience": 5, "learning_rate": 1e-3,
         "weight_decay": 1e-5, "workers": 4, "precision_policy": "bf16_amp"}
