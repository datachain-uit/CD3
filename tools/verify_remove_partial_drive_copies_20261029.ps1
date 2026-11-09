$ErrorActionPreference = 'Stop'
$rclone = 'C:\Users\manndm\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe'
$root = 'G:\My Drive\Jobs\CQ\organized_results_20261029'
$items = @(
 @('L1_runs\cq_patchtst_v0_seed42_20261023','L1_runs\run_bundles\cq_patchtst_v0_seed42_20261023'),
 @('L1_runs\cq_patchtst_d23_stability_pilot_20261026','L1_runs\run_bundles\cq_patchtst_d23_stability_pilot_20261026'),
 @('L1_runs\cq_rnn_replay_protocol27_20261029','L1_runs\run_bundles\cq_rnn_replay_protocol27_20261029'),
 @('L2_facts\cq_f1_allfamilies_l2_ingest_r3_20261021','L2_facts\fact_exports\cq_f1_allfamilies_l2_ingest_r3_20261021'),
 @('evidence_packages\audit_prefix_validation_alignment_v1_20261017','L2_facts\audits_and_evidence\audit_prefix_validation_alignment_v1_20261017'),
 @('evidence_packages\cq_batch2048_closure_audit_20261019','L2_facts\audits_and_evidence\cq_batch2048_closure_audit_20261019'),
 @('evidence_packages\cq_f1_oldfamilies_l2_ingest_r2_20261021','L2_facts\fact_exports\cq_f1_oldfamilies_l2_ingest_r2_20261021')
)
foreach ($item in $items) {
 $source = Join-Path $root $item[0]
 $sourceRemote = 'gdrive:Jobs/CQ/organized_results_20261029/' + $item[0].Replace('\','/')
 $destRemote = 'gdrive:Jobs/CQ/organized_moved_20261029/' + $item[1].Replace('\','/')
 if (-not (Test-Path -LiteralPath $source)) { throw "Missing source $source" }
 & $rclone check $sourceRemote $destRemote --one-way --checkers 8 --log-level NOTICE
 if ($LASTEXITCODE -ne 0) { Write-Output "KEEP_DIFFERENT $source"; continue }
 $resolved = (Resolve-Path -LiteralPath $source).Path
 if (-not $resolved.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe path $resolved" }
 Remove-Item -LiteralPath $resolved -Recurse -Force
 Write-Output "REMOVED_VERIFIED_DUPLICATE $resolved"
}
Write-Output 'PARTIAL_DUPLICATE_CHECK_COMPLETE'
