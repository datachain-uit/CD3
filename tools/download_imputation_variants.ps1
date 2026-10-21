param(
    [string]$Volume = "tempo-data-v1",
    [string]$Release = "imputation-v1"
)

$ErrorActionPreference = "Stop"
$root = Join-Path (Get-Location) "downloads\imputation\mean_median_extra_trees_full"
$variants = @("V1", "V5", "V9") # Median, Mean, ExtraTrees
$tasks = @(
    @{ task = "CQ"; regime = "CQ_RAW_EARLY" },
    @{ task = "LO"; regime = "LO_FULL_EARLY" }
)

function Invoke-VariantDownload {
    param([string]$Remote, [string]$Target, [string]$Name, [string]$Pipeline)
    $python = (Get-Command python -ErrorAction Stop).Source
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $stdout = Join-Path $Target ".${Name}.attempt${attempt}.out.log"
        $stderr = Join-Path $Target ".${Name}.attempt${attempt}.err.log"
        $process = Start-Process -FilePath $python -ArgumentList @(
            '-X', 'utf8', '-m', 'modal', 'volume', 'get', '--force', $Volume, $Remote, $Target
        ) -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
        # A stalled HTTPS stream must not block the whole 18-run migration.
        Wait-Process -Id $process.Id -Timeout 1200 -ErrorAction SilentlyContinue
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            Write-Warning "$Name timed out on attempt $attempt; retrying."
            continue
        }
        $expectedManifest = Join-Path $Target "pipeline=$Pipeline\seed=20260922\run_manifest.json"
        # Modal's detached Windows process occasionally leaves ExitCode unset
        # despite a completed download.  The immutable run manifest is the
        # authoritative completion marker.
        if (Test-Path $expectedManifest) {
            return
        }
        Write-Warning "$Name failed on attempt $attempt (exit $($process.ExitCode)); retrying."
    }
    throw "Migration failed after three attempts: $Name"
}

foreach ($entry in $tasks) {
    foreach ($window in @("W1", "W2", "W3")) {
        foreach ($pipeline in $variants) {
            # Legacy account layout is the complete W1–W3 archive.  Modal
            # places pipeline=V* below this destination, preserving seed,
            # run, manifest, preprocessor and all transformed model inputs.
            $remote = "meta_release=$Release/L1_runs/task=$($entry.task)/regime=$($entry.regime)/window=$window/model=IMPUTATION_ONLY/pipeline=$pipeline"
            $target = Join-Path $root "task=$($entry.task)\window=$window"
            New-Item -ItemType Directory -Force -Path $target | Out-Null
            $name = "$($entry.task)_${window}_$pipeline"
            $existingManifest = Join-Path $target "pipeline=$pipeline\seed=20260922\run_manifest.json"
            if (Test-Path $existingManifest) {
                Write-Host "Already downloaded $name"
                continue
            }
            Write-Host "Downloading $name"
            Invoke-VariantDownload -Remote $remote -Target $target -Name $name -Pipeline $pipeline
        }
    }
}

Get-ChildItem $root -Recurse -File | Measure-Object Length -Sum |
    Select-Object Count, @{Name = "TotalGiB"; Expression = { [math]::Round($_.Sum / 1GB, 2) }}
