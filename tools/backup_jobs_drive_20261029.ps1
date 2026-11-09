param([double]$ReserveGiB = 6)
$ErrorActionPreference = 'Stop'
$project = 'D:\Source_code\myself'
$jobs = 'G:\My Drive\Jobs'
$groups = @(
    @{Task='CQ'; Source=Join-Path $project 'CQ\resuilt'; Target='source_results'},
    @{Task='LO'; Source=Join-Path $project 'LO\resuilt'; Target='source_results'},
    @{Task='CQ'; Source=Join-Path $project 'downloads\vastai\CQ_V2_2_clean_grain_seed42'; Target='input_model_data'},
    @{Task='LO'; Source=Join-Path $project 'downloads\vastai\LO_V3_1_clean_grain_seed42'; Target='input_model_data'}
)
$ledger = Join-Path $project 'tools\backup_jobs_drive_20261029_manifest.jsonl'
$reserve = [long]($ReserveGiB * 1GB)
foreach ($group in $groups) {
    $src = [System.IO.Path]::GetFullPath($group.Source).TrimEnd('\')
    $dst = Join-Path $jobs (Join-Path $group.Task (Join-Path 'backup_local_20261029' $group.Target))
    $files = @(Get-ChildItem -LiteralPath $src -File -Recurse -Force -ErrorAction Stop | Sort-Object FullName)
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($src.Length).TrimStart('\')
        if ($relative -match '(?i)(^|\\)(private|\.git)(\\|$)' -or $file.Name -match '(?i)(salt|secret|token|credential|\.env)') {
            continue
        }
        $target = Join-Path $dst $relative
        if (Test-Path -LiteralPath $target -PathType Leaf) {
            $existing = Get-Item -LiteralPath $target
            if ($existing.Length -ne $file.Length) { throw "Existing destination differs in size: $target" }
            $srcHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
            $dstHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
            if ($srcHash -ne $dstHash) { throw "Existing destination differs in hash: $target" }
            continue
        }
        $free = ([System.IO.DriveInfo]::new('C')).AvailableFreeSpace
        if (($free - $file.Length) -lt $reserve) {
            Write-Output "PAUSED_LOW_CACHE task=$($group.Task) path=$relative free_bytes=$free next_file_bytes=$($file.Length) reserve_bytes=$reserve"
            exit 2
        }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target
        $srcHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        $dstHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        if ($srcHash -ne $dstHash) { throw "Hash mismatch: $target" }
        $entry = @{task=$group.Task; source=$file.FullName; destination=$target; bytes=$file.Length; sha256=$srcHash; checked_utc=[DateTime]::UtcNow.ToString('o')}
        [System.IO.File]::AppendAllText($ledger, (($entry | ConvertTo-Json -Compress) + [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
        Write-Output "COPIED task=$($group.Task) bytes=$($file.Length) path=$relative"
    }
}
Write-Output 'LOCAL_COPY_HASH_VERIFICATION_COMPLETE; CLOUD_SYNC_MUST_BE_VERIFIED_SEPARATELY'
