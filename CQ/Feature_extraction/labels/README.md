# CQ label code map

| Release | Entry point | Role |
|---|---|---|
| `v1` | `../build_cq_labels.py`, `../cq_component_builder.py` | CQ vector-proximity label construction |

Label construction remains under `Feature_extraction/`, because labels are a
derived feature-extraction artifact rather than an imputation/model artifact.

## Provenance of the ACELO rule (note of 2026-11-09)

Source: the F0 audit of 2026-11-08 (`CQ/resuilt/f0_cq_partial_triad_20261108/README.md`, `validation/audit_cq_partial_triad_components.py`).

- The production artefacts `labels/cq_personal_v3` (3,192,206 enrollments) and `cq_labels_v1` were built with the ACELO rule **`with_comment`**
  (the comment weight is part of ACELO). A run of the production component builder at q = 1.0 reproduces `cq_personal_v3` exactly
  (max absolute difference 0.0 for COELO, AFELO and ACELO); `cq_labels_v1` equals it to 1.7e-16.
- The builder that is currently in this repository (`cq_component_builder.py`, release `v1`) leaves comments out of ACELO and therefore
  **does not reproduce the production artefacts**: 30,231 enrollments (0.95 %) differ.
- **The artefacts are the source of truth.** No label is changed by this note. Do not regenerate labels with the repository builder
  before the two rules have been reconciled.
- To reproduce either rule for audit purposes: `F0_ACELO_RULE=with_comment` (default; reproduces `cq_personal_v3`) or
  `F0_ACELO_RULE=video_problem_only` (the repository builder) in `validation/audit_cq_partial_triad_components.py`.
