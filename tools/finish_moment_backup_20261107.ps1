$ErrorActionPreference = 'Stop'
$log = 'D:\Source_code\myself\logs\moment_backup_20261107.log'
function Write-Status([string]$message) {
    Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) $message" -Encoding UTF8
}
$jobs = @(
    @{ Id = 45000; Local = 'D:\Source_code\myself\.moment_cache'; Remote = 'gdrive:Moment/moment_cache' },
    @{ Id = 18608; Local = 'D:\Source_code\myself\.moment_benchmark_venv'; Remote = 'gdrive:Moment/moment_benchmark_venv' }
)
foreach ($job in $jobs) {
    Write-Status "Waiting for copy PID $($job.Id): $($job.Local)"
    $proc = Get-Process -Id $job.Id -ErrorAction SilentlyContinue
    if ($proc) { $proc.WaitForExit() }
    if (-not (Test-Path -LiteralPath $job.Local -PathType Container)) { Write-Status "SKIP missing local: $($job.Local)"; continue }
    $resolved = (Resolve-Path -LiteralPath $job.Local).Path
    if ($resolved -ne $job.Local) { Write-Status "SKIP unexpected target: $resolved"; continue }
    & rclone check $job.Local $job.Remote --one-way --checkers 8 --log-level NOTICE --log-file $log
    if ($LASTEXITCODE -ne 0) { Write-Status "CHECK FAILED; retained local: $($job.Local)"; continue }
    Write-Status "CHECK PASSED; removing local: $($job.Local)"
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction Stop
    Write-Status "REMOVED: $($job.Local)"
}
Write-Status 'FINISHED'
