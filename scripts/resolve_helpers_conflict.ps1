$ErrorActionPreference = "Stop"
$repo = Get-Location

Write-Host "== Resolving helpers namespace conflict =="

$fileModule = "apps/api/helpers.py"
$packageDir = "apps/api/helpers"
$initFile = "apps/api/helpers/__init__.py"
$newFile = "apps/api/helpers/aggregate.py"

if (!(Test-Path $fileModule)) {
    Write-Host "helpers.py not found. Nothing to move."
    exit 1
}

Write-Host "Moving helpers.py contents into helpers/aggregate.py..."

# Move contents
Get-Content $fileModule | Set-Content $newFile -Encoding UTF8

# Remove original file
Remove-Item $fileModule -Force

Write-Host "Updating __init__.py export..."

@"
from .aggregate import aggregate_severity_summary

__all__ = ["aggregate_severity_summary"]
"@ | Set-Content $initFile -Encoding UTF8

# Activate venv if exists
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}

$env:PYTHONPATH = $repo

Write-Host "Running pytest..."
pytest -q

Write-Host "== Done =="