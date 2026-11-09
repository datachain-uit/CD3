$ErrorActionPreference='Stop'
$root='G:\My Drive\Jobs'
$src=Join-Path $root 'CQ\rclone_direct_20261029'
$dst=Join-Path $root 'CQ\organized_moved_20261029'
$items=@(
 @('reports','reports\rclone_direct_20261029'),
 @('input_model_data','input_archives\model_input_seed42'),
 @('source_results','input_archives\source_inputs_20261029'),
 @('README.md','transfer_receipts_and_logs\rclone_direct_20261029_README.md')
)
foreach($item in $items){
 $from=Join-Path $src $item[0]; $to=Join-Path $dst $item[1]
 if(-not(Test-Path -LiteralPath $from)){throw "Missing: $from"}
 if(Test-Path -LiteralPath $to){throw "Collision: $to"}
 New-Item -ItemType Directory -Path (Split-Path -Parent $to) -Force | Out-Null
 Move-Item -LiteralPath $from -Destination $to
 if(-not(Test-Path -LiteralPath $to)){throw "Move failed: $to"}
 Write-Output "MOVED $from -> $to"
}
foreach($task in @('CQ','LO')){
 $target=Join-Path $root "$task\rclone_direct_20261029"
 if(@(Get-ChildItem -LiteralPath $target -Recurse -File -Force).Count -gt 0){throw "Files remain: $target"}
 $resolved=(Resolve-Path -LiteralPath $target).Path
 if($resolved -ne $target){throw "Unexpected path: $resolved"}
 Remove-Item -LiteralPath $resolved -Recurse -Force
 Write-Output "REMOVED_EMPTY $resolved"
}
