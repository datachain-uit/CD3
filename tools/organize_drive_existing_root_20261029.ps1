$ErrorActionPreference = 'Stop'
$root = 'G:\My Drive\Jobs'
$mapping = @(
 @('CQ','cq_lstm_batch2048_audit_20261018','L2_facts\audits_and_evidence'),
 @('CQ','cq_lstm_batch2048_full_20261018','L1_runs\preserved_packages'),
 @('CQ','cq_rnn_historical_layout_batch2048_seed42_20261020','L1_runs\preserved_packages'),
 @('CQ','cq_recurrent_batch2048_seed42_20261019','L1_runs\preserved_packages'),
 @('CQ','cq_prefix_audit_inputs_20261017','input_archives'),
 @('LO','vastai_audits','L2_facts\audits_and_evidence'),
 @('LO','radius_fallback_audit_v3_1_logs','L2_facts\audits_and_evidence'),
 @('LO','audit_prefix_validation_alignment_v1','L2_facts\audits_and_evidence'),
 @('LO','_checked_feature_v2','input_archives'),
 @('LO','radius_fallback_audit_v3_1_vastai_seed42','L2_facts\audits_and_evidence'),
 @('LO','vastai_runs','L1_runs\preserved_packages'),
 @('LO','vastai','L1_runs\preserved_packages'),
 @('LO','vastai_f2_batch2048_seed42_20261013','L1_runs\preserved_packages'),
 @('LO','vastai_f1_seed42_closure_20261013','L1_runs\preserved_packages')
)
foreach ($m in $mapping) {
 $src = Join-Path $root "$($m[0])\$($m[1])"
 $parent = Join-Path $root "$($m[0])\organized_moved_20261029\$($m[2])"
 $dst = Join-Path $parent $m[1]
 if (-not (Test-Path -LiteralPath $src)) { throw "Missing source: $src" }
 if (Test-Path -LiteralPath $dst) { throw "Destination exists: $dst" }
 New-Item -ItemType Directory -Path $parent -Force | Out-Null
 Move-Item -LiteralPath $src -Destination $dst
 if (-not (Test-Path -LiteralPath $dst) -or (Test-Path -LiteralPath $src)) { throw "Verification failed: $src" }
 Write-Output "MOVED $src -> $dst"
}
Write-Output 'ROOT_ORGANIZATION_COMPLETE'
