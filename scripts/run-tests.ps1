# Runs every automated check: backend tests, frontend tests, and the frontend type-check + build.
# No API key or internet connection is needed (the backend tests use a mock LLM and a test-only embedder).
$root = Split-Path -Parent $PSScriptRoot
$failed = @()

Set-Location "$root\backend"
& .\.venv\Scripts\python.exe -m pytest
if ($LASTEXITCODE -ne 0) { $failed += "backend tests" }

Set-Location "$root\frontend"
npm test
if ($LASTEXITCODE -ne 0) { $failed += "frontend tests" }
npm run build
if ($LASTEXITCODE -ne 0) { $failed += "frontend type-check/build" }

Write-Host ""
if ($failed.Count -eq 0) { Write-Host "All checks passed." -ForegroundColor Green }
else { Write-Host ("FAILED: " + ($failed -join ", ")) -ForegroundColor Red; exit 1 }
