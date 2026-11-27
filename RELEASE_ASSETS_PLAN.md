# Plan of the release assets (for the author to choose; nothing is uploaded or tagged)

Release `CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2`. Hashes read on the delivered files (sha256 in `sha256sums.txt` of the release).

| File | Size (bytes) | sha256 | Limit check |
|---|---:|---|---|
| `meta_dataset_seed_agg.parquet` | 164 712 412 (157.1 MiB) | `26409d4e9b55723e4ff042d8312397cc7b0be099888e573ed4a7aa8a3d763f0a` | above the 100 MiB limit of a normal git file |
| `meta_dataset_seed_level.parquet` | 88 784 875 (84.7 MiB) | `57b56e1ab4dae42e5fdde3d66ee28c2b3a1f94a7aa346a5c3f7852e3717ef61e` | below 100 MiB, above the 50 MiB warning |
| `meta_column_dictionary.csv` | 24 408 | `162ff20d025b6e5d0bed58f09d9a674159c980cdc68d30324c28ce09a012df6f` | small |
| `meta_release_manifest.json` | 23 645 | `03b66dd289275bcec3bb67c002a4d910686c0364e0393ac4528c8609ade1e746` | small |
| `sha256sums.txt` | 4 088 | `2cf2733346bd475735b4eed1be9f5c4606631431b20bde1a812950561eab0acc` | small |
| `seed_level_parts/` | 30 parquet parts + `parts_manifest.json`, about 95 MB in total | in `parts_manifest.json` | each part below 10 MB |

Still to add when delivered by the team: `qa_outcomes_release_r2.csv` (item B.2), the folder of the three-seed slice and per-class tables (item D), the folder of the negative-control re-run (`phaseC_negative_control_r2_20261126`, already on Drive in `work_in_progress/`), and `static_layout_by_unit.csv` and `radius_fallback_class_*` files (items B.3, B.4) once accepted.

## Options

1. **GitHub Release assets (recommended by the team).** Attach the two parquet tables, the dictionary, the manifest, `sha256sums.txt` and the QA table to a Release of the tag chosen by the author. Per-asset limit is 2 GiB, so no splitting is needed. Keeps the git history small. Needs the author to create the tag; the team prepares the files only.
2. **Git LFS.** Track `*.parquet` under `meta_release/`. Adds a dependency and a quota; clones need LFS.
3. **Split parts.** Commit `seed_level_parts/` (each part below 10 MB) with the combining script and the sha256 check; for `meta_dataset_seed_agg.parquet` a split is needed too (157 MiB), which the team has not produced yet (the seed-aggregated table has no parts folder). Heavy for readers.

Results of the ten runs of phase C (`mm_runs_phaseC_r2_*`, the delivered version with files above 10 MB split into parts, 388 files): publish as one more Release asset (a zip with its sha256) or under `results/meta_runs_phaseC_r2/`; the reviewer's estimate is about 41 MiB for the tables kept in the publication copy.
