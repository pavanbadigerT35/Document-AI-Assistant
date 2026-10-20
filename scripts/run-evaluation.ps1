# Measures retrieval quality with the REAL embedding model (downloads it on first use, ~90 MB).
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-evaluation.ps1                    -> the two synthetic sample PDFs
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-evaluation.ps1 -Syllabus "C:\path\syllabus.pdf"   -> your syllabus
param([string]$Syllabus = "")
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"
if ($Syllabus) {
    & .\.venv\Scripts\python.exe -m evaluation.run_eval --pdf $Syllabus
} else {
    & .\.venv\Scripts\python.exe -m evaluation.run_eval --pdf "$root\samples\sample_api_testing_notes.pdf" "$root\samples\sample_cicd_pipeline_notes.pdf" --dataset evaluation\sample_dataset.json
}
