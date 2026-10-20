# Starts the FastAPI backend on http://localhost:8000 (auto-reloads when you edit code).
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "The virtual environment is missing. Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
