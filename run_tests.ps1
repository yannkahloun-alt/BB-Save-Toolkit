param(
    [Parameter(Position=0)]
    [string]$Suite = "all"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Pytest([string[]]$PytestArgs) {
    & python -m pytest -c "tests/pytest.ini" -o "cache_dir=tests/cache/pytest" @PytestArgs
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        Write-Host ""
        Write-Host "TESTS FAILED (exit code $code)" -ForegroundColor Red
        exit $code
    }
    Write-Host ""
    Write-Host "ALL REQUESTED TESTS PASSED" -ForegroundColor Green
}

switch ($Suite.ToLowerInvariant()) {
    "all"         { Invoke-Pytest @("-q") }
    "unit"        { Invoke-Pytest @("tests/unit", "-q") }
    "integration" { Invoke-Pytest @("tests/integration", "-q") }
    "slow"        { Invoke-Pytest @("-m", "slow", "-q") }
    "parser"      { Invoke-Pytest @("-m", "parser", "-q") }
    "ui"          { Invoke-Pytest @("-m", "ui", "-q") }
    "advisor"     { Invoke-Pytest @("-k", "advisor", "-q") }
    "coverage"    { & "$PSScriptRoot\run_coverage.ps1"; exit $LASTEXITCODE }
    default {
        Write-Host "Unknown test suite: $Suite" -ForegroundColor Red
        Write-Host "Valid values: all, unit, integration, slow, parser, ui, advisor, coverage"
        exit 2
    }
}
