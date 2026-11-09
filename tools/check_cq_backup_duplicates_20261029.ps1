$ErrorActionPreference='Stop'
$rclone='C:\Users\manndm\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe'
$root='G:\My Drive\Jobs\CQ\backup_local_20261029\source_results'
$items=@(
 @('_checked_feature_v2','rclone_direct_20261029/source_results/_checked_feature_v2'),
 @('cq_prefix_audit_inputs_20261017','rclone_direct_20261029/source_results/cq_prefix_audit_inputs_20261017'),
 @('audit_prefix_validation_alignment_v1_20261017','organized_moved_20261029/L2_facts/audits_and_evidence/audit_prefix_validation_alignment_v1_20261017'),
 @('cq_batch2048_closure_audit_20261019','organized_moved_20261029/L2_facts/audits_and_evidence/cq_batch2048_closure_audit_20261019'),
 @('cq_f1_allfamilies_l2_ingest_r3_20261021','organized_moved_20261029/L2_facts/fact_exports/cq_f1_allfamilies_l2_ingest_r3_20261021'),
 @('cq_f1_oldfamilies_l2_ingest_r2_20261021','organized_moved_20261029/L2_facts/fact_exports/cq_f1_oldfamilies_l2_ingest_r2_20261021'),
 @('cq_full_prefix_static_audit_20261017','organized_moved_20261029/L2_facts/audits_and_evidence/cq_full_prefix_static_audit_20261017'),
 @('cq_lstm_batch2048_metadata_20261018','organized_moved_20261029/L2_facts/audits_and_evidence/cq_lstm_batch2048_metadata_20261018'),
 @('cq_patchtst_d23_stability_pilot_20261026','organized_moved_20261029/L1_runs/run_bundles/cq_patchtst_d23_stability_pilot_20261026'),
 @('cq_patchtst_v0_seed42_20261023','organized_moved_20261029/L1_runs/run_bundles/cq_patchtst_v0_seed42_20261023')
)
foreach($i in $items){
 $local=Join-Path $root $i[0]
 if(-not(Test-Path -LiteralPath $local)){continue}
 & $rclone check "gdrive:Jobs/CQ/backup_local_20261029/source_results/$($i[0])" "gdrive:Jobs/CQ/$($i[1])" --one-way --checkers 8 --log-level NOTICE
 if($LASTEXITCODE -ne 0){Write-Output "KEEP_UNVERIFIED $($i[0])";continue}
 $resolved=(Resolve-Path -LiteralPath $local).Path
 if(-not $resolved.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe target'}
 Remove-Item -LiteralPath $resolved -Recurse -Force
 Write-Output "REMOVED_VERIFIED_DUPLICATE $($i[0])"
}
Write-Output 'BACKUP_COMPARISON_COMPLETE'
