# Starts the React dev server on http://localhost:5173 (run the backend in another window first).
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\frontend"
if (-not (Test-Path "node_modules")) {
    Write-Host "Packages are missing. Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}
npm run dev
