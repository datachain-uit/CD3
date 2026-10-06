<#!
.SYNOPSIS
Uploads one validated immutable CQ V2.2 or LO V3.1 input release to Modal.

.DESCRIPTION
The runner never touches /data/meta_release=imputation-v1.  It only writes
the frozen source-input namespace consumed by S0/S1.  Both source datasets
must already be extracted Parquet directories.

.EXAMPLE
.\modal_jobs\upload_release.ps1 -Task CQ `
  -PhaseViewsPath .\CQ\resuilt\phase_views_v2_2\phase_views_v2_2 `
  -TestPrefixesPath .\CQ\resuilt\test_prefix_views_v2_2\test_prefix_views_v2_2
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet("CQ", "LO")]
    [string]$Task,

    [Parameter(Mandatory)]
    [string]$PhaseViewsPath,

    [Parameter(Mandatory)]
    [string]$TestPrefixesPath,

    [string]$Volume = "tempo-data-v1",

    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

$release = if ($Task -eq "CQ") {
    @{
        Id = "CQ_v2_2"
        PhaseDirectory = "phase_views_v2_2"
        TestDirectory = "test_prefix_views_v2_2"
        Manifest = Join-Path $PSScriptRoot "cq_v2_2_release_manifest.json"
    }
} else {
    @{
        Id = "LO_v3_1"
        PhaseDirectory = "phase_views_v3_1_scored_signal_excluded"
        TestDirectory = "test_prefix_views_v3_1_scored_signal_excluded"
        Manifest = Join-Path $PSScriptRoot "lo_v3_1_release_manifest.json"
    }
}

function Resolve-ReleaseDirectory([string]$Path, [string]$ExpectedLeaf) {
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if ((Split-Path -Leaf $resolved) -eq $ExpectedLeaf) { return $resolved }
    $nested = Join-Path $resolved $ExpectedLeaf
    if (Test-Path -LiteralPath $nested -PathType Container) {
        return (Resolve-Path -LiteralPath $nested).Path
    }
    throw "Expected directory '$ExpectedLeaf' at '$resolved' or directly below it."
}

function Assert-HasParquet([string]$Path, [string]$Description) {
    $firstParquet = Get-ChildItem -LiteralPath $Path -File -Filter "*.parquet" |
        Select-Object -First 1
    if ($null -eq $firstParquet) {
        throw "$Description is incomplete: no Parquet file found under $Path"
    }
}

$phaseSource = Resolve-ReleaseDirectory $PhaseViewsPath $release.PhaseDirectory
$testSource = Resolve-ReleaseDirectory $TestPrefixesPath $release.TestDirectory

Assert-HasParquet $phaseSource "Phase-view release"
foreach ($phase in "P1", "P2", "P3", "P4") {
    $phasePath = Join-Path $testSource $phase
    if (-not (Test-Path -LiteralPath $phasePath -PathType Container)) {
        throw "Test-prefix release is incomplete: missing directory $phasePath"
    }
    Assert-HasParquet $phasePath "Test-prefix $phase"
}
if (-not (Test-Path -LiteralPath $release.Manifest -PathType Leaf)) {
    throw "Release manifest is missing: $($release.Manifest)"
}

$remoteRoot = "/input/$($release.Id)"
Write-Host "Validated $Task release:"
Write-Host "  phase=$phaseSource"
Write-Host "  test=$testSource"
Write-Host "  remote=$remoteRoot"

if ($VerifyOnly) { return }

& python -X utf8 -m modal volume put --force $Volume $phaseSource "$remoteRoot/"
if ($LASTEXITCODE -ne 0) { throw "Phase-view upload failed with exit code $LASTEXITCODE" }

& python -X utf8 -m modal volume put --force $Volume $testSource "$remoteRoot/"
if ($LASTEXITCODE -ne 0) { throw "Test-prefix upload failed with exit code $LASTEXITCODE" }

& python -X utf8 -m modal volume put --force $Volume $release.Manifest "$remoteRoot/release_manifest.json"
if ($LASTEXITCODE -ne 0) { throw "Release-manifest upload failed with exit code $LASTEXITCODE" }

& python -X utf8 -m modal volume ls $Volume $remoteRoot
if ($LASTEXITCODE -ne 0) { throw "Remote verification failed with exit code $LASTEXITCODE" }

Write-Host "Upload complete: $Task -> $remoteRoot"
