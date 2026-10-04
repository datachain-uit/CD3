"""V13: MICE/chained equations with Bayesian-ridge conditional models."""

from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer
from sklearn.linear_model import BayesianRidge


class NaNSafeBayesianRidge(BayesianRidge):
    """BayesianRidge with a train-derived fallback for sparse MICE predictors.

    IterativeImputer normally initializes every predictor before each chained
    regression.  On this release's very sparse modality matrix, sklearn can
    still pass a NaN predictor subset to ``predict``.  The fallback is learned
    exclusively from the estimator's training rows and applies only to that
    internal regression call; it never fills output columns directly.
    """

    @staticmethod
    def _finite_fill(values, fill_values=None):
        import numpy as np

        array = np.asarray(values, dtype="float64")
        if fill_values is None:
            with np.errstate(all="ignore"):
                fill_values = np.nanmedian(array, axis=0)
            fill_values = np.where(np.isfinite(fill_values), fill_values, 0.0)
        return np.where(np.isfinite(array), array, fill_values), fill_values

    def fit(self, X, y, sample_weight=None):
        clean, self._predictor_fill_values = self._finite_fill(X)
        return super().fit(clean, y, sample_weight=sample_weight)

    def predict(self, X, return_std=False):
        clean, _ = self._finite_fill(X, self._predictor_fill_values)
        return super().predict(clean, return_std=return_std)


def build(*, seed: int):
    return IterativeImputer(
        estimator=NaNSafeBayesianRidge(),
        max_iter=3,
        # With the full pooled P1--P4 matrix, a median initializer can retain
        # NaN in a sparse predictor during sklearn's chained-regression pass.
        # A finite constant is only the initial state; Bayesian Ridge replaces
        # eligible values over the subsequent MICE iterations.
        initial_strategy="constant",
        fill_value=0.0,
        sample_posterior=False,
        skip_complete=True,
        random_state=seed,
        # Emits one concise Modal log per chained-imputation round, making a
        # long full-train MICE fit observable without changing its result.
        verbose=2,
    )
