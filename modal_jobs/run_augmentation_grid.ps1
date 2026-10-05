<#
Materialize the complete seed-aligned S2 augmentation grid.

For every master seed, the resulting balanced TRAIN artifact is stored under
the same seed and consumed by run_model_grid.ps1 with its default
match_model_seed policy.  Calls are deliberately sequential to avoid Modal
app-creation and memory pressure; launch separate task scripts only after
checking available account capacity.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet("CQ", "LO")][string]$Task = "CQ",
    [string[]]$Windows = @("W1", "W2", "W3"),
    [ValidateSet("V1", "V5", "V9", "V13")][string[]]$ParentPipelines = @("V1", "V5", "V9", "V13"),
    [ValidateSet("CDSMOTE", "SASMOTE", "RADIUS_SMOTE")][string[]]$Methods = @("CDSMOTE", "SASMOTE", "RADIUS_SMOTE"),
    [int[]]$Seeds = @(42, 43, 44),
    [ValidateSet("CQ_V2_2", "LO_V3_1")][string]$ReleaseId = "",
    [string]$LogRoot = ".\logs\augmentation_grid"
)

$ErrorActionPreference = "Stop"
if (-not $ReleaseId) { $ReleaseId = if ($Task -eq "CQ") { "CQ_V2_2" } else { "LO_V3_1" } }
$App = Join-Path $PSScriptRoot "augmentation_app.py"
$Stamp = Get-Date -Format "yyyyMMddTHHmmss"
$RunRoot = Join-Path $LogRoot "$Task`_augmentation_$Stamp"
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null

$plan = foreach ($Window in $Windows) {
    foreach ($Parent in $ParentPipelines) {
        foreach ($Method in $Methods) {
            foreach ($Seed in $Seeds) {
                [ordered]@{ task=$Task; release_id=$ReleaseId; window=$Window; parent_pipeline=$Parent; method=$Method; seed=$Seed }
            }
        }
    }
}
$plan | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $RunRoot "plan.json")

$results = [System.Collections.Generic.List[object]]::new()
foreach ($item in $plan) {
    $tag = "$($item.window)_$($item.parent_pipeline)_$($item.method)_seed$($item.seed)"
    $log = Join-Path $RunRoot "$tag.log"
    Write-Host "[$(Get-Date -Format s)] AUGMENT $tag"
    $args = @("-X", "utf8", "-m", "modal", "run", $App,
              "--mode", "augment", "--task", $item.task, "--window", $item.window,
              "--phase", "P4", "--parent-pipeline", $item.parent_pipeline,
              "--method", $item.method, "--seed", "$($item.seed)",
              "--release-id", $item.release_id)
    if ($PSCmdlet.ShouldProcess($tag, "materialize balanced TRAIN")) {
        $savedErrorAction = $ErrorActionPreference
        $savedNativePreference = $PSNativeCommandUseErrorActionPreference
        $ErrorActionPreference = "Continue"
        if ($null -ne (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)) {
            $PSNativeCommandUseErrorActionPreference = $false
        }
        try {
            & python @args 2>&1 | Tee-Object -FilePath $log
            $exitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedErrorAction
            if ($null -ne (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)) {
                $PSNativeCommandUseErrorActionPreference = $savedNativePreference
            }
        }
    } else { $exitCode = 0 }
    $record = [ordered]@{}
    foreach ($key in $item.Keys) { $record[$key] = $item[$key] }
    $record["exit_code"] = $exitCode
    $results.Add([pscustomobject]$record)
}
$results | Export-Csv -NoTypeInformation -Encoding utf8 (Join-Path $RunRoot "run_summary.csv")
$failed = @($results | Where-Object { $_.exit_code -ne 0 })
Write-Host "Completed $($results.Count) planned augmentation cells; failed $($failed.Count). Logs: $RunRoot"
if ($failed.Count) { exit 1 }
