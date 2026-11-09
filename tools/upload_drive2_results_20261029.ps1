$ErrorActionPreference = 'Stop'
$r = 'C:\Users\manndm\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe'
$source = 'D:\Source_code\myself\upload_staging\drive2_results_20261029'
$folderId = '1cQM0gIc6zEBfA1-_cC0X2ZK6m0wEw0Gt'
$log = 'D:\Source_code\myself\upload_staging\drive2_results_20261029_transfer.log'
& $r copy $source 'gdrive2:' --drive-root-folder-id $folderId --immutable --transfers 3 --checkers 8 --stats 30s --stats-one-line --log-level INFO --log-file $log
if ($LASTEXITCODE -ne 0) { throw "Rclone copy failed: $LASTEXITCODE; see $log" }
& $r check $source 'gdrive2:' --drive-root-folder-id $folderId --one-way --checkers 8 --stats 30s --stats-one-line --log-level INFO --log-file $log
if ($LASTEXITCODE -ne 0) { throw "Rclone check failed: $LASTEXITCODE; see $log" }
Write-Output 'DRIVE2_LOCAL_RESULTS_COPY_AND_CHECK_COMPLETE'
