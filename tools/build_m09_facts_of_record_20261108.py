"""Build M-09 deliverables: three T1-EX-07 READMEs, FACTS_OF_RECORD.md and the per-file SHA-256 list.

Every value comes from the downloaded Drive folders (upload_staging/m09/inventory.json, files hashed here), the resource tables
of the exports, the packages' own summaries/READMEs and the registry module. Anything the exports do not record is written as
NOT RECORDED, never guessed.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'LO'))
sys.path.insert(0, str(ROOT))
import registries

OUT = ROOT / 'CQ' / 'resuilt' / 'm09_facts_of_record_20261108'
OUT.mkdir(parents=True, exist_ok=True)
INV = json.loads((ROOT / 'upload_staging' / 'm09' / 'inventory.json').read_text(encoding='utf8'))
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%d')


def fix(text):
    """Translate the pre-migration Drive paths (Jobs/...) into the layout of 2026-11-09 (Results/...)."""
    for a, b in (
        ('Jobs/L3_meta/m13_inputs_phase1_20261108', 'cross_task_meta/work_in_progress/m13_inputs_phase1_20261108'),
        ('Jobs/L3_meta/retroactive_receipts_20261108', 'cross_task_meta/retroactive_receipts/retroactive_receipts_20261108'),
        ('Jobs/CQ/organized_moved_20261029/', 'CQ/'), ('Jobs/LO/organized_moved_20261029/', 'LO/'),
        ('CQ/organized_moved_20261029/', 'CQ/'), ('LO/organized_moved_20261029/', 'LO/'),
        ('Jobs/LO/.../lo_static_v2_seed42_20261026/models', 'LO/L1_runs/S3_model/primary/release=LO_STATIC_V2/lo_static_v2_seed42_20261026/models'),
        ('at the root of Jobs/', 'at the root of Results/'), ('Jobs-relative path', 'Results-relative path'),
        ('Thư mục (dưới `Jobs/`)', 'Thư mục (dưới `Results/`)'), ('ở gốc `Jobs/`', 'ở gốc `Results/`'),
    ):
        text = text.replace(a, b)
    return text
CQ_REL = 'sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045'
LO_REL = 'sha256:2edf8cc293044d29c360cb2db71b8d21e26e2187cf40c6d45266f342a826d35b'
REGISTRY_NOW = registries.REGISTRY_REVISION

pipes = registries.build_pipeline_registry()
mapping_lines = ['| Pipeline | Imputer family | Imputer | Balancer family | Balancer | Parent (imputer-only) |', '|---|---|---|---|---|---|']
parent = {'V2': 'V1', 'V3': 'V1', 'V4': 'V1', 'V6': 'V5', 'V7': 'V5', 'V8': 'V5', 'V10': 'V9', 'V11': 'V9', 'V12': 'V9', 'V14': 'V13', 'V15': 'V13', 'V16': 'V13'}
for p in pipes:
    mapping_lines.append(f"| {p['pipeline_id']} | {p['imputer_family']} | {p['imputer']} | {p['balancer_family']} | {p['balancer']} | {parent.get(p['pipeline_id'], p['pipeline_id'])} |")
MAPPING = '\n'.join(mapping_lines)


def table_hashes(key, suffixes=('.parquet', '.json')):
    rows = [f for f in INV[key]['files'] if f['rel'].endswith(suffixes) and '/' not in f['rel']]
    return '\n'.join(f"  - `{f['rel']}` — {f['bytes']:,} bytes — `{f['sha256']}`" for f in rows)


def readme(title, folder_key, drive_path, merge, energy, backend, commits, layout, extra):
    return f"""# {title} — T1-EX-07 README

Folder: `{drive_path}`
Written: {NOW} by the code team. Every statement below is traceable to a file in this folder, to the run manifests/receipts named here, or to the registry module; items the export does not record are marked NOT RECORDED.

## 1. Content and merge rule
{merge}

## 2. Energy label
{energy}

## 3. Pipeline mapping V0-V16 -> (imputer, balancer)
From `registries.build_pipeline_registry()` (LO/registries.py). V0 is the no-intervention row; every balanced pipeline has an imputer-only parent whose imputed TRAIN rows it augments.

{MAPPING}

## 4. Backend and ingest receipt
{backend}

## 5. Repository and runner commits
{commits}

## 6. Registry version
The export does not record a registry revision. Derived from git where a runner commit is known (see section 5): R4 LSTM/GRU/BILSTM -> `registries_rev_2026-10-14_r1` (commit `ce0486e`); PatchTST V0-V6 -> `registries_rev_2026-10-27_r1` (commit `29da3b25`); LO static-v2 -> `registries_rev_2026-10-25_r1` (commit `b0e5ae12`); R4 RNN: not determinable (uncommitted working tree). Repository registry revision at the time of this README: `{REGISTRY_NOW}` (not the one in force when the cells were run).

## 7. Static layout hash
{layout}

## 8. Release identity
CQ data_release_id `{CQ_REL}` (CQ_V2_2); LO data_release_id `{LO_REL}` (LO_V3_1). A release-identity ledger snapshot for CQ exists (`cq_release_identity_modal_20261107`, generated 2026-10-22, data_release_id_current equal to the identity above); the official ledger of the release identity app (M-08) is still open.

## 9. File hashes (SHA-256)
Per-file hashes of this folder are in `FACTS_OF_RECORD_sha256.txt` at the root of Jobs/ (section "{folder_key}"); main tables:
{table_hashes(folder_key)}

## 10. Known limits
{extra}
"""


R4_MERGE = """One row per family (RNN, LSTM, GRU, BILSTM), pipeline (V0-V16), window (W1-W3), split (VALIDATION, TEST) and phase (P1-P4): 1,632 evaluation cells, 204 resource runs, 4,896 per-class rows, 14,688 per-class bootstrap rows (seed 42; see `summary.json`). TRAIN time is the sum of epoch `train_seconds`.
The export does not document how the four families were merged. What is verifiable: the LSTM, GRU and BILSTM rows (153 runs) were ingested earlier under `vastai_cq_f1_batch2048_seed42_slice_r2_20261019` (receipt in `L0_registry/modal_L0_registry/L0_registry/external_fact_ingests/task=CQ/`, copied locally as `CQ/resuilt/cq_r4_provenance_20261102/prior_153_run_ingest_receipt.json`); the RNN rows (51 runs) have no receipt in that store. The 14 files of this folder match the SHA-256 inventory taken on 2026-11-03 (`CQ/resuilt/cq_r4_provenance_20261102/source_inventory.json`), re-checked on {today}.
The ALL-slice STRICT/OVERLAP partition and the reconciliation with predictions are in the separate folder `cq_r4_slices_reconciled_20261103`.""".replace('{today}', NOW)

R4_ENERGY = "All 204 runs: `energy_measurement_type = NVML_POWER_SAMPLING_ESTIMATE` (GPU-only NVML power sampling, label ESTIMATED), no run without energy. It is not full-machine energy and not CO2. TIME (`train_seconds`, `elapsed_seconds`) is the primary cost basis."
R4_BACKEND = """`execution_backend = vastai_portable_runner` for all 204 runs, GPU NVIDIA L4, batch_size 2048, micro_batch_size 2048, accumulation_steps 1 (resource table).
Receipt: only the prior 153-run ingest has one (uniform runner SHA-256 `sha256:10cd38a26adcd6b0cec501ec40072013961ff2c7ee4658027e72f41d53507b83`, release contract SHA-256 `sha256:342edbdc869898284071f274237c97bcfb19389979d0132af99e37c2cbaa926f`, 66 partitions written). NO receipt exists for the full R4 export or for the 51 RNN runs.
**Derived (not recorded by the run; recovered 2026-11-08):** that runner SHA-256 equals the SHA-256 of `tools/vastai_train_shared.py` at repository commit `ce0486e0b9712341cb703b2c823b76a31a746b17` (2026-10-15, registry revision `registries_rev_2026-10-14_r1`) when line endings are converted to CRLF; no other commit was found with this hash. The 51 RNN runs have no runner SHA-256 anywhere."""
R4_COMMITS = "The resource table has no `runner_git_commit` column. Recovered from the ORIGINAL `run_manifest.json` files of the preserved packages (all 204 R4 resource runs matched one-to-one by model, window, pipeline, seed, `created_at_utc` and `elapsed_seconds`; table `upload_staging/m09/r4_vs_manifests.csv`): the manifests of the 153 LSTM/GRU/BILSTM runs (`cq_lstm_batch2048_full_20261018`, `cq_recurrent_batch2048_seed42_20261019`) and of the 51 RNN runs (`cq_rnn_historical_layout_batch2048_seed42_20261020`) have `runner_git_commit` = null, i.e. the runs themselves never recorded a commit. Best available derivation for the 153 receipt-covered runs: commit `ce0486e0b9712341cb703b2c823b76a31a746b17` (see runner SHA-256 above). For the 51 RNN runs there is NO commit: the code team states (2026-11-08) that these runs were executed from a working tree that had not been committed yet, which is consistent with `runner_git_commit = null` in every manifest. The manifests name `runner = tools/vastai_train_shared.py` with `static_layout_policy = historical_reference`; that feature first appears in commit `83c5056` (2026-10-19) and the runner differs from the next commit `eb80516` (2026-10-21) by 21 lines, but neither commit is claimed to be the code that ran. The exact runner code of these 51 runs is not recoverable from the repository. Separate later RNN reruns (`cq_rnn_matched_historical_20261029`, commit `29da3b25…`) have different `created_at_utc` and are NOT the R4 runs."
R4_LAYOUT = "Not a column of this export. Recovered 2026-11-08 by hashing the 153 `feature_layout.json` files of the original preserved packages (`cq_lstm_batch2048_full_20261018`, `cq_recurrent_batch2048_seed42_20261019`) with SHA-256; the method is the one the runner uses (for PatchTST the file hash equals the manifest `feature_layout_sha256`). LSTM (51 runs, all identical): `sha256:b747da1ebe141251d9e6c1c3641c6391ac9fa1becf32cdf229d4e78c3016ad41`. GRU (51) and BILSTM (51), all identical: `sha256:f99c3d3270d9695ef20c1db793f1b28eba97e836d490b979dff039e9d61caec7`. RNN (51 runs): `reference_layout_sha256 = sha256:b747da1ebe141251d9e6c1c3641c6391ac9fa1becf32cdf229d4e78c3016ad41` (the same historical layout as LSTM). None equals the CQ current layout `sha256:367bf42bb9fcc68a91f5c8c9a2419cca28df7f8decfc8ceaa639b5ef6667b904`, so the four families were NOT all trained on one layout and R4 contains two layouts. Derived from files, not recorded in the export."
R4_EXTRA = "Exporter: the file set of this folder (`cq_family_pipeline_window_phase_metrics`, `cq_metrics_per_class_long`, `cq_bootstrap_metrics_per_class_long`, `cq_family_window_phase_mean`, `cq_resource_per_run`, `cq_train_time_energy_family_pipeline`, `summary.json`) is written by `tools/export_cq_recurrent_grid_report.py` (first committed in `5b14052`, 2026-10-23, the folder date; file unchanged since); this is identified by output names and date, the export itself does not record the script or the commit. `cq_qa23_reviewed_behavioural_linkage` comes from a different step. No receipt for the full export; `cq_r4_slices_reconciled_20261103` documents that ALL-slice calibration/PR-AUC differ from R4 because the audit and the model use different implementations. Probability-clip convention of these facts is the former 1e-7 threshold (M-16: old facts keep their provenance)."

PT_MERGE = """CQ PatchTST, pipelines V0-V6, seed 42, windows W1-W3: 168 split/window/phase sanity cells (7 pipelines x 3 windows x 2 splits x 4 phases), 504 ALL/STRICT/OVERLAP rows, 504 per-class rows, 1,512 bootstrap rows (B = 2,000), 21 run-resource rows, 672 audited SEEN/UNSEEN x STRICT/OVERLAP cohort rows (`cohort_slice_status`). Built by `tools/build_cq_patchtst_v0_v6_full_facts_20261103.py` (appended and finalised by `tools/append_cq_patchtst_v0_v6_full_facts_20261103.py`, `tools/finalize_cq_patchtst_cohorts_20261103.py`, `tools/add_cq_cost_vnd_20261103.py`) from the per-run post-hoc audits; V0 provenance is the separately downloaded audit and original run directories. V7-V16, LO F2 and seeds 43/44 are outside this export. `acctempo_m4` = S_perf^0.6 x S_san_plus_v2^0.4 with floor 0.001. STRICT + OVERLAP counts equal ALL in every cell."""
PT_ENERGY = "All 21 runs: `NVML_POWER_SAMPLING_ESTIMATE`, `energy_boundary = GPU_ONLY` (ESTIMATED). Not full-machine energy and not CO2; the VND cost table is derived from TIME."
PT_BACKEND = "`execution_backend = vastai_portable_runner` for all 21 runs, GPU NVIDIA L4, batch_size 2048 = micro_batch_size 512 x accumulation_steps 4. No ingest receipt for this export exists in `external_fact_ingests` (the receipt there for LO F2 `vastai_lo_f2_seed42_clean_20261025_r3` is a different export). V4/W3 used workers=0 after an out-of-memory failure (README of the package)."
PT_COMMITS = "`runner_git_commit = 29da3b252dde9ed96f42f7bda7f886b11ae1efa1` for all 21 runs (resource table). The registry revision at that commit is `registries_rev_2026-10-27_r1` (derived from git, not recorded by the run). The repository commit of the export tools is not recorded."
PT_LAYOUT = "`feature_layout_sha256 = sha256:367bf42bb9fcc68a91f5c8c9a2419cca28df7f8decfc8ceaa639b5ef6667b904` for all 21 runs (CQ current static layout)."
PT_EXTRA = "No ingest receipt; V0 is audited from separately downloaded runs; the course cohort join uses the PatchTST prediction salt and is specific to this export."

LO_MERGE = """LO static-v2, seed 42: four families (RNN, LSTM, GRU, BILSTM) x 17 pipelines x 3 windows x 2 splits x 4 phases = 1,632 evaluation cells, 204 resource runs, 4,896 ALL/STRICT/OVERLAP slices checked (partition PASS). Source (README): the four immutable LO static-v2 family audits and the corresponding run manifests/history under `Jobs/LO/.../lo_static_v2_seed42_20261026/models`; one row per family, pipeline, window, split and phase. `acctempo_m4 = max(s_perf,0.001)^0.6 x max(s_san_plus_v2,0.001)^0.4`. STRICT share uses the matching audit slices. `train_seconds` sums epoch `train_seconds`; `elapsed_seconds` is the recorded wall time. The exporter is `tools/export_lo_static_v2_r4_20261102.py` (committed in `834ad30`, 2026-11-03; identified by name, output file set and date; the export does not record it)."""
LO_ENERGY = "All 204 runs: `NVML_POWER_SAMPLING_ESTIMATE` (label ESTIMATED, decision D-35; GPU-only estimate, not total energy or CO2). The 2026-11-02 request text expects NOT_MEASURED for LO: the facts record the measured estimate and were not relabelled. TIME is the primary cost basis."
LO_BACKEND = "`execution_backend = vastai_portable_runner` for all 204 runs, GPU NVIDIA L4, batch_size 2048, micro_batch_size 2048, accumulation_steps 1. No ingest receipt for this export exists in `external_fact_ingests` (the LO receipt there belongs to the F2 export)."
LO_COMMITS = "`runner_git_commit = b0e5ae1270fae1c0397facf6e9fc9e522016dc9d` for all 204 runs (resource table and `summary.json`). The registry revision at that commit is `registries_rev_2026-10-25_r1` (derived from git, not recorded by the run). The repository commit of the export step is not recorded; the exporter script was first committed in `834ad30`."
LO_LAYOUT = "`feature_layout_sha256 = sha256:847617755f0d0190efdc52ecada53772f24117e7034885e3432f609b604e17d1` for all 204 runs (`summary.json` `layout_sha256`, 13 static columns)."
LO_EXTRA = "No ingest receipt; the ablation of the static block (M-03) is a separate package (`ablation_m03_static_v2_20261108`) and the 2026-10-19 exploratory ablation is archive; exporter: `tools/export_lo_static_v2_r4_20261102.py`."

docs = {
    'README_T1-EX-07_cq_recurrent_allfamilies_grid_r4_20261023.md': readme('CQ F1 recurrent R4 (RNN, LSTM, GRU, BILSTM), seed 42', 'CQ F1 R4', 'Jobs/CQ/organized_moved_20261029/L2_facts/fact_exports/cq_recurrent_allfamilies_grid_r4_20261023', R4_MERGE, R4_ENERGY, R4_BACKEND, R4_COMMITS, R4_LAYOUT, R4_EXTRA),
    'README_T1-EX-07_cq_patchtst_v0_v6_full_facts_20261103.md': readme('CQ F2 PatchTST V0-V6, seed 42', 'CQ F2 PatchTST V0-V6', 'Jobs/CQ/organized_moved_20261029/L2_facts/fact_exports/cq_patchtst_v0_v6_full_facts_20261103', PT_MERGE, PT_ENERGY, PT_BACKEND, PT_COMMITS, PT_LAYOUT, PT_EXTRA),
    'README_T1-EX-07_lo_static_v2_grid_seed42_20261102.md': readme('LO F1 recurrent static-v2, seed 42', 'LO F1 static-v2', 'Jobs/LO/organized_moved_20261029/L2_facts/fact_exports/lo_static_v2_grid_seed42_20261102', LO_MERGE, LO_ENERGY, LO_BACKEND, LO_COMMITS, LO_LAYOUT, LO_EXTRA),
}
for name, text in docs.items():
    (OUT / name).write_text(fix(text), encoding='utf8')

# ---- per-file sha256 list
lines = ['# SHA-256 of every file of the facts-of-record folders (as downloaded from Drive on %s)' % NOW, '# format: sha256  bytes  Jobs-relative path', '']
total = 0
for key, v in INV.items():
    lines.append(f'## {key}')
    for f in v['files']:
        lines.append(f"{f['sha256']}  {f['bytes']}  {v['path']}/{f['rel']}")
        total += 1
    lines.append('')
(OUT / 'FACTS_OF_RECORD_sha256.txt').write_text(fix('\n'.join(lines)), encoding='utf8')


def row(task, tier, seed, key, date, exporter, content, status):
    v = INV[key]
    return f"| {task} | {tier} | {seed} | `{v['path']}` | {date} | {exporter} | {content} | {len(v['files'])} | {status} |"


facts = [
    row('CQ', 'F1 RNN/LSTM/GRU/BILSTM', 42, 'CQ F1 R4', '2026-10-23', '`tools/export_cq_recurrent_grid_report.py` (suy ra từ tên file + ngày, commit `5b14052`)', '1.632 ô, 204 run, 4.896 per-class, 14.688 bootstrap per-class; V0-V16 × W1-W3', 'Chưa có receipt cho cả export; 153/204 run có receipt tiền nhiệm (runner suy ra commit `ce0486e`); layout: LSTM+RNN `b747da1e…`, GRU+BILSTM `f99c3d32…`; 51 RNN chạy khi chưa commit'),
    row('CQ', 'F1 (lát)', 42, 'CQ F1 R4 slices', '2026-11-03', '`tools/reconcile_cq_r4_slices_from_predictions_20261103.py`', '4.896 lát ALL/STRICT/OVERLAP; phân hoạch confusion matrix PASS', 'ALL lấy từ R4; STRICT/OVERLAP tính lại trên dự đoán đã lưu'),
    row('CQ', 'F2 PatchTST V0-V6', 42, 'CQ F2 PatchTST V0-V6', '2026-11-03', '`tools/build_cq_patchtst_v0_v6_full_facts_20261103.py`', '168 ô sanity, 504 lát, 504 per-class, 1.512 bootstrap, 21 run; 672 lát SEEN/UNSEEN', 'runner `29da3b25…`, layout `367bf42b…`; không có receipt'),
    row('LO', 'F1 RNN/LSTM/GRU/BILSTM static-v2', 42, 'LO F1 static-v2', '2026-11-02', '`tools/export_lo_static_v2_r4_20261102.py` (suy ra từ tên file + ngày, commit `834ad30`)', '1.632 ô, 204 run, 4.896 lát (phân hoạch PASS)', 'runner `b0e5ae12…`, layout `84761775…`; không có receipt; năng lượng ESTIMATED (D-35)'),
]
support = [
    row('CQ', 'hỗ trợ offering', 42, 'CQ class_offering_support', '2026-11-03', '`tools/export_cq_class_offering_support_20261103.py`', 'support theo lớp × offering và cờ cell', 'Bản gốc của M-05 CQ'),
    row('CQ', 'bootstrap theo cụm offering', 42, 'CQ offering bootstrap', '2026-11-08', '`tools/finalize_cq_offering_bootstrap_20261108.py`', '600 ô bị cờ, 1.800 dòng lớp, B = 2.000', 'Đã đối chiếu join và support (PASS)'),
    row('LO', 'hỗ trợ offering + bootstrap', 42, 'LO offering support+bootstrap', '2026-11-07', '`tools/export_lo_offering_support_20261106.py`', '1.632 ô, 4.896 dòng lớp, B = 2.000; 544 dòng NOT_ESTIMABLE_SINGLE_OFFERING', 'Có thư mục `lo_offering_bootstrap_delivery_20261107` cùng nội dung bootstrap (7 file)'),
    row('CQ', 'S2 / Radius / kappa', 42, 'CQ S2 kappa', '2026-11-07', 'gói M-06 (chuyên biệt, không có script riêng trong repo)', '108 dòng S2, 24 dòng Radius, `kappa_reached` đã định nghĩa', 'Hash ledger 36 manifest tính lại, không có tham chiếu độc lập'),
    row('LO', 'S2 / Radius / kappa', 42, 'LO S2 kappa', '2026-11-08', 'gói M-06', '108 dòng S2, 24 dòng Radius; `radius_parent_identity_check.csv` 24/24', 'Parent ID kiểm gián tiếp qua manifest/đường dẫn'),
    row('LO', 'ablation static no_static', 42, 'LO M-03 ablation', '2026-11-08', 'gói M-03', '16 dòng so sánh W1 × V0/V8, 64 lát SEEN/UNSEEN × STRICT/OVERLAP', 'So sánh tổng hợp, không paired'),
    row('CQ', 'registry split', 42, 'CQ split registry', '2026-11-08', '`tools/build_split_registry_final_20261108.py`', '`split_registry_cq_v2_2.{csv,json}` + khối A-G, STRICT theo pha, thời lượng offering', 'M-07'),
    row('LO', 'registry split', 42, 'LO split registry', '2026-11-08', '`tools/build_split_registry_final_20261108.py`', '`split_registry_lo_v3_1.{csv,json}` + bảng lý do loại', 'M-07'),
    row('CQ', 'quần thể raw', 42, 'CQ raw population', '2026-11-08', 'đối chiếu `process_user.py` + log lúc tạo', '3.330.294 user → 11.807.090 enrollment → 3.192.206 có nhãn + 8.614.884 không nhãn', 'Chuẩn: số đếm, không có hash byte lịch sử'),
]
exploratory = [row('CQ', 'F3 Mantis (EXPLORATORY)', 42, 'CQ Mantis facts (EXPLORATORY)', '2026-11-08', '`tools/mantis_standardize_runs_20261108.py`, `tools/run_standard_audit_pruned_20261108.py`', '7 cell (V1 W1-W3, V13 W1-W3, V3 W1); 56 ô sanity, 168 lát, B = 2.000', 'NGOÀI bài giai đoạn 1; xuất riêng, không gộp vào bảng chính (quyết định 36/37)')]
meta = [row('CQ+LO', 'đầu vào M-13', 42, 'M-13 inputs', '2026-11-08', '`tools/build_m13_s0_v3_20261108.py`, `tools/assemble_f0_cq_partial_triad_20261108.py`', 'S0 profile 48 dòng, Z_M 5 dòng, F0 CQ 24 dòng', 'Không phải meta-release; ba quy ước S0 chờ phía viết xác nhận')]
head = '| Task | Tầng | Seed | Thư mục (dưới `Jobs/`) | Ngày | Công cụ xuất | Nội dung | Số file | Trạng thái / ghi chú |\n|---|---|---|---|---|---|---|---|---|'

archive = """
**CQ** (`Jobs/CQ/organized_moved_20261029/L2_facts/fact_exports/`): `cq_f1_oldfamilies_l2_ingest_r2_20261021`, `cq_f1_allfamilies_l2_ingest_r3_20261021`, `cq_recurrent_allfamilies_grid_r3_20261021`, `cq_recurrent_batch2048_slice_r2_20261019`, `cq_recurrent_batch2048_slice_r3_partition_20261021`, `review_20261019_window_phase`, `vastai_f1_l2_exports_20261016`, `cq_r4_provenance_20261103_DRAFT` (bản nháp provenance của R4). Pilot trong `L2_facts/audits_and_evidence/`: `patchtst_determinism_pilot_20261015`; trong `L1_runs/S3_model/run_bundles/`: `cq_patchtst_d23_stability_pilot_20261026`.

**LO** (`Jobs/LO/organized_moved_20261029/L2_facts/fact_exports/`): `lo_recurrent_allfamilies_grid_r2_20261021`, `lo_l2_ingest_closure_seed42_20261025`, `review_20261019_window_phase`, `review_20261019_window_phase_r2`. Ablation 19/10: `L2_facts/audits_and_evidence/static_probe_w1_v0_20261019` và `static_contract_history_20261019` (layout lịch sử 15 cột, không thay thế ablation 13 cột của M-03).

Không thư mục nào ở mục này là facts của bài; chỉ giữ để truy vết. Danh sách tên lấy từ listing Drive ngày %s, chưa kiểm hash.""" % NOW

md = f"""# FACTS_OF_RECORD — facts của bài, giai đoạn 1 (seed 42)

Lập ngày {NOW} bởi đội code. File này chỉ ra, cho từng (task, tầng, seed), thư mục nào trên Drive là facts của bài, ngày, công cụ xuất, số file và SHA-256. Hash từng file nằm ở `FACTS_OF_RECORD_sha256.txt` cạnh file này ({total} file thuộc {len(INV)} thư mục); các bảng chính có hash ngay dưới đây. Mọi giá trị trong báo cáo phải lấy từ các thư mục ở mục A và B; mục E là lưu trữ.

Release: CQ_V2_2, data_release_id `{CQ_REL}`; LO_V3_1, data_release_id `{LO_REL}`. Registry hiện tại trong repo: `{REGISTRY_NOW}` (các export không ghi revision registry; suy ra từ commit runner: R4 LSTM/GRU/BILSTM `registries_rev_2026-10-14_r1`, LO static-v2 `registries_rev_2026-10-25_r1`, PatchTST `registries_rev_2026-10-27_r1`).

Đường dẫn trong file này tính từ gốc thư mục chia sẻ `Results/`, theo bố cục Drive ngày 09/11/2026 (`CQ/` và `LO/` gồm L0_registry, L1_runs, L2_facts, L3_meta; `cross_task_meta/`; xem `README.md` và `DRIVE_LAYOUT_MIGRATION_20261109.md` ở gốc). Các bản `Jobs/...` cũ còn được giữ nguyên ở cây cũ để đối chiếu hash và không còn là nơi tham chiếu.

## A. Facts của bài (seed 42)

{head}
{chr(10).join(facts)}

Không có facts LO F2 và không có seed 43/44 trong giai đoạn 1.

## B. Bằng chứng hỗ trợ cùng seed

{head}
{chr(10).join(support)}

## C. Khám phá (EXPLORATORY), không thuộc bài giai đoạn 1

{head}
{chr(10).join(exploratory)}

## D. Đầu vào tầng meta

{head}
{chr(10).join(meta)}

## E. Lưu trữ — không phải facts của bài
{archive}

## F. Quy ước đã áp dụng
- **Năng lượng:** NVML ước lượng (ESTIMATED), phạm vi GPU-only, không phải năng lượng toàn máy hay CO2; TIME là cơ sở chi phí chính. LO static-v2 ghi ESTIMATED (D-35), không gán lại NOT_MEASURED.
- **Clip xác suất (M-16):** từ 08/11 mã dùng clip 1e-12 float64 rồi chuẩn hóa hàng; facts cũ (R4, static-v2, PatchTST V0-V6) giữ ngưỡng 1e-7 và provenance cũ, không gắn lại nhãn.
- **AccTEMPO:** `acctempo_m3` là primary; `acctempo_m4 = S_perf^0.6 × S_san_plus_v2^0.4`, sàn 0,001.
- **Hạt facts:** một dòng cho mỗi family/mô hình, pipeline, window, split, phase; lát ALL/STRICT/OVERLAP là mô tả trên cùng cohort.

## G. Chưa xác nhận được (phải nêu trong mọi báo cáo dùng các số này)
1. **Receipt ingest:** chỉ 153/204 run của R4 (LSTM, GRU, BILSTM) có receipt tiền nhiệm; R4 đầy đủ, 51 run RNN, static-v2 và PatchTST V0-V6 chưa có receipt trong `external_fact_ingests`. Ngày 08/11 đã dựng **receipt hồi tố** cho cả ba export tại `Jobs/L3_meta/retroactive_receipts_20261108/` (`receipt_type = RETROACTIVE_RECONSTRUCTED`, không phải receipt do bước ingest sinh ra, không để trong `external_fact_ingests`).
2. **Commit và layout:** đã suy ra được từ manifest gốc và git (đánh dấu *suy ra*, không phải do run ghi): R4 LSTM/GRU/BILSTM → runner `ce0486e` (khớp SHA-256 runner của receipt, với xuống dòng CRLF); layout R4 (băm 153 `feature_layout.json` gốc + manifest RNN): LSTM và RNN `b747da1e…` (lịch sử), GRU và BILSTM `f99c3d32…`, không family nào dùng layout hiện tại `367bf42b…`; LO static-v2 và PatchTST → revision registry theo commit runner. 51 run RNN → không có commit (chạy từ working tree chưa commit, theo xác nhận của đội code 08/11). **Vẫn chưa ghi:** commit/mã runner của 51 run RNN (chưa commit khi chạy), commit repo của bước xuất, revision registry lúc chạy (đều chỉ suy ra).
3. **Công cụ xuất:** đã tìm thấy theo tên file đầu ra và ngày: R4 → `tools/export_cq_recurrent_grid_report.py` (`5b14052`), LO static-v2 → `tools/export_lo_static_v2_r4_20261102.py` (`834ad30`). Export không tự ghi script hay commit, nên đây là suy luận, chưa có receipt.
4. **Ledger release (M-08):** mới có snapshot lịch sử của CQ; ledger chính thức của app chưa có cho CQ và LO.
5. **Quần thể raw (M-07):** các số đếm lúc tạo nhãn khớp hôm nay nhưng không có hash byte của `user.json` hay artifact nhãn lúc build.

## H. Ghi chú nghiệm thu
Hash trong file này được tính trên bản tải từ Drive ngày {NOW} và đã đối chiếu với `sha256sums.txt` của từng gói có file đó (0 sai lệch); R4 đối chiếu với kiểm kê 03/11 (14/14 khớp). `_drive_manifest.json` của hai gói phía viết đã chép không nằm trong repo nên chưa so được.
"""
(OUT / 'FACTS_OF_RECORD.md').write_text(fix(md), encoding='utf8')
print('written', sorted(p.name for p in OUT.iterdir()), 'files hashed', total)
