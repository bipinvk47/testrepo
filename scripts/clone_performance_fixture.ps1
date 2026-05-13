Param(
    [string]$Repo = "https://github.com/django/django.git",
    [string]$Ref = "5.1.11"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Parent = Join-Path $RepoRoot "fixtures\benchmark-subject"
$Target = Join-Path $Parent "django"

New-Item -ItemType Directory -Force -Path $Parent | Out-Null

if (Test-Path $Target) {
    Write-Host "Already exists: $Target"
    Write-Host "Remove the folder manually to reclone, or run: git -C `"$Target`" fetch --depth 1 origin tag $Ref"
    exit 0
}

Write-Host "Shallow cloning $Repo (ref=$Ref) into $Target ..."
git clone --depth 1 --branch $Ref $Repo $Target
Write-Host "Done. Use: python scripts/whitebox_metrics.py --root `"$RepoRoot`" --with-benchmark-fixture -o metrics/whitebox_report.json"
