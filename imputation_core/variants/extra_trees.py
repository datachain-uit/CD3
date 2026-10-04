"""V9: TEMPO-compatible chained ExtraTrees imputation.

This deliberately preserves the light ExtraTrees baseline in
``TEMPO-DQ-Framework/src/CQ/process/imputation/extra_trees_imputation``:
one shallow tree and one chained-equation pass.  It is a reproducible baseline,
not a high-cost hyperparameter search.
"""

from sklearn.ensemble import ExtraTreesRegressor
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer


def build(*, seed: int):
    estimator = ExtraTreesRegressor(
        n_estimators=1,
        max_depth=5,
        random_state=seed,
        n_jobs=-1,
    )
    return IterativeImputer(
        estimator=estimator,
        max_iter=1,
        initial_strategy="median",
        sample_posterior=False,
        skip_complete=True,
        random_state=seed,
    )
