# CQ split and view code map

The executable sources remain in this directory while the pipeline is being
run from Databricks.  The version folders are navigation/documentation maps;
they deliberately do not duplicate executable code.

| Release | Entry point | Role |
|---|---|---|
| `v1` | `materialize_label_stratified_views.py` | Legacy Method-5 views and prefixes |
| `v2_1` | `build_split_v2.py` | First temporal split builder |
| `v2_2` | `build_split_v2_2.py`, `materialize_label_stratified_views_v2_2.py` | Locked CQ V2.2 split and views |
| `v2_3` | `build_split_v2_3.py`, `materialize_label_stratified_views_v2_3.py` | Subsequent split/view revision |
| audits | `audit_long_offering_assignment_v1.py` | Split and long-offering audits |

When a release is frozen and no notebook still imports the root path directly,
the corresponding sources may be moved into its version directory as one
atomic migration, together with updated upload/run commands.
