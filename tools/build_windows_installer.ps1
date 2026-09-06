[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$SignCommand = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $IsWindows) {
    throw "Windows installer builds must run on Windows."
}

$normalizedVersion = $Version.Trim()
if ($normalizedVersion.StartsWith("v", [System.StringComparison]::OrdinalIgnoreCase)) {
    $normalizedVersion = $normalizedVersion.Substring(1)
}
if ($normalizedVersion -notmatch '^\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.-]+)?$') {
    throw "Version must look like 3.89 or 3.89.1."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$specPath = Join-Path $repoRoot "packaging\windows\BB-Save-Toolkit.spec"
$issPath = Join-Path $repoRoot "packaging\windows\BB-Save-Toolkit.iss"
$generatedReferenceCaches = @(
    "dictionary.json",
    "backgrounds.json",
    "perk_effects.json",
    "trait_effects.json",
    "permanent_injury_effects.json",
    "perk_audit.json"
)

Push-Location $repoRoot
try {
    # Packaging must not inherit a developer/worktree runtime cache. In particular,
    # a schema-valid but partial/stale generated cache would otherwise cause
    # ensure_references() to skip regeneration and PyInstaller would ship it.
    # Remove only the documented generated caches, then rebuild all of them from
    # the repository-pinned immutable sources before collecting package data.
    foreach ($name in $generatedReferenceCaches) {
        Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $repoRoot "references\$name")
    }

    python -c "from references.update_references import ensure_references; ensure_references(verbose=False)"
    if ($LASTEXITCODE -ne 0) {
        throw "Reference bundle generation failed."
    }
    foreach ($name in $generatedReferenceCaches) {
        if (-not (Test-Path (Join-Path $repoRoot "references\$name"))) {
            throw "Required generated reference is missing: $name"
        }
    }

    python -m PyInstaller --clean --noconfirm $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    $compilerCandidates = @()
    if ($env:INNO_SETUP_COMPILER) {
        $compilerCandidates += $env:INNO_SETUP_COMPILER
    }
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        $compilerCandidates += $command.Source
    }
    $compilerCandidates += @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $iscc = $compilerCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup 6 compiler (ISCC.exe) was not found. Set INNO_SETUP_COMPILER or install Inno Setup 6."
    }

    $arguments = @("/Qp", "/DAppVersion=$normalizedVersion")
    if ($SignCommand) {
        $arguments += "/DSignedBuild=1"
        $arguments += "/Ssigntool=$SignCommand"
    }
    $arguments += $issPath
    & $iscc @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup build failed."
    }

    $installer = Join-Path $repoRoot "dist\windows\BB-Save-Toolkit-$normalizedVersion-setup.exe"
    if (-not (Test-Path $installer)) {
        throw "Expected installer was not produced: $installer"
    }
    Write-Output $installer
}
finally {
    Pop-Location
}
