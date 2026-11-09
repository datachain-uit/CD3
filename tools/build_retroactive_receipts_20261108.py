"""Retroactive (reconstructed) ingest receipts for the CQ R4, CQ PatchTST V0-V6 and LO static-v2 exports.

These are NOT receipts produced by the ingest step. They are dated 2026-11-08, rebuilt from the files of each export,
the original run manifests and git, and every field carries its provenance.
"""
import glob
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

OUT = Path('CQ/resuilt/retroactive_receipts_20261108')
OUT.mkdir(parents=True, exist_ok=True)
NOW = datetime.now(timezone.utc).isoformat()
INV = json.load(open('upload_staging/m09/inventory.json'))
CQ_REL = 'sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045'
LO_REL = 'sha256:2edf8cc293044d29c360cb2db71b8d21e26e2187cf40c6d45266f342a826d35b'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def vc(s):
    return {str(k): int(v) for k, v in s.value_counts(dropna=False).items()}


def base(key, ingest_id, task, release, rid, resource, exporter, exporter_commit, derived, not_recorded):
    inv = INV[key]
    local = Path(inv['local'].replace(chr(92), '/'))
    res = pd.read_parquet(local / resource)
    summ = json.load(open(local / 'summary.json', encoding='utf8')) if (local / 'summary.json').exists() else {}
    obs = {
        'resource_rows': len(res),
        'models': vc(res['model_name']) if 'model_name' in res else None,
        'execution_backend': vc(res['execution_backend']) if 'execution_backend' in res else 'COLUMN_ABSENT',
        'gpu': vc(res['gpu']) if 'gpu' in res else 'COLUMN_ABSENT',
        'energy_measurement_type': vc(res['energy_measurement_type']) if 'energy_measurement_type' in res else 'COLUMN_ABSENT',
        'created_at_utc_min': str(res['created_at_utc'].min()) if 'created_at_utc' in res else 'COLUMN_ABSENT',
        'created_at_utc_max': str(res['created_at_utc'].max()) if 'created_at_utc' in res else 'COLUMN_ABSENT',
        'runner_git_commit': vc(res['runner_git_commit']) if 'runner_git_commit' in res else 'COLUMN_ABSENT',
        'feature_layout_sha256': vc(res['feature_layout_sha256']) if 'feature_layout_sha256' in res else 'COLUMN_ABSENT',
    }
    rec = {
        'receipt_type': 'RETROACTIVE_RECONSTRUCTED',
        'warning': 'Not produced by the ingest step. Rebuilt on 2026-11-08 from the export files, the original run manifests and git history; it does not replace and must not be filed in external_fact_ingests.',
        'ingest_id_proposed': ingest_id,
        'created_at_utc': NOW,
        'task': task, 'release_id': release, 'data_release_id': rid, 'seed': 42,
        'export_folder': inv['path'],
        'export_file_count': len(inv['files']),
        'export_files': [{'path': f['rel'], 'bytes': f['bytes'], 'sha256': f['sha256']} for f in inv['files']],
        'summary_json': summ,
        'observed_in_export': obs,
        'exporter': {'script': exporter, 'first_commit': exporter_commit,
                     'script_sha256_current': sha(exporter) if exporter and Path(exporter).exists() else None,
                     'basis': 'identified by output file names and date; not recorded by the export'},
        'derived_from_other_sources': derived,
        'not_recorded': not_recorded,
    }
    return rec


R4_MAN = pd.read_csv('upload_staging/m09/r4_vs_manifests.csv')
_k = ['model_name', 'window_id', 'pipeline_id', 'seed']
_ok = R4_MAN[R4_MAN.same_created & R4_MAN.same_elapsed]
r4_match = {'r4_runs': 204,
            'runs_with_a_manifest_of_identical_created_at_utc_and_elapsed_seconds': int(_ok.drop_duplicates(_k).shape[0]),
            'manifests_by_package_for_those_runs': vc(_ok.pkg),
            'note': 'one RNN run also appears in cq_rnn_baseline_drive_20261029 (same created_at_utc); cq_rnn_matched_historical_20261029 is a later rerun of the same key with a different created_at_utc and is not an R4 run'}
r4 = base('CQ F1 R4', 'cq_recurrent_allfamilies_grid_r4_20261023', 'CQ', 'CQ_V2_2', CQ_REL, 'cq_resource_per_run.parquet',
          'tools/export_cq_recurrent_grid_report.py', '5b14052',
          {
              'prior_receipt_153_runs': {'file': 'cq_r4_provenance_20261102/prior_153_run_ingest_receipt.json', 'ingest_id': 'vastai_cq_f1_batch2048_seed42_slice_r2_20261019',
                                         'runner_sha256': 'sha256:10cd38a26adcd6b0cec501ec40072013961ff2c7ee4658027e72f41d53507b83',
                                         'runner_commit_matching_that_sha256': 'ce0486e0b9712341cb703b2c823b76a31a746b17 (tools/vastai_train_shared.py with CRLF line endings; registry registries_rev_2026-10-14_r1)'},
              'run_manifest_match': r4_match,
              'feature_layout_sha256_by_family': {'LSTM': 'sha256:b747da1ebe141251d9e6c1c3641c6391ac9fa1becf32cdf229d4e78c3016ad41 (51 feature_layout.json files)',
                                                  'GRU': 'sha256:f99c3d3270d9695ef20c1db793f1b28eba97e836d490b979dff039e9d61caec7 (51 files)',
                                                  'BILSTM': 'sha256:f99c3d3270d9695ef20c1db793f1b28eba97e836d490b979dff039e9d61caec7 (51 files)',
                                                  'RNN': 'reference_layout_sha256 sha256:b747da1ebe141251d9e6c1c3641c6391ac9fa1becf32cdf229d4e78c3016ad41 (historical_reference, 51 manifests)'},
          },
          ['runner commit of the 51 RNN runs (run from an uncommitted working tree, confirmed by the code team 2026-11-08)',
           'repository commit of the export step', 'registry revision in force at run time',
           'original ingest receipt for the full 204-run export and for the 51 RNN runs'])
pt = base('CQ F2 PatchTST V0-V6', 'cq_patchtst_v0_v6_full_facts_20261103', 'CQ', 'CQ_V2_2', CQ_REL, 'resource_per_run.parquet',
          'tools/build_cq_patchtst_v0_v6_full_facts_20261103.py', None,
          {'runner_git_commit_recorded_in_manifests': '29da3b252dde9ed96f42f7bda7f886b11ae1efa1',
           'registry_revision_at_that_commit': 'registries_rev_2026-10-27_r1',
           'builder_chain': ['tools/build_cq_patchtst_v0_v6_full_facts_20261103.py', 'tools/append_cq_patchtst_v0_v6_full_facts_20261103.py',
                             'tools/finalize_cq_patchtst_cohorts_20261103.py', 'tools/add_cq_cost_vnd_20261103.py']},
          ['repository commit of the export tools', 'registry revision in force at run time (derived only)', 'original ingest receipt'])
lo = base('LO F1 static-v2', 'lo_static_v2_grid_seed42_20261102', 'LO', 'LO_V3_1', LO_REL, 'lo_resource_per_run.parquet',
          'tools/export_lo_static_v2_r4_20261102.py', '834ad30',
          {'runner_git_commit_recorded_in_manifests': 'b0e5ae1270fae1c0397facf6e9fc9e522016dc9d',
           'registry_revision_at_that_commit': 'registries_rev_2026-10-25_r1'},
          ['repository commit of the export step beyond the first commit of the script', 'registry revision in force at run time (derived only)', 'original ingest receipt'])

# first commit of the PatchTST builder, from git
import subprocess
for rec in (pt,):
    out = subprocess.run(['git', 'log', '--diff-filter=A', '--format=%h %ci', '--', rec['exporter']['script']], capture_output=True, text=True).stdout.strip().splitlines()
    rec['exporter']['first_commit'] = out[-1] if out else None

names = {'r4': (r4, 'retroactive_receipt_cq_recurrent_allfamilies_grid_r4_20261023.json'),
         'pt': (pt, 'retroactive_receipt_cq_patchtst_v0_v6_full_facts_20261103.json'),
         'lo': (lo, 'retroactive_receipt_lo_static_v2_grid_seed42_20261102.json')}
for k, (rec, fn) in names.items():
    (OUT / fn).write_text(json.dumps(rec, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf8')

readme = f"""# Retroactive ingest receipts (reconstructed) — {NOW[:10]}

**These are not original ingest receipts.** The three exports below were never ingested through `external_fact_ingests`, so no receipt was written when they were produced. Each file here was rebuilt on {NOW[:10]} by the code team from (a) the export folder itself (file list, bytes, SHA-256, row counts, resource table), (b) the original run manifests of the preserved packages, and (c) git history. They are kept in a separate folder and must not be filed in `external_fact_ingests`; `receipt_type = RETROACTIVE_RECONSTRUCTED`.

| Receipt | Export |
|---|---|
| `retroactive_receipt_cq_recurrent_allfamilies_grid_r4_20261023.json` | CQ F1 R4 (RNN, LSTM, GRU, BILSTM), 204 runs |
| `retroactive_receipt_cq_patchtst_v0_v6_full_facts_20261103.json` | CQ F2 PatchTST V0-V6, 21 runs |
| `retroactive_receipt_lo_static_v2_grid_seed42_20261102.json` | LO F1 static-v2, 204 runs |

Each receipt separates `observed_in_export` (read from the export), `derived_from_other_sources` (manifests/git, with basis) and `not_recorded` (cannot be recovered). In particular the 51 RNN runs of R4 were run from an uncommitted working tree (code team, {NOW[:10]}), so no runner commit exists for them.
"""
(OUT / 'README.md').write_text(readme, encoding='utf8')
lines = [f"{sha(p)}  {p.name}" for p in sorted(OUT.iterdir()) if p.name != 'sha256sums.txt']
(OUT / 'sha256sums.txt').write_bytes(('\n'.join(lines) + '\n').encode())
print([p.name for p in OUT.iterdir()])
for k, (rec, fn) in names.items():
    print(fn, rec['observed_in_export']['resource_rows'], rec['observed_in_export']['runner_git_commit'], rec['exporter']['first_commit'])
