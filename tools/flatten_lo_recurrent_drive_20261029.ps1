$ErrorActionPreference = 'Stop'
$root = 'G:\My Drive\Jobs\LO\organized_moved_20261029\L1_runs\run_bundles\lo_static_v2_seed42_20261026\models'
foreach ($family in @('RNN','LSTM','GRU')) {
 $base=Join-Path $root "$family\runs"
 foreach ($window in Get-ChildItem -LiteralPath $base -Directory) {
  foreach ($version in Get-ChildItem -LiteralPath $window.FullName -Directory) {
   $nested=Join-Path $version.FullName $family
   if (-not (Test-Path -LiteralPath $nested)) { throw "Missing: $nested" }
   foreach ($entry in Get-ChildItem -LiteralPath $nested -Force) {
    $dest=Join-Path $version.FullName $entry.Name
    if (Test-Path -LiteralPath $dest) { throw "Collision: $dest" }
    Move-Item -LiteralPath $entry.FullName -Destination $dest
    if (-not (Test-Path -LiteralPath $dest)) { throw "Move failed: $dest" }
   }
   if (@(Get-ChildItem -LiteralPath $nested -Force).Count -ne 0) { throw "Not empty: $nested" }
   Remove-Item -LiteralPath $nested -Force
  }
  Write-Output "FLATTENED $family/$($window.Name)"
 }
}
Write-Output 'LO_RECURRENT_FLATTEN_COMPLETE'
