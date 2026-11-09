$ErrorActionPreference = 'Stop'
$rclone = 'C:\Users\manndm\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe'
$root = 'gdrive:Jobs'
$curated = @('cq_patchtst_v0_seed42_20261023','cq_patchtst_d23_stability_pilot_20261026','cq_rnn_replay_protocol27_20261029','cq_f1_allfamilies_l2_ingest_r3_20261021','cq_recurrent_allfamilies_grid_r4_20261023','review_20261019_window_phase','qa23_v2_2','lo_static_v2_seed42_20261026','lo_l2_ingest_closure_seed42_20261025','lo_recurrent_allfamilies_grid_r2_20261021','lo_static_v2_cohort_audit_20261028','lo_static_v2_static_contract_audit_20261028','lo_prefix_source_audit_20261028')
foreach ($task in @('CQ','LO')) {
    $local = Join-Path (Join-Path 'D:\Source_code\myself' $task) 'resuilt'
    $remoteNames = @(& $rclone lsf "$root/$task/rclone_direct_20261029/source_results" --dirs-only)
    if ($LASTEXITCODE -ne 0) { throw "Could not list remote results for $task" }
    foreach ($dir in Get-ChildItem -LiteralPath $local -Directory) {
        $name = $dir.Name
        if ($name -in $curated -or $name -match '^(private|input|transfer_logs|_checked_feature_v2|cq_prefix_audit_inputs_20261017)$') { continue }
        if (($name + '/') -notin $remoteNames) { Write-Output "NOT_ON_DRIVE $task/$name"; continue }
        # Keep mixed/historical packages intact, without claiming they are canonical facts.
        $source = "$root/$task/rclone_direct_20261029/source_results/$name"
        $dest = "$root/$task/organized_results_20261029/evidence_packages/$name"
        Write-Output "COPY $source -> $dest"
        & $rclone copy $source $dest --immutable --transfers 4 --checkers 8 --stats 30s --stats-one-line --log-level INFO --ignore-case --exclude '**/private/**' --exclude '**/*salt*' --exclude '**/*secret*' --exclude '**/*token*' --exclude '**/*credential*' --exclude '**/.env*'
        if ($LASTEXITCODE -ne 0) { throw "copy failed: $source" }
        & $rclone check $source $dest --one-way --checkers 8 --ignore-case --exclude '**/private/**' --exclude '**/*salt*' --exclude '**/*secret*' --exclude '**/*token*' --exclude '**/*credential*' --exclude '**/.env*'
        if ($LASTEXITCODE -ne 0) { throw "check failed: $source" }
        Write-Output "VERIFIED $dest"
    }
}
Write-Output 'REMAINING_PACKAGES_COMPLETE'
