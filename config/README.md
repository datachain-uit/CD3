# Runtime paths

Tracked protocol configs use relative defaults (`preprocessed` and `raw`) so
the repository contains no personal Databricks workspace or Volume path.

Before running a Spark job, set both variables in the notebook/job:

```python
import os
os.environ["TEMPO_OUTPUT_BASE"] = "/Volumes/<catalog>/<schema>/<volume>/preprocessed"
os.environ["TEMPO_RAW_BASE"] = "/Volumes/<catalog>/<schema>/<volume>/raw"
```

`PROJECT_ROOT` is optional for normal file execution: entry points infer it
from their own location. Set it only when executing copied notebook cells
without a meaningful `__file__`.
