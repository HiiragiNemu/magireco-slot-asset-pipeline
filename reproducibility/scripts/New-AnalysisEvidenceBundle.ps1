param(
    [Parameter(Mandatory = $true)]
    [string]$AssetManifestRoot,
    [Parameter(Mandatory = $true)]
    [string]$ResearchRoot,
    [Parameter(Mandatory = $true)]
    [string]$BiliRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutDir
)

$ErrorActionPreference = 'Stop'
$allowedExtensions = @('.csv', '.json', '.md', '.txt', '.srt')
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bundleName = "magireco-analysis-evidence-v18-$stamp"
$staging = Join-Path (Resolve-Path -LiteralPath $OutDir).Path $bundleName
New-Item -ItemType Directory -Path $staging -ErrorAction Stop | Out-Null

function Copy-EvidenceTree {
    param([string]$Source, [string]$Destination)
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) { return }
    $sourceRoot = (Resolve-Path -LiteralPath $Source).Path
    foreach ($file in Get-ChildItem -LiteralPath $sourceRoot -Recurse -File) {
        if ($allowedExtensions -notcontains $file.Extension.ToLowerInvariant()) { continue }
        $relative = $file.FullName.Substring($sourceRoot.Length).TrimStart('\')
        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target
    }
}

Copy-EvidenceTree $AssetManifestRoot (Join-Path $staging 'asset_manifests')
Copy-EvidenceTree (Join-Path $ResearchRoot 'manifests') (Join-Path $staging 'research_manifests')
Copy-EvidenceTree (Join-Path $ResearchRoot 'production_manifests_v18') (Join-Path $staging 'production_manifests_v18')
foreach ($capture in @('runtime_sequence_20260613', 'runtime_sequence_20260618', 'runtime_sequence_20260619')) {
    Copy-EvidenceTree (Join-Path $ResearchRoot "$capture\resolved") (Join-Path $staging "$capture\resolved")
}
Copy-EvidenceTree (Join-Path $BiliRoot 'event_timeline_official') (Join-Path $staging 'event_timeline_official')
Copy-EvidenceTree (Join-Path $BiliRoot 'cri_official_video_map') (Join-Path $staging 'cri_official_video_map')

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$unpackedProjectRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $AssetManifestRoot)).Path
$pathReplacements = [ordered]@{
    $unpackedProjectRoot = '${UNPACKED_PROJECT_ROOT}'
    ((Resolve-Path -LiteralPath $ResearchRoot).Path) = '${RESEARCH_ROOT}'
    ((Resolve-Path -LiteralPath $BiliRoot).Path) = '${BILI_ROOT}'
    $repoRoot = '${REPOSITORY_ROOT}'
    'A:\magireco_installed_pull_20260603' = '${INSTALLED_PULL_ROOT}'
    'A:\magireco_final_mp4_videos' = '${LEGACY_MEDIA_ROOT}'
}
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
foreach ($file in Get-ChildItem -LiteralPath $staging -Recurse -File) {
    $text = [System.IO.File]::ReadAllText($file.FullName)
    foreach ($entry in $pathReplacements.GetEnumerator()) {
        $key = [string]$entry.Key
        $value = [string]$entry.Value
        $text = $text.Replace($key, $value)
        $text = $text.Replace($key.Replace('\', '/'), $value)
        $text = $text.Replace($key.Replace('\', '\\'), $value)
    }
    $text = $text.Replace('C:\\Users\\cryne\\', '${USER_HOME}/')
    $text = $text.Replace('C:\Users\cryne\', '${USER_HOME}/')
    $text = $text.Replace('A:\\', '${A_DRIVE}/')
    $text = $text.Replace('A:\', '${A_DRIVE}/')
    $text = $text.Replace('D:\\', '${D_DRIVE}/')
    $text = $text.Replace('D:\', '${D_DRIVE}/')
    [System.IO.File]::WriteAllText($file.FullName, $text, $utf8NoBom)
}

$index = foreach ($file in Get-ChildItem -LiteralPath $staging -Recurse -File | Sort-Object FullName) {
    [pscustomobject]@{
        relative_path = $file.FullName.Substring($staging.Length).TrimStart('\').Replace('\', '/')
        size_bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    }
}
$index | Export-Csv -LiteralPath (Join-Path $staging 'BUNDLE_CONTENTS.csv') -NoTypeInformation -Encoding utf8
$zipPath = Join-Path (Split-Path -Parent $staging) "$bundleName.zip"
Compress-Archive -LiteralPath $staging -DestinationPath $zipPath -CompressionLevel Optimal
$zip = Get-Item -LiteralPath $zipPath
[pscustomobject]@{
    path = $zip.FullName
    size_bytes = $zip.Length
    sha256 = (Get-FileHash -LiteralPath $zip.FullName -Algorithm SHA256).Hash
    evidence_files = $index.Count
} | ConvertTo-Json
