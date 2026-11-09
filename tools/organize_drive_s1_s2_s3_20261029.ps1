$ErrorActionPreference='Stop'
$root='G:\My Drive\Jobs'
foreach($task in @('CQ','LO')) {
 $base=Join-Path $root "$task\organized_moved_20261029"
 $l1=Join-Path $base 'L1_runs'
 foreach($bundle in @('run_bundles','preserved_packages')) {
  $src=Join-Path $l1 $bundle; $parent=Join-Path $l1 'S3_model'; $dest=Join-Path $parent $bundle
  if(Test-Path -LiteralPath $src) {
   if(Test-Path -LiteralPath $dest){throw "Collision: $dest"}
   New-Item -ItemType Directory -Path $parent -Force | Out-Null
   Move-Item -LiteralPath $src -Destination $dest
   Write-Output "MOVED $task/$bundle -> S3_model"
  }
 }
 $train=Join-Path $base 'input_archives\model_input_seed42\train'
 if(Test-Path -LiteralPath $train) {
  foreach($window in Get-ChildItem -LiteralPath $train -Directory) {
   if($window.Name -notmatch '^W[123]$'){throw "Unexpected window $($window.Name)"}
   foreach($v in Get-ChildItem -LiteralPath $window.FullName -Directory) {
    if($v.Name -notmatch '^V([0-9]|1[0-6])$'){throw "Unexpected pipeline $($v.Name)"}
    $isS1=$v.Name -in @('V0','V1','V5','V9','V13')
    $file=if($isS1){'train.parquet'}else{'balanced_train.parquet'}
    if(-not(Test-Path -LiteralPath (Join-Path $v.FullName $file))){throw "Missing expected $file in $($v.FullName)"}
    $stage=if($isS1){'S1_imputation'}else{'S2_augmentation'}
    $parent=Join-Path $l1 "$stage\model_inputs_seed42\$($window.Name)"
    $dest=Join-Path $parent $v.Name
    if(Test-Path -LiteralPath $dest){throw "Collision $dest"}
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Move-Item -LiteralPath $v.FullName -Destination $dest
    if(-not(Test-Path -LiteralPath (Join-Path $dest $file))){throw "Move failed $dest"}
    Write-Output "MOVED $task/$($window.Name)/$($v.Name) -> $stage"
   }
  }
 }
}
Write-Output 'S1_S2_S3_ORGANIZATION_COMPLETE'
