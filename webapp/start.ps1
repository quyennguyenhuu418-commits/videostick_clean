# === VideoStick WebApp launcher (PowerShell) ===
# Set environment then start Flask server.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot

# Use venv Python if available
if (Test-Path "$ProjectRoot\venv\Scripts\python.exe") {
    $PythonExe = "$ProjectRoot\venv\Scripts\python.exe"
} else {
    $PythonExe = "python"
}

# Set project root so 'src' package can be imported
$env:PYTHONPATH = $ProjectRoot

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " VideoStick WebApp" -ForegroundColor Cyan
Write-Host " Python: $PythonExe"
Write-Host " URL:    http://127.0.0.1:5555"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

try {
    & $PythonExe "$ProjectRoot\webapp\webapp.py"
} finally {
    Pop-Location
}
