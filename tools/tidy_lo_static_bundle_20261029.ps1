$ErrorActionPreference = 'Stop'
$base = 'G:\My Drive\Jobs\LO\organized_moved_20261029\L1_runs\run_bundles\lo_static_v2_seed42_20261026'
$items = @(
 @('RNN','models'),@('LSTM','models'),@('GRU','models'),
 @('_bilstm_metadata_20261029','models\BILSTM'),@('_bilstm_predictions','models\BILSTM'),
 @('_closure_audit_temp','audits'),@('lo_rnn_replay_protocol27_seed42','replay'),
 @('LO_static_v2_GRU.tar','archives'),@('LO_static_v2_LSTM.tar','archives'),
 @('LO_static_v2_RNN.tar','archives'),@('LO_static_v2_closure_20261028.tar.gz','archives')
)
foreach ($file in Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Name -like 'LO_auto_download*' }) { $items += ,@($file.Name,'transfer_receipts_and_logs') }
foreach ($m in $items) {
 $src=Join-Path $base $m[0]; $parent=Join-Path $base $m[1]; $dst=Join-Path $parent $m[0]
 if (-not (Test-Path -LiteralPath $src)) { throw "Missing source: $src" }
 if (Test-Path -LiteralPath $dst) { throw "Destination exists: $dst" }
 New-Item -ItemType Directory -Path $parent -Force | Out-Null
 Move-Item -LiteralPath $src -Destination $dst
 if (-not (Test-Path -LiteralPath $dst)) { throw "Move failed: $src" }
 Write-Output "MOVED $($m[0]) -> $($m[1])"
}
Write-Output 'TIDY_COMPLETE'
