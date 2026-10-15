[CmdletBinding()]
param(
    [string]$Volume = "tempo-data-v1",
    [int]$Retries = 3
)

$ErrorActionPreference = "Stop"
# Modal currently emits Python deprecation warnings on Windows.  In PowerShell
# 7 these stderr lines can otherwise be promoted to terminating native-command
# errors despite a successful Modal exit code.
$PSNativeCommandUseErrorActionPreference = $false
$Root = Split-Path -Parent $PSScriptRoot
$Destination = Join-Path $Root "downloads\vastai\CQ_V2_2_clean_grain_seed42"
$ManifestPath = Join-Path $Destination "download_manifest.json"
$LogPath = Join-Path $Destination "download.log"

& python -X utf8 (Join-Path $PSScriptRoot "build_cq_vastai_download_manifest.py")
if ($LASTEXITCODE -ne 0) { throw "Could not build the authoritative CQ VastAI download manifest." }

$manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $Destination | Out-Null

"[$(Get-Date -Format o)] START release=$($manifest.release_id) data_release=$($manifest.data_release_id) files=$($manifest.counts.total)" |
    Tee-Object -FilePath $LogPath -Append

foreach ($item in $manifest.files) {
    $local = Join-Path $Destination $item.local_path
    $parent = Split-Path -Parent $local
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    if ((Test-Path -LiteralPath $local) -and ((Get-Item -LiteralPath $local).Length -gt 0)) {
        "[$(Get-Date -Format o)] SKIP $($item.remote_path)" | Tee-Object -FilePath $LogPath -Append
        continue
    }
    $completed = $false
    for ($attempt = 1; $attempt -le $Retries -and -not $completed; $attempt++) {
        "[$(Get-Date -Format o)] GET [$attempt/$Retries] $($item.remote_path)" | Tee-Object -FilePath $LogPath -Append
        # Route Python stderr through cmd before PowerShell receives it.  This
        # avoids Windows PowerShell treating Modal's harmless deprecation
        # warning as NativeCommandError while preserving it in download.log.
        & cmd.exe /d /c "python -X utf8 -m modal volume get --force $Volume $($item.remote_path) $local 2>&1" |
            Tee-Object -FilePath $LogPath -Append
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $local) -and ((Get-Item -LiteralPath $local).Length -gt 0)) {
            $completed = $true
        } else {
            Remove-Item -LiteralPath $local -Force -ErrorAction SilentlyContinue
            "[$(Get-Date -Format o)] RETRY $($item.remote_path)" | Tee-Object -FilePath $LogPath -Append
        }
    }
    if (-not $completed) { throw "Failed after $Retries attempts: $($item.remote_path)" }
}

"[$(Get-Date -Format o)] COMPLETE" | Tee-Object -FilePath $LogPath -Append
