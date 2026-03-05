# scripts\local_verify.ps1
$ErrorActionPreference = "Stop"

Write-Host "== Payroll Compliance: Local Verify =="

# 0) Move to repo root
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
Write-Host "Repo:" (Get-Location)

# 1) Python env (use .venv if present, else create)
if (!(Test-Path ".\.venv")) {
  Write-Host "Creating venv..."
  python -m venv .venv
}

Write-Host "Activating venv..."
. .\.venv\Scripts\Activate.ps1

Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

# 2) Install deps
Write-Host "Installing project..."
pip install -e .

# 3) Run tests
Write-Host "Running pytest..."
pytest -q

# 4) Start API in background (uvicorn)
$env:PYTHONPATH = $repo
$env:APP_ENV = "local"
$env:JWT_SECRET = "dev-secret-change-me"
$env:UPLOAD_DIR = "$repo\storage\uploads"

Write-Host "Starting API on http://127.0.0.1:8000 ..."
$api = Start-Process -PassThru -WindowStyle Minimized `
  -FilePath ".\.venv\Scripts\python.exe" `
  -ArgumentList "-m", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", "8000"

Start-Sleep -Seconds 2

# 5) Health check
Write-Host "Calling /health..."
try {
  $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method GET
  Write-Host "Health OK:" ($health | ConvertTo-Json -Compress)
} catch {
  Write-Host "Health FAILED"
  Stop-Process -Id $api.Id -Force
  throw
}

# 6) Quick scan test (uses your phase1_test_files/01_clean.csv)
# If scan endpoint requires auth, we detect and stop with a clear message.
$testCsv = Join-Path $repo "phase1_test_files\01_clean.csv"
if (!(Test-Path $testCsv)) { throw "Missing test CSV: $testCsv" }

Write-Host "Posting scan request with 01_clean.csv..."
try {
  $form = @{
    file = Get-Item $testCsv
  }
  $scan = Invoke-RestMethod -Uri "http://127.0.0.1:8000/scan" -Method POST -Form $form
  Write-Host "Scan OK (truncated):"
  ($scan | ConvertTo-Json -Depth 6)
} catch {
  if ($_.Exception.Response.StatusCode.value__ -eq 401 -or $_.Exception.Response.StatusCode.value__ -eq 403) {
    Write-Host ""
    Write-Host "Scan endpoint requires auth. Next step:"
    Write-Host " - Run seed script: python apps/api/scripts/seed_admin.py"
    Write-Host " - Then login via /auth and retry scan with token."
  } else {
    Write-Host "Scan FAILED:"
    throw
  }
}

# 7) Stop API
Write-Host "Stopping API..."
Stop-Process -Id $api.Id -Force

Write-Host "== DONE: Local Verify Complete =="