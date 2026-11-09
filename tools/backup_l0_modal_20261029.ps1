param([ValidateSet('CQ','LO')][string]$Task)
$ErrorActionPreference='Stop'
$profiles=@{CQ='sghqvbg';LO='minhman26804'}
$inputNames=@{CQ='CQ_v2_2';LO='LO_v3_1'}
$lineages=@{CQ='materialization_lineage_v2_2';LO='materialization_lineage_v3_1_scored_signal_excluded'}
$profile=$profiles[$Task]; $inputName=$inputNames[$Task]; $lineage=$lineages[$Task]
$local=Join-Path 'D:\Source_code\myself\downloads\l0_modal_backup_20261029' $Task
$registry=Join-Path $local 'modal_L0_registry'; $release=Join-Path $local 'input_release'
New-Item -ItemType Directory -Path $registry,$release -Force | Out-Null
foreach($item in @(
 @('meta_release=imputation-v1/L0_registry',$registry),
 @("input/$inputName/release_manifest.json",(Join-Path $release 'release_manifest.json')),
 @("input/$inputName/$lineage",(Join-Path $release $lineage))
)) {
 Write-Output "DOWNLOAD $Task $($item[0])"
 & python -X utf8 -m modal volume get --profile $profile --force tempo-data-v1 $item[0] $item[1]
 if($LASTEXITCODE -ne 0){throw "Modal download failed: $($item[0])"}
}
$r='C:\Users\manndm\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe'
$dest="gdrive:Jobs/$Task/organized_moved_20261029/L0_registry"
$filters=@('--ignore-case','--exclude','**/*salt*','--exclude','**/*secret*','--exclude','**/*token*','--exclude','**/*credential*','--exclude','**/.env*')
& $r copy $local $dest @filters --immutable --transfers 4 --checkers 8 --stats 30s
if($LASTEXITCODE -ne 0){throw "Drive upload failed: $Task"}
& $r check $local $dest @filters --one-way --checkers 8 --stats 30s
if($LASTEXITCODE -ne 0){throw "Drive verification failed: $Task"}
Write-Output "VERIFIED_L0 $Task"
