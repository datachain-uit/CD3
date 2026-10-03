# LO label code map

| Release | Entry point | Role |
|---|---|---|
| `v1` | `../build_lo_labels.py` | Legacy operational/behavioural LO label lineage |
| `v3_1` | `../build_lo_labels.py` and `../audit_lo_*` | Catalog-normalized activity-derived final-score label and its audits |

The same builder filename serves successive releases through the locked
protocol configuration. The release is identified by the configuration and
written label artifact/manifest, not by copying a mutable builder.
