$ErrorActionPreference = 'Stop'
$root = 'G:\My Drive\Jobs\LO\organized_moved_20261029\L1_runs\run_bundles\lo_static_v2_seed42_20261026\models\BILSTM'
foreach ($kind in @('metadata','predictions')) {
 $base = Join-Path $root $kind
 $lo = Join-Path $base 'LO'
 foreach ($window in Get-ChildItem -LiteralPath $lo -Directory) {
  foreach ($version in Get-ChildItem -LiteralPath $window.FullName -Directory) {
   $model = Join-Path $version.FullName 'BILSTM'
   if (-not (Test-Path -LiteralPath $model)) { throw "Missing model folder: $model" }
   foreach ($seed in Get-ChildItem -LiteralPath $model -Force) {
    $dst = Join-Path $version.FullName $seed.Name
    if (Test-Path -LiteralPath $dst) { throw "Collision: $dst" }
    Move-Item -LiteralPath $seed.FullName -Destination $dst
    if (-not (Test-Path -LiteralPath $dst)) { throw "Missing after move: $dst" }
   }
   if (@(Get-ChildItem -LiteralPath $model -Force).Count -ne 0) { throw "Model folder not empty: $model" }
   Remove-Item -LiteralPath $model -Force
  }
  $target=Join-Path $base $window.Name
  if (Test-Path -LiteralPath $target) { throw "Collision: $target" }
  Move-Item -LiteralPath $window.FullName -Destination $target
  Write-Output "FLATTENED $kind/$($window.Name)"
 }
 if (@(Get-ChildItem -LiteralPath $lo -Force).Count -eq 0) { Remove-Item -LiteralPath $lo -Force }
}
Write-Output 'BILSTM_FLATTEN_COMPLETE'
