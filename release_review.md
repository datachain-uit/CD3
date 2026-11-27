# Release review of the repository branch `release-prep` (26/11/2026)

Scope: the tracked files of branch `release-prep` (base `acd11c1`, three commits added by this branch) and the tables of the meta-dataset release `CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2`. Nothing was deleted or rewritten; the branch is not merged and not tagged. The findings below are for the author to decide.

## 1. Machine paths, user name, keys and tokens in tracked files

Method: `git grep -I` on the tracked files of the branch. Counts are files, not lines.

| Pattern | Files | Where | Remark |
|---|---|---|---|
| Absolute Windows drive paths (`X:\` or `X:/` followed by a name) | 42 | `tools/` only (none in `docs/`, `meta_analysis/`, `checks/`, `tools/subgroups_phaseB/`, `tools/m15_3seed/` or `tools/mq08_dtype_finding/`): backup, upload and organisation scripts of 29/10–09/11/2026 (`tools/ops_20261109/` 5 files, about 25 `.ps1`/`.py` files of 29/10–05/11), `tools/vastai_audit_shared.py`, and three seed-43/44 M-18 builders (`tools/seed43_44_pipeline/m43_build_m18.py`, `m44_build_m18.py`, `m44_build_m18_repair.py`) | 63 lines in total. Scripts of phase B and C, and `tools/seed43_44_pipeline/tempo_paths.py`, read the work and repository roots from the environment variables `TEMPO_WORK_ROOT`, `TEMPO_REPO_ROOT` and `TEMPO_AUDIT44_ROOT`. |
| Local user name | 10 | `tools/backup_jobs_rclone_20261029.ps1`, `tools/backup_l0_modal_20261029.ps1`, `tools/check_cq_backup_duplicates_20261029.ps1`, `tools/organize_drive_remaining_20261029.ps1`, `tools/organize_drive_results_20261029.ps1`, `tools/upload_drive2_results_20261029.ps1`, `tools/verify_remove_partial_drive_copies_20261029.ps1`, `tools/ops_20261109/up_lo_parent.sh`, `up_lo_parent_w.sh`, `up_v8.sh` | The user name occurs in home-directory paths. Three scripts of `tools/ops_20261109/` also name the path of an SSH private-key file (the file itself is not in the repository). |
| Private keys, credentials files, `.env`, AWS configuration | 0 | none tracked | checked by file name and by content patterns (`AKIA…`, `ghp_…`, password, API key) |
| Salt values | 0 | none | the word *secret* appears in 13 files as the name of a Modal secret (`tempo-prediction-salt`), as a code comment or as a variable name; no salt value, 32-hex or longer, is assigned in any tracked file |
| Word *token* | 22 | model and feature code (tokenisation, token embeddings), registries | not credentials |
| E-mail address, GitHub user name | 0 | none | |

Not in the tracked tree but present in the working directory of the team (ignored by `.gitignore` or untracked): `.aws/`, `.codex/`, local result folders under `CQ/resuilt/` and `LO/resuilt/`, SSH-related scripts. They must stay untracked.

Recommended before publication (author to decide): remove or replace the home-directory paths and the key path in the ten files above; decide whether the old operational scripts (backup, Drive organisation, relay and launch scripts of October–November) belong in the public repository at all.

## 2. Files that carry team-internal text

`docs/` is tracked and public. It holds team reports and reply letters (`docs/12112026/`, `docs/13112026/`, `docs/20112026/`, `docs/21112026/`, and further folders on the base branch) written for the internal exchange with the writing side, with tables derived from the results. The author decides whether to keep, move or remove them. Deleting a file in a new commit does not remove it from the git history.

## 3. Learner-level data and identifiers in the meta-dataset tables

Read on `meta_dataset_seed_level.parquet`, `meta_dataset_seed_agg.parquet` and `meta_column_dictionary.csv` (roles: KEY 22, PROV 24, TARGET 168, X_STATE 98, X_VAL 75, X_CONTEXT 34, DIAG 36, DERIVED 25, QA 13, COST 12, UNASSIGNED 54):

- No column holds a user, enrollment, course, offering, teacher or school identifier. Columns whose names contain *enrollment* or *offering* (`tr_n_enrollments`, `ev_n_enrollments`, `tr_n_offerings`, `ev_n_offerings`) are counts of the evaluated cohort.
- Role KEY columns are experiment keys: task, window, pipeline, model, seed, split, phase, subgroup axis and value, and SHA-256 digests (`meta_obs_id`, `rec_group_id`, `run_id_after`, `run_group_id`, `run_id_before`) of experiment configurations. They are not derived from learner identifiers.
- Role PROV columns carry versions, objective definitions and backend names (for example `model_revision`, `execution_backend = vastai_portable_runner`); no host names, paths or tokens.
- The tables hold aggregated metrics per run, phase and subgroup. The smallest subgroup cells hold a few learners (flag `small_subgroup_flag`); the number of evaluated samples per cell (`n_eval_samples`) and the class supports are published in the tables. The author should confirm that publishing these counts is acceptable under the terms of the source dataset.

Not checked by this review: the per-sample prediction files (they carry salted hashes of enrollment identifiers and are not part of the release).

## 4. Source dataset and terms of use

The tracked tree contains the code that reads the source dataset and the registries that name it; the terms of use of the source dataset are not stored in the repository. The author needs to state the name, the licence and the conditions for derived data before the release is described as open data. The code team has not verified these terms.

## 5. Decisions left to the author

1. Licence of the code and of the data.
2. Date of the tag for the submitted version.
3. Whether a persistent identifier is obtained for the data.
4. What to do with `docs/` and with the old operational scripts of section 1.

## 6. What this branch adds

- Commit 1: `metamodel/` (0.3.1) and `tempo_fix/` (registry revision 2026-11-26b) from the delivered package, 120 files; the blobs equal the sha256 list `handoff_2026-11-26_tree_sha256.txt` (checked file by file); `.gitattributes` (`-text` for the two folders) keeps the bytes as delivered.
- Commit 2: `run_negative_control_r2.py`, `phaseC_frozen_configurations_r2.json`, `handoff_2026-11-26_tree_sha256.txt`, `checks/` (post hoc script and the reference tables of the writing side), `requirements-meta.txt`, `meta_analysis/README.md` (reproduction), `tools/mq08_dtype_finding/` (scripts of the 24/11/2026 dtype investigation) and `tools/m15_3seed/verify_m18_vs_facts_seed44.py` (per-cell check of the M-18 package).
- Not committed: the release tables and the results of the ten runs of phase C (see the release asset plan, `RELEASE_ASSETS_PLAN.md` at the repository root).
