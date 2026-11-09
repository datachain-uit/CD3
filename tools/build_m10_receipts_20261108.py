"""M-10: README + sha256sums for the CQ QA23 evidence package and the LO prefix-audit evidence package."""
import hashlib
import shutil
from pathlib import Path

NOW = '2026-11-08'
CQ = Path('CQ/resuilt/cq_qa23_detail_20261103')
LO = Path('LO/resuilt/lo_prefix_audit_evidence_20261108')
SRC = Path('upload_staging/m10')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write_sums(root, skip):
    lines = []
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name not in skip:
            lines.append(f"{sha(p)}  {p.relative_to(root).as_posix()}")
    (root / 'sha256sums.txt').write_bytes(('\n'.join(lines) + '\n').encode())
    return len(lines)


CQ_README = f"""# CQ QA23 evidence — V2.2 (M-10)

Package folder: `cq_qa23_detail_20261103` (the request text calls it `cq_qa23_evidence_20261103`; same content, name kept as published). Receipt written {NOW}.

## 1. Source
`CQ/resuilt/qa23_v2_2.zip`, SHA-256 `615c5a947aa0a201831df376a1c06dfd3510fb474696de1dfd9b30a65675c2d3` (CRC PASS). 111 of its members were extracted verbatim (feature_dictionary_v1: 47, imputer_predictors_cq_raw_early: 46, qa23_summary: 18; per-member SHA-256 in `source_inventory.json`). `prefix_audit/full_scan.json` and `labels/label_view_consistency.json` come from the R21 evidence. These are snapshot audits; they do not prove that every time-availability assumption of the metadata holds.

## 2. Contents
| Path | What it is |
|---|---|
| `phase_id=P1..P4/qa23_summary/` | one row per phase: audited_feature_count, unreviewed_proxy_count, proxy_in_imputer_predictors, qa23_ok |
| `phase_id=P1..P4/feature_dictionary_v1/` | feature dictionary of the phase (353 rows each) |
| `phase_id=P1..P4/imputer_predictors_cq_raw_early/` | predictors allowed for the imputers (87 / 158 / 229 / 300 rows for P1 / P2 / P3 / P4) |
| `prefix_audit/full_scan.json` | prefix audit: per phase the number of future cells (P1 122,802,624; P2 81,868,416; P3 40,934,208; P4 0) and non-null future cells (0 in all four, pass), plus 65 static-column profiles |
| `labels/label_view_consistency.json` | label vs source view check: 18 inputs (train_validation and test_p1..p4 per window and split), label_mismatches = 0, source_missing = 0, source_excluded = 0 in all |
| `source_inventory.json` | zip member list with bytes and SHA-256 |
| `sha256sums.txt` | SHA-256 of every file of this folder except itself (LF line endings) |

## 3. Result of the audit (from the files)
audited_feature_count 90 / 161 / 232 / 303, unreviewed_proxy_count 0, proxy_in_imputer_predictors 0, qa23_ok = true for P1 / P2 / P3 / P4.

## 4. How label G is built (D-21(b))
Defined in `CQ/Feature_extraction/labels/build_cq_labels.py` (rule `cq_vector_proximity_v1_zero_activity_policy`):
1. Personal vector (COELO_personal, AFELO_personal, ACELO_personal); ACELO includes the comment weight.
2. d = Euclidean distance to [1, 1, 1]; proximity **G = 1 - d / sqrt(3)** (the weighted geometric mean in the code is only a diagnostic, not the label).
3. Label: `warning` if G < 0.10; `average` if 0.10 <= G < 0.30; `good` if G >= 0.30.
4. Not observed, or an invalid component: label null with an exclusion reason. At most 200,000 zero-activity warning rows are excluded, in a deterministic hash order.
Production labels: `labels/cq_personal_v3` -> `cq_label_release_v1` -> `cq_labels_v1` (built 2026-09-22).

## 5. Known limits
- Snapshot produced for data_release_id `sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045` (CQ_V2_2); the official release-identity ledger (M-08) is still open.
- The Spark `_committed/_started/_SUCCESS` marker files are kept as extracted and are hashed.
"""

LO_README = f"""# LO prefix-audit evidence — LO_V3_1 (M-10, LO side)

Receipt written {NOW}. LO has no QA23 zip equivalent to the CQ one; the LO analogue of the CQ prefix audit is `lo_prefix_source_audit_20261028`, a full scan of the LO phase views. This folder is its small-file receipt; the large parquet views are not copied.

## 1. Source
Drive: `Jobs/LO/organized_moved_20261029/L2_facts/audits_and_evidence/lo_prefix_source_audit_20261028` (28 files, 718 MiB: three result files copied here, 25 Spark parquet/marker files of `phase_views_v3_1_scored_signal_excluded/` and `test_prefix_views_v3_1_scored_signal_excluded/P1..P4`). Release: LO_V3_1, data_release_id `sha256:2edf8cc293044d29c360cb2db71b8d21e26e2187cf40c6d45266f342a826d35b`; view set `v3_1_scored_signal_excluded`. The three result files are byte copies of the Drive files dated 2026-10-28 (SHA-256 in `sha256sums.txt`). The Drive store offers MD5 only: MD5 and size of all 28 Drive files are in `drive_view_files_md5.csv` (their SHA-256 was not computed).

## 2. Contents
| File | Content |
|---|---|
| `summary_static13_full_scan.json` | scope `all_files_all_row_groups`, 13 static columns, future-phase mask per phase, 39 static parity checks, `parity_all_ok = true`, 0 mismatches, layout source RNN/W1/V0 feature_layout |
| `prefix_mask_full_scan.csv` | per phase P1..P4: 353 columns, 409,508 rows checked, future-phase columns 231 / 154 / 77 / 0, future cells checked 94,596,348 / 63,064,232 / 31,532,116 / 0, non-null future cells 0, `future_mask_ok_sample = true` in all four |
| `static13_parity.csv` | the 39 comparisons (P1 vs P2, P3, P4 for each of the 13 static columns): n_rows 409,508, n_mismatched 0, values_identical true |
| `drive_view_files_md5.csv` | path, bytes, MD5, modification time of the 28 Drive files |
| `sha256sums.txt` | SHA-256 of every file of this folder except itself (LF line endings) |

Note: the `source_file` paths inside the csv/json are Windows paths of the machine that ran the scan; they are kept as written.

## 3. How the LO label is built (counterpart of D-21(b))
Defined in `LO/Feature_extraction_LO/labels/build_lo_labels.py`. The LO target is the behavioural-performance label `LO_performance_label_3`, an operational proxy, **not** an observed completion, grade or dropout.
1. `performance_score = video_weight x watch_percent + assignment_weight x assignment_ratio_catalog + exam_weight x exam_ratio_catalog`. The ratios use the best automatic score per catalog problem and an unattempted catalog problem counts as 0, so each ratio is in [0, 1] and the score is in [0, 100]. The final-chapter exercises are the exam set when the course has a positive exam weight.
2. `E` (Excellent) if 85 <= score <= 100; `G` (Good) if 60 <= score < 85; `I/D` (Inactive/Dropout, a legacy operational band) if score < 60.
3. Enrollments without scored signal are excluded (null label, `proxy_exclusion_reason`); threshold set `CATALOG_NORMALIZED_PRIMARY_V3_1__EXCLUDE_NO_SCORED_SIGNAL`.
4. The legacy TEMPO score (clipped at 100, threshold set `TEMPO_LEGACY_CLIP_V3_1__EXCLUDE_NO_SCORED_SIGNAL`) is a separate sensitivity label and is not the target.
The build script raises if any score is outside [0, 100] or any label violates its band.

## 4. Known limits
- The scan reads the phase views as written; like the CQ audit it does not prove time-availability assumptions that the views do not encode.
- No imputer-predictor or feature-dictionary per-phase tables exist for LO in this audit; none are claimed.
- The official release-identity ledger (M-08) is still open.
"""

(CQ / 'README.md').write_text(CQ_README, encoding='utf8')
n = write_sums(CQ, {'sha256sums.txt'})
LO.mkdir(parents=True, exist_ok=True)
for f in ('summary_static13_full_scan.json', 'prefix_mask_full_scan.csv', 'static13_parity.csv'):
    shutil.copyfile(SRC / 'lo_src' / f, LO / f)
shutil.copyfile(SRC / 'drive_view_files_md5.csv', LO / 'drive_view_files_md5.csv')
(LO / 'README.md').write_text(LO_README, encoding='utf8')
m = write_sums(LO, {'sha256sums.txt'})
print('CQ files hashed', n, 'LO files hashed', m)
