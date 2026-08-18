$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force -Path "tests\coverage" | Out-Null
$env:COVERAGE_FILE = "tests\coverage\.coverage"
$env:COVERAGE_RCFILE = "tests\.coveragerc"
& python -m pytest -c "tests/pytest.ini" -o "cache_dir=tests/cache/pytest" -q -m "not coverage_slow" --cov=bbtool --cov-branch --cov-report=term-missing --cov-report=html:tests/coverage/html --cov-report=json:tests/coverage/coverage.json
$code = $LASTEXITCODE
if ($code -ne 0) { exit $code }
Write-Host ""
Write-Host "BRANCH COVERAGE HTML: tests\coverage\html\index.html" -ForegroundColor Green
Write-Host "BRANCH COVERAGE JSON: tests\coverage\coverage.json" -ForegroundColor Green
