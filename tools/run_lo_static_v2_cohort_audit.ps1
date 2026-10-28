[CmdletBinding()]
param(
    [ValidateSet('RNN', 'LSTM', 'GRU')]
    [string]$Family,
    [string]$DataRoot = 'downloads/vastai/LO_V3_1_clean_grain_seed42',
    [string]$ResultRoot = 'LO/resuilt/lo_static_v2_seed42_20261026',
    [string]$OutputRoot = 'LO/resuilt/lo_static_v2_cohort_audit_20261028',
    [string]$SaltFile = 'downloads/private/lo_grid_prediction_salt'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

foreach ($index in 0..16) {
    $pipeline = "V$index"
    $target = Join-Path $OutputRoot "$Family/$pipeline"
    $summary = Join-Path $target 'summary.json'
    if (Test-Path -LiteralPath $summary) {
        $existing = Get-Content -LiteralPath $summary -Raw | ConvertFrom-Json
        if ($existing.cells -eq 96 -and $existing.duplicate_hashes -eq 0 -and $existing.invalid_strict -eq 0) {
            Write-Output "[$(Get-Date -Format o)] SKIP $Family/$pipeline (complete)"
            continue
        }
    }

    Write-Output "[$(Get-Date -Format o)] START $Family/$pipeline"
    & python tools/audit_prediction_course_cohort.py `
        --task LO `
        --data-root $DataRoot `
        --model-root (Join-Path $ResultRoot $Family) `
        --output-root $target `
        --pipeline-id $pipeline `
        --model-name $Family `
        --seed 42 `
        --prediction-salt-file $SaltFile
    if ($LASTEXITCODE -ne 0) {
        throw "Cohort audit failed for $Family/$pipeline (exit $LASTEXITCODE)."
    }
    Write-Output "[$(Get-Date -Format o)] DONE $Family/$pipeline"
}
