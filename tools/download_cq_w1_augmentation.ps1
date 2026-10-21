$ErrorActionPreference = 'Stop'

$task = 'CQ'
$regime = 'CQ_RAW_EARLY'
$window = 'W1'
$seed = '20260922'
$volume = 'tempo-data-v1'
$destination = Join-Path $PSScriptRoot '..\downloads\augmentation\CQ_W1_P4_CDSMOTE_complete'
$destination = [System.IO.Path]::GetFullPath($destination)
New-Item -ItemType Directory -Force -Path $destination | Out-Null

foreach ($pipeline in 'V2', 'V6', 'V10', 'V14') {
    $remoteBase = "meta_release=imputation-v1/L1_runs/task=$task/feature_regime=$regime/window_id=$window/phase_id=P4/pipeline_id=$pipeline/model_name=BALANCED_TRAIN_ONLY/seed=$seed"
    $localBase = Join-Path $destination $pipeline
    New-Item -ItemType Directory -Force -Path $localBase | Out-Null
    foreach ($name in 'run_manifest.json', 'synthetic_ledger.parquet', 'balanced_train.parquet') {
        $localPath = Join-Path $localBase $name
        $remotePath = "$remoteBase/$name"
        $ok = $false
        for ($attempt = 1; $attempt -le 3 -and -not $ok; $attempt++) {
            Write-Output "Downloading $pipeline/$name (attempt $attempt)"
            & python -X utf8 -m modal volume get --force $volume $remotePath $localPath
            if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $localPath) -and ((Get-Item -LiteralPath $localPath).Length -gt 0)) {
                $ok = $true
            } else {
                Write-Warning "$pipeline/$name was incomplete; retrying"
            }
        }
        if (-not $ok) { throw "Could not download a non-empty file: $pipeline/$name" }
    }
}
Write-Output 'DOWNLOAD_COMPLETE'
