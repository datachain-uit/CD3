$ErrorActionPreference='Stop'
$source='G:\My Drive\Jobs\LO\rclone_direct_20261029'
$base='G:\My Drive\Jobs\LO\organized_moved_20261029'
$items=@(
 @('reports','reports\rclone_direct_20261029'),
 @('input_model_data','input_archives\model_input_seed42'),
 @('source_results\transfer_logs','transfer_receipts_and_logs\rclone_direct_20261029'),
 @('README.md','transfer_receipts_and_logs\rclone_direct_20261029_README.md')
)
foreach($item in $items){
 $src=Join-Path $source $item[0]; $dst=Join-Path $base $item[1]
 if(-not(Test-Path -LiteralPath $src)){throw "Missing $src"}
 if(Test-Path -LiteralPath $dst){throw "Collision $dst"}
 New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
 Move-Item -LiteralPath $src -Destination $dst
 if(-not(Test-Path -LiteralPath $dst)){throw "Move failed $dst"}
 Write-Output "MOVED $src -> $dst"
}
Write-Output 'LO_REMAINING_MOVED'
