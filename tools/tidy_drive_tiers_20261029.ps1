$ErrorActionPreference = 'Stop'
$root = 'G:\My Drive\Jobs'
foreach ($task in @('CQ','LO')) {
  $base = Join-Path $root "$task\organized_moved_20261029"
  foreach ($spec in @(@('L1_runs','run_bundles',@('preserved_packages','run_bundles')), @('L2_facts','fact_exports',@('audits_and_evidence','fact_exports')))) {
    $tierPath = Join-Path $base $spec[0]
    $bucket = Join-Path $tierPath $spec[1]
    foreach ($item in Get-ChildItem -LiteralPath $tierPath -Force) {
      if ($item.Name -in $spec[2]) { continue }
      New-Item -ItemType Directory -Path $bucket -Force | Out-Null
      $dest = Join-Path $bucket $item.Name
      if (Test-Path -LiteralPath $dest) { throw "Destination exists: $dest" }
      Move-Item -LiteralPath $item.FullName -Destination $dest
      if (-not (Test-Path -LiteralPath $dest)) { throw "Move failed: $dest" }
      Write-Output "MOVED $($item.FullName) -> $dest"
    }
  }
}
