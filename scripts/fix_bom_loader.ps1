$ErrorActionPreference = "Stop"
$repo = Get-Location
Write-Host "== Fixing BOM config loader =="

$configLoader = "apps/api/config_loader.py"

if (!(Test-Path $configLoader)) {
    Write-Host "config_loader.py not found."
    exit 1
}

$content = Get-Content $configLoader -Raw

$content = $content -replace 'encoding="utf-8"', 'encoding="utf-8-sig"'

Set-Content $configLoader $content -Encoding UTF8

Write-Host "Updated encoding to utf-8-sig."

# Activate venv
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}

$env:PYTHONPATH = $repo

Write-Host "Running pytest..."
pytest -q

Write-Host "== Done =="