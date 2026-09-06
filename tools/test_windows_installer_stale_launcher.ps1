[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $IsWindows) {
    throw "Windows installer stale-launcher validation must run on Windows."
}

$installer = (Resolve-Path $InstallerPath).Path
$installRoot = Join-Path $env:LOCALAPPDATA "Programs\BB-Save-Toolkit"
$userStateRoot = Join-Path $env:LOCALAPPDATA "BB-Save-Toolkit"
$exe = Join-Path $installRoot "BB-Save-Toolkit.exe"
$runtimeRoot = Join-Path $env:TEMP "BB-Save-Toolkit"
$startupShortcut = Join-Path ([Environment]::GetFolderPath("Startup")) "BB Save Toolkit.lnk"

function Invoke-Installer {
    $process = Start-Process -FilePath $installer -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/TASKS=autostart"
    ) -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Installer exited with code $($process.ExitCode)"
    }
    if (-not (Test-Path $exe -PathType Leaf)) {
        throw "Installed executable is missing after repair."
    }
}

function Remove-TestInstallation {
    if (Test-Path $exe -PathType Leaf) {
        $stop = Start-Process -FilePath $exe -ArgumentList "stop" -Wait -PassThru
        if ($stop.ExitCode -ne 0) {
            throw "Repaired application stop command failed with code $($stop.ExitCode)"
        }
    }
    $uninstaller = Join-Path $installRoot "unins000.exe"
    if (Test-Path $uninstaller -PathType Leaf) {
        $process = Start-Process -FilePath $uninstaller -ArgumentList @(
            "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DELETEUSERDATA"
        ) -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "Uninstaller exited with code $($process.ExitCode)"
        }
    }
    Remove-Item $runtimeRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $startupShortcut -Force -ErrorAction SilentlyContinue
}

if (Test-Path $installRoot) {
    throw "Stale-launcher validation requires a clean installation root: $installRoot"
}
if (Test-Path $userStateRoot) {
    throw "Stale-launcher validation requires a clean user-state root: $userStateRoot"
}

try {
    Invoke-Installer

    # Silent installation does not launch the application. Replace only the installed
    # executable with invalid bytes to model the real upgrade boundary: an old
    # PyInstaller launcher remains on disk but no BB Save Toolkit instance/mutex exists.
    [System.IO.File]::WriteAllText($exe, "not-a-valid-windows-executable")

    Invoke-Installer

    # A repaired launcher with no running server must initialize normally and report
    # status=not-running (exit 1), rather than failing its embedded Python bootstrap.
    $status = Start-Process -FilePath $exe -ArgumentList "status" -Wait -PassThru
    if ($status.ExitCode -ne 1) {
        throw "Repaired launcher status returned $($status.ExitCode); expected 1 for no running app."
    }
}
finally {
    Remove-TestInstallation
}
