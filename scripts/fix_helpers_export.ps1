# scripts\fix_helpers_export.ps1
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

Write-Host "== Fixing helpers export =="

$scanSummaryPath = "apps/api/helpers/scan_summary.py"
$initPath = "apps/api/helpers/__init__.py"

if (!(Test-Path $scanSummaryPath)) {
    Write-Host "ERROR: scan_summary.py not found."
    exit 1
}

$scanContent = Get-Content $scanSummaryPath -Raw

if ($scanContent -notmatch "def\s+aggregate_severity_summary") {
    Write-Host "ERROR: aggregate_severity_summary not found in scan_summary.py"
    exit 1
}

Write-Host "Function found. Updating __init__.py..."

@"
from .scan_summary import aggregate_severity_summary

__all__ = ["aggregate_severity_summary"]
"@ | Set-Content $initPath -Encoding UTF8

Write-Host "__init__.py updated."

# Activate venv
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}

$env:PYTHONPATH = $repo

Write-Host "Running pytest..."
pytest -q

Write-Host "== Done =="