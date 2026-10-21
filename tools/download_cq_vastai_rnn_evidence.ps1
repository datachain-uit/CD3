[CmdletBinding()]
param(
    [string[]]$Windows = @("W1"),
    [string[]]$Pipelines = @("V0"),
    [switch]$IncludeValidation,
    [string]$Volume = "tempo-data-v1",
    [int]$Retries = 3
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$Root = Split-Path -Parent $PSScriptRoot
$Destination = Join-Path $Root "downloads\vastai\CQ_V2_2_clean_grain_seed42\rnn_evidence"
$ManifestPath = Join-Path $Destination "download_manifest.json"
$LogPath = Join-Path $Destination "download.log"

$args = @("-X", "utf8", (Join-Path $PSScriptRoot "build_cq_vastai_rnn_evidence_manifest.py"), "--windows") + $Windows + @("--pipelines") + $Pipelines
if ($IncludeValidation) { $args += "--include-validation" }
& python @args
if ($LASTEXITCODE -ne 0) { throw "Could not build the RNN evidence manifest." }

$manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
foreach ($item in $manifest.files) {
    $local = Join-Path $Destination $item.local_path
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $local) | Out-Null
    if ((Test-Path -LiteralPath $local) -and ((Get-Item -LiteralPath $local).Length -gt 0)) { continue }
    $complete = $false
    for ($attempt = 1; $attempt -le $Retries -and -not $complete; $attempt++) {
        "[$(Get-Date -Format o)] GET [$attempt/$Retries] $($item.remote_path)" | Tee-Object -FilePath $LogPath -Append
        & cmd.exe /d /c "python -X utf8 -m modal volume get --force $Volume $($item.remote_path) $local 2>&1" | Tee-Object -FilePath $LogPath -Append
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $local) -and ((Get-Item -LiteralPath $local).Length -gt 0)) {
            $complete = $true
        } else {
            Remove-Item -LiteralPath $local -Force -ErrorAction SilentlyContinue
        }
    }
    if (-not $complete) { throw "Failed after $Retries attempts: $($item.remote_path)" }
}
"[$(Get-Date -Format o)] COMPLETE" | Tee-Object -FilePath $LogPath -Append
