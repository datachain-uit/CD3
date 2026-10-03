# LO split and view code map

The root files are still the executable Databricks entry points. Version
folders are an additive map, preventing accidental breakage of existing
`PROJECT_ROOT/views/...` upload and `run_clean(...)` commands.

| Release | Entry point | Role |
|---|---|---|
| `v1` | `materialize_label_stratified_views.py` | Legacy Method-5 views and prefixes |
| `v2_1` | `build_split_v2.py` | First temporal split builder |
| `v2_2` | `build_split_v2_2.py`, `materialize_label_stratified_views_v2_2.py` | Shared-calendar temporal split/views |
| `v2_3` | `build_split_v2_3.py`, `materialize_label_stratified_views_v2_3.py` | Follow-on temporal split/views revision |
| `v3_1` | `materialize_label_stratified_views_v3_1.py` | Catalog-normalized, scored-signal-excluded LO views |
| audits | `audit_lo_proxy_label_coverage_v1.py`, `audit_long_offering_assignment_v1.py` | Coverage, assignment, and long-offering audits |
