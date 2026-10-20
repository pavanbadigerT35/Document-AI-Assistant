# One-time setup on Windows. From the project root run:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE). See the message above." } }

Write-Host "== Backend: virtual environment and packages ==" -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv } else { python -m venv .venv }
    Check "Creating the virtual environment"
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
Check "Upgrading pip"
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Check "Installing backend packages"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created backend\.env  (add your GROQ_API_KEY there to enable chat and quizzes)" -ForegroundColor Yellow
}

Write-Host "== Frontend: packages ==" -ForegroundColor Cyan
Set-Location "$root\frontend"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
npm install
Check "npm install"

Write-Host ""
Write-Host "Setup finished. Next:" -ForegroundColor Green
Write-Host "  1. (optional) edit backend\.env and set GROQ_API_KEY"
Write-Host "  2. Terminal 1:  powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1"
Write-Host "  3. Terminal 2:  powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1"
Write-Host "  4. Open http://localhost:5173"
