"""Independent imputation strategies used by the shared wide-data contract."""

from .extra_trees import build as extra_trees
from .mean import build as mean
from .median import build as median
from .mice import build as mice
from .v0 import build as v0

BUILDERS = {"v0": v0, "median": median, "mean": mean, "extra_trees": extra_trees, "mice": mice}
