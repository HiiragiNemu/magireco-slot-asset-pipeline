param(
    [Parameter(Mandatory = $true)]
    [string]$InstalledPullRoot,
    [Parameter(Mandatory = $true)]
    [string]$UnpackedProjectRoot
)

$ErrorActionPreference = 'Stop'
$manifestPath = Join-Path $PSScriptRoot '..\reference-inputs.sha256.csv'
$rootMap = @{
    installed_pull = (Resolve-Path -LiteralPath $InstalledPullRoot).Path
    unpacked_project = (Resolve-Path -LiteralPath $UnpackedProjectRoot).Path
}
$failed = 0
$rows = foreach ($row in Import-Csv -LiteralPath $manifestPath) {
    $root = $rootMap[$row.root_key]
    $path = Join-Path $root ($row.relative_path -replace '/', '\')
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $failed++
        [pscustomobject]@{ status = 'missing'; path = $path; expected_sha256 = $row.sha256 }
        continue
    }
    $file = Get-Item -LiteralPath $path
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    $status = if ($file.Length -eq [int64]$row.size_bytes -and $hash -eq $row.sha256) { 'passed' } else { 'mismatch' }
    if ($status -ne 'passed') { $failed++ }
    [pscustomobject]@{ status = $status; path = $path; size_bytes = $file.Length; sha256 = $hash }
}
$rows | Format-Table -AutoSize
if ($failed -gt 0) {
    Write-Error "$failed reference inputs are missing or mismatched"
}
Write-Host "All $($rows.Count) reference inputs passed size and SHA-256 verification."
