$ErrorActionPreference = 'Stop'
$rclone = 'C:\Users\manndm\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe'
$root = 'gdrive:Jobs'
$items = @(
    @('CQ','L1_runs','cq_patchtst_v0_seed42_20261023'),
    @('CQ','L1_runs','cq_patchtst_d23_stability_pilot_20261026'),
    @('CQ','L1_runs','cq_rnn_replay_protocol27_20261029'),
    @('CQ','L2_facts','cq_f1_allfamilies_l2_ingest_r3_20261021'),
    @('CQ','L2_facts','cq_recurrent_allfamilies_grid_r4_20261023'),
    @('CQ','L2_facts','review_20261019_window_phase'),
    @('CQ','L2_facts','qa23_v2_2'),
    @('LO','L1_runs','lo_static_v2_seed42_20261026'),
    @('LO','L2_facts','lo_l2_ingest_closure_seed42_20261025'),
    @('LO','L2_facts','lo_recurrent_allfamilies_grid_r2_20261021'),
    @('LO','L2_facts','lo_static_v2_cohort_audit_20261028'),
    @('LO','L2_facts','lo_static_v2_static_contract_audit_20261028'),
    @('LO','L2_facts','lo_prefix_source_audit_20261028')
)
foreach ($item in $items) {
    $source = "$root/$($item[0])/rclone_direct_20261029/source_results/$($item[2])"
    $dest = "$root/$($item[0])/organized_results_20261029/$($item[1])/$($item[2])"
    Write-Output "COPY $source -> $dest"
    & $rclone copy $source $dest --immutable --transfers 4 --checkers 8 --stats 30s --stats-one-line --log-level INFO
    if ($LASTEXITCODE -ne 0) { throw "copy failed: $source" }
    & $rclone check $source $dest --one-way --checkers 8 --stats 30s --stats-one-line --log-level INFO
    if ($LASTEXITCODE -ne 0) { throw "check failed: $source" }
    Write-Output "VERIFIED $dest"
}
Write-Output 'ORGANIZATION_COMPLETE'
