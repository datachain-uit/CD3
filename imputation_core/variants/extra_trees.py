"""V9: TEMPO-compatible chained ExtraTrees imputation.

This deliberately preserves the light ExtraTrees baseline in
``TEMPO-DQ-Framework/src/CQ/process/imputation/extra_trees_imputation``:
one shallow tree and one chained-equation pass.  It is a reproducible baseline,
not a high-cost hyperparameter search.
"""

from sklearn.ensemble import ExtraTreesRegressor
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer
from release_core.runtime_config import EXTRA_TREES


def build(*, seed: int):
    estimator = ExtraTreesRegressor(
        n_estimators=EXTRA_TREES["n_estimators"],
        max_depth=EXTRA_TREES["max_depth"],
        random_state=seed,
        n_jobs=EXTRA_TREES["n_jobs"],
    )
    return IterativeImputer(
        estimator=estimator,
        max_iter=EXTRA_TREES["max_iter"],
        initial_strategy=EXTRA_TREES["initial_strategy"],
        sample_posterior=False,
        skip_complete=True,
        random_state=seed,
    )
