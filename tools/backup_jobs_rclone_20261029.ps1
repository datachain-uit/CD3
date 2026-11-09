param([string]$Remote = 'gdrive:Jobs', [switch]$Archives)
$ErrorActionPreference = 'Stop'
$rclone = 'C:\Users\manndm\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe'
$root = 'D:\Source_code\myself'
$groups = @(
    @{Source=Join-Path $root 'CQ\resuilt'; Dest="$Remote/CQ/rclone_direct_20261029/source_results"},
    @{Source=Join-Path $root 'LO\resuilt'; Dest="$Remote/LO/rclone_direct_20261029/source_results"},
    @{Source=Join-Path $root 'downloads\vastai\CQ_V2_2_clean_grain_seed42'; Dest="$Remote/CQ/rclone_direct_20261029/input_model_data"},
    @{Source=Join-Path $root 'downloads\vastai\LO_V3_1_clean_grain_seed42'; Dest="$Remote/LO/rclone_direct_20261029/input_model_data"}
)
$filter = @('--ignore-case','--exclude','**/private/**','--exclude','**/.git/**','--exclude','**/*salt*','--exclude','**/*secret*','--exclude','**/*token*','--exclude','**/*credential*','--exclude','**/.env*','--exclude','**/cq_rnn_replay_protocol27_evidence.tar.gz','--exclude','**/LO_static_v2_BILSTM.tar')
if ($Archives) {
    $filter = @('--ignore-case','--filter','- **/private/**','--filter','- **/.git/**',
        '--filter','- **/*salt*','--filter','- **/*secret*','--filter','- **/*token*','--filter','- **/*credential*','--filter','- **/.env*',
        '--filter','- **/cq_rnn_replay_protocol27_evidence.tar.gz',
        '--filter','- **/LO_static_v2_BILSTM.tar',
        '--filter','+ *.zip','--filter','+ *.tar','--filter','+ *.tar.gz','--filter','- **')
}
else { $filter += @('--exclude','*.zip','--exclude','*.tar','--exclude','*.tar.gz') }
foreach ($group in $groups) {
    Write-Output "START source=$($group.Source) destination=$($group.Dest) archives=$Archives"
    & $rclone copy $group.Source $group.Dest @filter --immutable --transfers 4 --checkers 8 --stats 30s --stats-one-line --log-level INFO
    if ($LASTEXITCODE -ne 0) { throw "Rclone copy failed ($LASTEXITCODE): $($group.Source)" }
    & $rclone check $group.Source $group.Dest @filter --one-way --checkers 8 --stats 30s --stats-one-line --log-level INFO
    if ($LASTEXITCODE -ne 0) { throw "Rclone check failed ($LASTEXITCODE): $($group.Source)" }
    Write-Output "VERIFIED source=$($group.Source)"
}
Write-Output "PASS_COMPLETE archives=$Archives"
