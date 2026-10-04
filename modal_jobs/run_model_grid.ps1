<#
Launch the V1.6 recurrent-model plan without uncontrolled Modal fan-out.

Default is the one-cell official pilot (CQ/W1/V0/RNN/42).  ``-Mode grid``
expands only after the caller explicitly requests it.  Every model invocation
waits for completion, then materializes sanity facts from that immutable run.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet("CQ", "LO")][string]$Task = "CQ",
    [ValidateSet("pilot", "baseline", "grid")][string]$Mode = "pilot",
    [string[]]$Windows,
    [string[]]$Pipelines,
    [string[]]$Models,
    [int[]]$Seeds,
    [int]$AugmentationSeed = 42,
    [ValidateSet("CQ_V2_2", "LO_V3_1")][string]$ReleaseId = "",
    [switch]$SkipSanity,
    [string]$LogRoot = ".\logs\model_grid"
)

$ErrorActionPreference = "Stop"
if (-not $ReleaseId) { $ReleaseId = if ($Task -eq "CQ") { "CQ_V2_2" } else { "LO_V3_1" } }
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ModelApp = Join-Path $PSScriptRoot "model_app.py"
$SanityApp = Join-Path $PSScriptRoot "model_sanity_app.py"
$Stamp = Get-Date -Format "yyyyMMddTHHmmss"
$RunRoot = Join-Path $LogRoot "$Task`_$Mode`_$Stamp"
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null

switch ($Mode) {
    "pilot" {
        if (-not $Windows) { $Windows = @("W1") }
        if (-not $Pipelines) { $Pipelines = @("V0") }
        if (-not $Models) { $Models = @("RNN") }
        if (-not $Seeds) { $Seeds = @(42) }
    }
    "baseline" {
        if (-not $Windows) { $Windows = @("W1", "W2", "W3") }
        if (-not $Pipelines) { $Pipelines = @("V0") }
        if (-not $Models) { $Models = @("RNN") }
        if (-not $Seeds) { $Seeds = @(42, 43, 44) }
    }
    "grid" {
        if (-not $Windows) { $Windows = @("W1", "W2", "W3") }
        if (-not $Pipelines) { $Pipelines = 0..16 | ForEach-Object { "V$_" } }
        if (-not $Models) { $Models = @("RNN", "LSTM", "GRU", "BILSTM") }
        if (-not $Seeds) { $Seeds = @(42, 43, 44) }
    }
}

$plan = foreach ($Window in $Windows) {
    foreach ($Pipeline in $Pipelines) {
        foreach ($Model in $Models) {
            foreach ($Seed in $Seeds) {
                [ordered]@{ task=$Task; release_id=$ReleaseId; window=$Window; pipeline_id=$Pipeline; model_name=$Model; seed=$Seed; augmentation_seed=$AugmentationSeed }
            }
        }
    }
}
$plan | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $RunRoot "plan.json")

$results = [System.Collections.Generic.List[object]]::new()
foreach ($item in $plan) {
    $tag = "$($item.window)_$($item.pipeline_id)_$($item.model_name)_seed$($item.seed)"
    $modelLog = Join-Path $RunRoot "$tag.model.log"
    Write-Host "[$(Get-Date -Format s)] MODEL $tag"
    $modelArgs = @("-X", "utf8", "-m", "modal", "run", $ModelApp,
                   "--task", $item.task, "--window", $item.window,
                   "--pipeline-id", $item.pipeline_id, "--model-name", $item.model_name,
                   "--seed", "$($item.seed)", "--augmentation-seed", "$($item.augmentation_seed)",
                   "--release-id", $item.release_id)
    if ($PSCmdlet.ShouldProcess($tag, "train model")) {
        # Python/Modal emits deprecation warnings on stderr.  PowerShell 7
        # otherwise promotes that stderr text to NativeCommandError when
        # ErrorActionPreference=Stop, even though Modal exits successfully.
        $savedErrorAction = $ErrorActionPreference
        $savedNativePreference = $PSNativeCommandUseErrorActionPreference
        $ErrorActionPreference = "Continue"
        if ($null -ne (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)) {
            $PSNativeCommandUseErrorActionPreference = $false
        }
        try {
            & python @modelArgs 2>&1 | Tee-Object -FilePath $modelLog
            $modelExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedErrorAction
            if ($null -ne (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)) {
                $PSNativeCommandUseErrorActionPreference = $savedNativePreference
            }
        }
    } else { $modelExit = 0 }
    $status = [ordered]@{ task=$item.task; release_id=$item.release_id; window=$item.window; pipeline_id=$item.pipeline_id; model_name=$item.model_name; seed=$item.seed; augmentation_seed=$item.augmentation_seed; model_exit_code=$modelExit; sanity_exit_code=$null }
    if ($modelExit -ne 0) {
        $results.Add([pscustomobject]$status)
        continue
    }
    if (-not $SkipSanity) {
        $sanityLog = Join-Path $RunRoot "$tag.sanity.log"
        Write-Host "[$(Get-Date -Format s)] SANITY $tag"
        $sanityArgs = @("-X", "utf8", "-m", "modal", "run", $SanityApp,
                        "--task", $item.task, "--window", $item.window,
                        "--pipeline-id", $item.pipeline_id, "--model-name", $item.model_name,
                        "--seed", "$($item.seed)", "--release-id", $item.release_id)
        if ($PSCmdlet.ShouldProcess($tag, "materialize sanity")) {
            $savedErrorAction = $ErrorActionPreference
            $savedNativePreference = $PSNativeCommandUseErrorActionPreference
            $ErrorActionPreference = "Continue"
            if ($null -ne (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)) {
                $PSNativeCommandUseErrorActionPreference = $false
            }
            try {
                & python @sanityArgs 2>&1 | Tee-Object -FilePath $sanityLog
                $status.sanity_exit_code = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $savedErrorAction
                if ($null -ne (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)) {
                    $PSNativeCommandUseErrorActionPreference = $savedNativePreference
                }
            }
        } else { $status.sanity_exit_code = 0 }
    }
    $results.Add([pscustomobject]$status)
}
$results | Export-Csv -NoTypeInformation -Encoding utf8 (Join-Path $RunRoot "run_summary.csv")
$failed = @($results | Where-Object { $_.model_exit_code -ne 0 -or ($null -ne $_.sanity_exit_code -and $_.sanity_exit_code -ne 0) })
Write-Host "Completed $($results.Count) planned cells; failed $($failed.Count). Logs: $RunRoot"
if ($failed.Count) { exit 1 }
