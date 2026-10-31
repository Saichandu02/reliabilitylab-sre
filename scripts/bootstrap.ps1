# Bootstrap on Windows (PowerShell equivalent of bootstrap.sh)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python --version
python -m venv .venv
.\.venv\Scripts\pip install -q -r requirements-dev.txt
Write-Host "Bootstrap complete. Run: .\.venv\Scripts\python -m pytest -q"
Write-Host "Serve:    `$env:DATABASE_PATH='data/orders.db'; .\.venv\Scripts\uvicorn app.main:app --port 8000"
