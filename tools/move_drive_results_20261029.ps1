$ErrorActionPreference = 'Stop'
$root = 'G:\My Drive\Jobs'
foreach ($task in @('CQ','LO')) {
    $source = Join-Path $root "$task\rclone_direct_20261029\source_results"
    $destRoot = Join-Path $root "$task\organized_moved_20261029"
    foreach ($item in Get-ChildItem -LiteralPath $source -Force) {
        $name = $item.Name
        if ($name -match '(?i)(^private$|^input$|^transfer_logs$|^_checked_feature_v2$|audit_inputs|salt|secret|token|credential|^\.env)') { Write-Output "SKIP $task/$name"; continue }
        $tier = 'evidence_packages'
        if ($name -match '(?i)^lo_static_v2_seed42_20261026$|^cq_patchtst_v0_seed42_20261023$|^cq_patchtst_d23_stability_pilot_20261026$|^cq_rnn_replay_protocol27_20261029$') { $tier = 'L1_runs' }
        elseif ($name -match '(?i)l2_ingest|l2_exports|allfamilies_grid|slice_r[0-9]|qa23|review_20261019_window_phase') { $tier = 'L2_facts' }
        $dest = Join-Path (Join-Path $destRoot $tier) $name
        if (Test-Path -LiteralPath $dest) { throw "Destination already exists: $dest" }
        New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
        Move-Item -LiteralPath $item.FullName -Destination $dest
        if (-not (Test-Path -LiteralPath $dest) -or (Test-Path -LiteralPath $item.FullName)) { throw "Move verification failed: $($item.FullName)" }
        Write-Output "MOVED $task/$name -> $tier"
    }
}
Write-Output 'MOVES_COMPLETE'
