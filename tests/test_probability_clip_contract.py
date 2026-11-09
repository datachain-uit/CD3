import numpy as np

from metrics_core.evaluation import classification_metrics
from model.metrics import calibration_metrics


def test_calibration_matches_registered_clip_and_renormalization():
    y = np.array([0, 1, 2, 0])
    probabilities = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [.2, .3, .5]], dtype=np.float32)
    fact = classification_metrics(y, probabilities)
    model = calibration_metrics(y, probabilities, np.arange(3))
    assert np.isclose(fact['log_loss'], model['multiclass_nll'], rtol=0, atol=1e-14)
    assert np.isclose(fact['brier'], model['multiclass_brier'], rtol=0, atol=1e-14)
    assert np.isclose(fact['ece'], model['top_label_ece_15'], rtol=0, atol=1e-14)
