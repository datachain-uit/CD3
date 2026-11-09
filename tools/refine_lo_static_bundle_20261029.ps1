$ErrorActionPreference = 'Stop'
$base = 'G:\My Drive\Jobs\LO\organized_moved_20261029\L1_runs\run_bundles\lo_static_v2_seed42_20261026'
$items = @(
 @('models\RNN\LO','models\RNN\runs'),@('models\LSTM\LO','models\LSTM\runs'),@('models\GRU\LO','models\GRU\runs'),
 @('models\BILSTM\_bilstm_metadata_20261029','models\BILSTM\metadata'),
 @('models\BILSTM\_bilstm_predictions','models\BILSTM\predictions'),
 @('audits\_closure_audit_temp','audits\closure_seed42'),
 @('replay\lo_rnn_replay_protocol27_seed42','replay\RNN_protocol27_seed42')
)
foreach ($m in $items) {
 $src=Join-Path $base $m[0]; $dst=Join-Path $base $m[1]
 if (-not (Test-Path -LiteralPath $src)) { throw "Missing: $src" }
 if (Test-Path -LiteralPath $dst) { throw "Destination exists: $dst" }
 Move-Item -LiteralPath $src -Destination $dst
 if (-not (Test-Path -LiteralPath $dst)) { throw "Move failed: $src" }
 Write-Output "RENAMED $($m[0]) -> $($m[1])"
}
