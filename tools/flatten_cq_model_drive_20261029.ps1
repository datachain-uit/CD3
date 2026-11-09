$ErrorActionPreference = 'Stop'
$root='G:\My Drive\Jobs\CQ\organized_moved_20261029\L1_runs'
$paths=@(
 'preserved_packages\cq_rnn_historical_layout_batch2048_seed42_20261020\CQ',
 'preserved_packages\cq_lstm_batch2048_full_20261018\lstm\CQ',
 'preserved_packages\cq_recurrent_batch2048_seed42_20261019\bilstm\CQ',
 'preserved_packages\cq_recurrent_batch2048_seed42_20261019\gru\CQ',
 'run_bundles\cq_patchtst_d23_stability_pilot_20261026\CQ'
)
foreach ($path in $paths) {
 $base=Join-Path $root $path
 if (-not (Test-Path -LiteralPath $base)) { Write-Output "SKIP_MISSING $base"; continue }
 foreach ($window in Get-ChildItem -LiteralPath $base -Directory | Where-Object { $_.Name -match '^W[123]$' }) {
  foreach ($version in Get-ChildItem -LiteralPath $window.FullName -Directory | Where-Object { $_.Name -match '^V\d+$' }) {
   $models=@(Get-ChildItem -LiteralPath $version.FullName -Directory | Where-Object { $_.Name -in @('RNN','LSTM','GRU','BILSTM','PATCHTST') })
   if ($models.Count -ne 1) { Write-Output "SKIP_AMBIGUOUS $($version.FullName)"; continue }
   $nested=$models[0]
   foreach ($entry in Get-ChildItem -LiteralPath $nested.FullName -Force) {
    $dest=Join-Path $version.FullName $entry.Name
    if (Test-Path -LiteralPath $dest) { throw "Collision: $dest" }
    Move-Item -LiteralPath $entry.FullName -Destination $dest
    if (-not (Test-Path -LiteralPath $dest)) { throw "Missing: $dest" }
   }
   if (@(Get-ChildItem -LiteralPath $nested.FullName -Force).Count -eq 0) { Remove-Item -LiteralPath $nested.FullName -Force }
  }
  Write-Output "FLATTENED $path/$($window.Name)"
 }
}
Write-Output 'CQ_FLATTEN_COMPLETE'
