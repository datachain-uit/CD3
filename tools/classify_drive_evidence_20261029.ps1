$ErrorActionPreference = 'Stop'
$root = 'G:\My Drive\Jobs'
$runPattern = '(?i)baseline|matched_historical|replay_protocol|pilot_artifacts|historical_layout|nvml_audited|cohort_audit_nvml|runner_repair|static_ablation|static_v2_cohort'
foreach ($task in @('CQ','LO')) {
    $base = Join-Path $root "$task\organized_moved_20261029"
    $src = Join-Path $base 'evidence_packages'
    foreach ($item in Get-ChildItem -LiteralPath $src -Force) {
        $name = $item.Name
        if ($name -match '(?i)^test_prefix_views|^phase_views|^LO_V3_1_clean_grain') { $tier = 'input_archives' }
        elseif ($name -match $runPattern -or $name -match '(?i)^V0-.*\.zip$') { $tier = 'L1_runs\preserved_packages' }
        else { $tier = 'L2_facts\audits_and_evidence' }
        $parent = Join-Path $base $tier
        $dest = Join-Path $parent $name
        if (Test-Path -LiteralPath $dest) { throw "Destination exists: $dest" }
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        Move-Item -LiteralPath $item.FullName -Destination $dest
        if (-not (Test-Path -LiteralPath $dest) -or (Test-Path -LiteralPath $item.FullName)) { throw "Move failed: $name" }
        Write-Output "MOVED $task/$name -> $tier"
    }
}
Write-Output 'CLASSIFICATION_COMPLETE'
