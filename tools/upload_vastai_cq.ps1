[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$HostName,
    [Parameter(Mandatory = $true)]
    [int]$Port,
    [string]$UserName = "root",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\id_vastai"),
    [string]$LocalRoot = ".\downloads\vastai\CQ_V2_2_clean_grain_seed42",
    [string]$RemoteRoot = "/workspace/CD3",
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$LocalRoot = (Resolve-Path -LiteralPath $LocalRoot).Path
$manifestPath = Join-Path $LocalRoot "download_manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Missing download_manifest.json under $LocalRoot"
}
if (-not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH private key not found: $KeyPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$target = "$UserName@$HostName"
$ssh = @("-i", $KeyPath, "-p", "$Port", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20")
$scp = @("-i", $KeyPath, "-P", "$Port", "-o", "BatchMode=yes", "-o", "ConnectTimeout=30")
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$logDir = Join-Path $ProjectRoot "logs\vastai_upload"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir ("CQ_upload_{0:yyyyMMddTHHmmss}.log" -f (Get-Date))

function Invoke-Remote([string]$Command) {
    & ssh @ssh $target $Command
    if ($LASTEXITCODE -ne 0) { throw "Remote command failed: $Command" }
}

Invoke-Remote "mkdir -p $RemoteRoot/data/CQ_V2_2_clean_grain_seed42 $RemoteRoot/code $RemoteRoot/runs"

$i = 0
foreach ($entry in $manifest.files) {
    $i++
    $relative = $entry.local_path.Replace("\", "/")
    $local = Join-Path $LocalRoot $entry.local_path
    $remote = "$RemoteRoot/data/CQ_V2_2_clean_grain_seed42/$relative"
    if (-not (Test-Path -LiteralPath $local)) { throw "Missing local input: $local" }
    $localBytes = (Get-Item -LiteralPath $local).Length
    $remoteDir = [System.IO.Path]::GetDirectoryName($remote).Replace("\", "/")
    $existing = (& ssh @ssh $target "test -f '$remote' && stat -c%s '$remote' || echo 0").Trim()
    if ($existing -eq "$localBytes") {
        "[$i/$($manifest.files.Count)] SKIP $relative" | Tee-Object -FilePath $logPath -Append
        continue
    }
    Invoke-Remote "mkdir -p '$remoteDir'"
    "[$i/$($manifest.files.Count)] UPLOAD $relative" | Tee-Object -FilePath $logPath -Append
    & scp @scp -- $local "${target}:$remote"
    if ($LASTEXITCODE -ne 0) { throw "Upload failed for $relative" }
    $verified = (& ssh @ssh $target "stat -c%s '$remote'").Trim()
    if ($verified -ne "$localBytes") { throw "Size verification failed for ${relative}: local=$localBytes remote=$verified" }
}

"UPLOAD CODE" | Tee-Object -FilePath $logPath -Append
Invoke-Remote "rm -rf $RemoteRoot/code/model $RemoteRoot/code/metrics_core $RemoteRoot/code/release_core"
& scp @scp -r -- (Join-Path $ProjectRoot "model") "${target}:$RemoteRoot/code/"
if ($LASTEXITCODE -ne 0) { throw "Code upload failed: model/" }
& scp @scp -r -- (Join-Path $ProjectRoot "metrics_core") "${target}:$RemoteRoot/code/"
if ($LASTEXITCODE -ne 0) { throw "Code upload failed: metrics_core/" }
& scp @scp -r -- (Join-Path $ProjectRoot "release_core") "${target}:$RemoteRoot/code/"
if ($LASTEXITCODE -ne 0) { throw "Code upload failed: release_core/" }
foreach ($script in "vastai_train_shared.py", "vastai_audit_shared.py", "vastai_metadata_contract.py", "vastai_audit_w1.py", "vastai_run_cq_f1_audit.sh") {
    & scp @scp -- (Join-Path $ProjectRoot "tools\$script") "${target}:$RemoteRoot/code/$script"
    if ($LASTEXITCODE -ne 0) { throw "Code upload failed: $script" }
}
Invoke-Remote "chmod 700 $RemoteRoot/code/vastai_run_cq_f1_audit.sh"
& scp @scp -- $manifestPath "${target}:$RemoteRoot/data/CQ_V2_2_clean_grain_seed42/download_manifest.json"
if ($LASTEXITCODE -ne 0) { throw "Manifest upload failed" }

Invoke-Remote "cd $RemoteRoot && find data/CQ_V2_2_clean_grain_seed42 -type f | wc -l && du -sh data/CQ_V2_2_clean_grain_seed42 code"
"COMPLETE $(Get-Date -Format o)" | Tee-Object -FilePath $logPath -Append
Write-Host "Upload complete. Log: $logPath"
