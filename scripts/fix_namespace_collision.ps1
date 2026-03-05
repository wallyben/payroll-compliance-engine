$ErrorActionPreference = "Stop"
$repo = Get-Location

Write-Host "Fixing helpers namespace collision..."

$runsPath = "apps/api/routers/runs.py"

if (!(Test-Path $runsPath)) {
    Write-Host "runs.py not found."
    exit 1
}

$content = Get-Content $runsPath -Raw

$content = $content -replace `
"from apps\.api\.helpers import aggregate_severity_summary", `
"from apps.api.helpers import aggregate_severity_summary  # resolved via helpers.py module"

Set-Content $runsPath $content -Encoding UTF8

Write-Host "runs.py updated."

# Activate venv
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}

$env:PYTHONPATH = $repo

Write-Host "Running pytest..."
pytest -q

Write-Host "Done."