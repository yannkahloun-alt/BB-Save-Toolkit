param(
    [switch]$Tests
)

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

& python -c "import pyflakes" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Pyflakes is not installed." -ForegroundColor Yellow
    Write-Host "Install test/development dependencies with:" -ForegroundColor Yellow
    Write-Host "python -m pip install -r .\tests\requirements.txt"
    exit 2
}

$targets = @("bbtool", "bb_analyze.py")
if ($Tests) {
    $targets += "tests"
}

Write-Host "Running Pyflakes..." -ForegroundColor Cyan
& python -m pyflakes @targets
$code = $LASTEXITCODE

if ($code -eq 0) {
    Write-Host ""
    Write-Host "PYFLAKES CLEAN" -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "PYFLAKES FOUND ISSUES (exit code $code)" -ForegroundColor Red
exit $code
