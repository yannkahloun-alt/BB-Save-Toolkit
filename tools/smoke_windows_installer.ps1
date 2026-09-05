[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $IsWindows) {
    throw "Windows installer smoke validation must run on Windows."
}

$installer = (Resolve-Path $InstallerPath).Path
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$fixtureRoot = Join-Path $env:TEMP "BB-Save-Toolkit-smoke"
$fixture = Join-Path $fixtureRoot "synthetic-smoke.sav"
$installRoot = Join-Path $env:LOCALAPPDATA "Programs\BB-Save-Toolkit"
$userStateRoot = Join-Path $env:LOCALAPPDATA "BB-Save-Toolkit"
$runtimeFile = Join-Path $env:TEMP "BB-Save-Toolkit\runtime.json"
$startupShortcut = Join-Path ([Environment]::GetFolderPath("Startup")) "BB Save Toolkit.lnk"
$exe = Join-Path $installRoot "BB-Save-Toolkit.exe"

function New-SyntheticSmokeSave {
    New-Item -ItemType Directory -Force -Path $fixtureRoot | Out-Null
    $env:BBST_SMOKE_FIXTURE = $fixture
    @'
import os
import struct
from pathlib import Path
from bbtool.save_parser import BROTHER_SIGNATURE


def lp(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack("<H", len(raw)) + raw


def identity_blob(name="Synthetic Smoke Brother", level=2, points=1):
    head = lp(name) + lp("")
    q = len(head)
    data = bytearray(head + b"\0" * 80)
    struct.pack_into("<f", data, q, 0.0)
    struct.pack_into("<I", data, q + 4, 100)
    data[q + 14] = level
    data[q + 15] = 1
    data[q + 16] = 0
    data[q + 17] = points
    return bytes(data), q + 18


def star_and_roll_tail():
    stats = ("HP", "Resolve", "Fatigue", "Initiative", "MAtk", "RAtk", "MDef", "RDef")
    data = bytearray()
    data += struct.pack("<f", 0.0)
    data += bytes([0])
    data += b"\0" * 8
    data += bytes((0, 1, 2, 3, 0, 1, 2, 3))
    for _ in stats:
        data += bytes([2, 2, 3])
    return bytes(data)


def build_record():
    signature_offset = 100
    human_offset = 160
    data = bytearray(b"\0" * 1200)
    data[signature_offset:signature_offset + len(BROTHER_SIGNATURE)] = BROTHER_SIGNATURE
    data[signature_offset - 19] = 1
    data[human_offset:human_offset + 5] = b"human"
    ap_offset = human_offset + 10
    data[ap_offset] = 9
    values = (60, 40, 100, 60, 40, 5, 5, 100)
    for index, value in enumerate(values):
        struct.pack_into("<h", data, ap_offset + 1 + 2 * index, value)
    identity_start = ap_offset + 17 + 20
    identity, meta_relative = identity_blob()
    data[identity_start:identity_start + len(identity)] = identity
    meta_end = identity_start + meta_relative
    tail = star_and_roll_tail()
    data[meta_end:meta_end + len(tail)] = tail
    return bytes(data)


Path(os.environ["BBST_SMOKE_FIXTURE"]).write_bytes(build_record())
'@ | python -
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $fixture)) {
        throw "Failed to create deterministic synthetic smoke save."
    }
}

function Invoke-Installer {
    $process = Start-Process -FilePath $installer -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/TASKS=autostart"
    ) -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Installer exited with code $($process.ExitCode)"
    }
    if (-not (Test-Path $exe)) {
        throw "Installed executable is missing."
    }
    if (-not (Test-Path $startupShortcut)) {
        throw "Per-user startup shortcut is missing."
    }
}

function Wait-Runtime {
    param([int]$TimeoutSeconds = 30)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path $runtimeFile) {
            try {
                $runtime = Get-Content $runtimeFile -Raw | ConvertFrom-Json
                if ($runtime.schema -eq "bbtool.windows-runtime.v1" -and $runtime.port) {
                    $origin = "http://127.0.0.1:$($runtime.port)"
                    $health = Invoke-RestMethod -Uri "$origin/api/v1/health" -TimeoutSec 2
                    if ($health.data.status -eq "ok") {
                        return @{ Runtime = $runtime; Origin = $origin }
                    }
                }
            }
            catch {
                # The app may still be binding or replacing the runtime file.
            }
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Installed application did not become healthy."
}

function Start-App {
    Start-Process -FilePath $exe -ArgumentList "background" | Out-Null
    return Wait-Runtime
}

function Stop-App {
    if (Test-Path $exe) {
        $process = Start-Process -FilePath $exe -ArgumentList "stop" -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "Installed application stop command failed with code $($process.ExitCode)"
        }
    }
}

function Get-Session {
    param([string]$Origin)
    return (Invoke-RestMethod -Uri "$Origin/api/v1/session" -TimeoutSec 5).data.token
}

function Invoke-ApiPost {
    param(
        [string]$Origin,
        [string]$Token,
        [string]$Path,
        [hashtable]$Payload
    )
    $headers = @{
        Origin = $Origin
        "X-BBST-Session" = $Token
    }
    return Invoke-RestMethod -Uri "$Origin$Path" -Method Post -Headers $headers `
        -ContentType "application/json" -Body ($Payload | ConvertTo-Json -Compress -Depth 20) `
        -TimeoutSec 30
}

function Request-AnalysisWhenStable {
    param(
        [string]$Origin,
        [string]$Token,
        [int]$PreferencesRevision
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            return Invoke-ApiPost -Origin $Origin -Token $Token -Path "/api/v1/analysis/jobs" `
                -Payload @{ expected_preferences_revision = $PreferencesRevision }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Selected save never became stable enough to analyze."
}

function Assert-PersistedState {
    param(
        [string]$Origin,
        [string]$ExpectedSave,
        [string]$ExpectedBuildId
    )
    $followed = (Invoke-RestMethod -Uri "$Origin/api/v1/followed-save" -TimeoutSec 5).data
    if ([string]$followed.selected_path -ne $ExpectedSave) {
        throw "Selected save did not survive the application lifecycle."
    }
    $catalog = (Invoke-RestMethod -Uri "$Origin/api/v1/archetypes" -TimeoutSec 5).data
    $ids = @($catalog.roles | ForEach-Object { [string]$_.id })
    if ($ExpectedBuildId -notin $ids) {
        throw "User archetype state did not survive the application lifecycle."
    }
}

if (Test-Path $userStateRoot) {
    throw "Smoke validation requires a clean user-state root: $userStateRoot"
}
New-SyntheticSmokeSave

Invoke-Installer
$first = Start-App
$firstPid = [int]$first.Runtime.pid
$firstOrigin = [string]$first.Origin

Start-Process -FilePath $exe -ArgumentList "background" -Wait | Out-Null
$duplicate = Wait-Runtime
if ([int]$duplicate.Runtime.pid -ne $firstPid) {
    throw "Second launch created a conflicting application instance."
}

$token = Get-Session -Origin $firstOrigin

# Persist one custom build and reduce the effective catalog to it. Combined with
# the deterministic one-brother/zero-recruit synthetic save, this exercises the
# real installed parser -> worker -> analysis service -> publication path while
# keeping installer CI bounded and independent of the expensive full preview.
$catalog = (Invoke-RestMethod -Uri "$firstOrigin/api/v1/archetypes" -TimeoutSec 5).data
if (@($catalog.roles).Count -lt 1) {
    throw "Installed archetype catalog is empty."
}
$sourceBuildId = [string]$catalog.roles[0].id
$baseBuildIds = @($catalog.roles | ForEach-Object { [string]$_.id })
$duplicated = (Invoke-ApiPost -Origin $firstOrigin -Token $token -Path "/api/v1/archetypes/duplicate" `
    -Payload @{
        id = $sourceBuildId
        expected_revision = [int]$catalog.revision
        name = "Packaging Smoke Build"
    }).data
$customBuild = $duplicated.roles | Where-Object { $_.name -eq "Packaging Smoke Build" } | Select-Object -First 1
if (-not $customBuild) {
    throw "Failed to create deterministic user archetype state."
}
$customBuildId = [string]$customBuild.id
$catalogRevision = [int]$duplicated.revision
foreach ($baseBuildId in $baseBuildIds) {
    $reduced = (Invoke-ApiPost -Origin $firstOrigin -Token $token -Path "/api/v1/archetypes/set-disabled" `
        -Payload @{
            id = $baseBuildId
            disabled = $true
            expected_revision = $catalogRevision
        }).data
    $catalogRevision = [int]$reduced.revision
}
$reducedCatalog = (Invoke-RestMethod -Uri "$firstOrigin/api/v1/archetypes" -TimeoutSec 5).data
$remainingBuildIds = @($reducedCatalog.roles | ForEach-Object { [string]$_.id })
if ($remainingBuildIds.Count -ne 1 -or $remainingBuildIds[0] -ne $customBuildId) {
    throw "Smoke catalog reduction did not leave exactly the custom build."
}

$followed = (Invoke-RestMethod -Uri "$firstOrigin/api/v1/followed-save" -TimeoutSec 5).data
$selected = (Invoke-ApiPost -Origin $firstOrigin -Token $token -Path "/api/v1/followed-save/select" `
    -Payload @{
        path = $fixture
        expected_revision = [int]$followed.revision
        auto_refresh = $false
    }).data
$preferencesRevision = [int]$selected.revision

$jobResponse = Request-AnalysisWhenStable -Origin $firstOrigin -Token $token `
    -PreferencesRevision $preferencesRevision
$jobId = [int]$jobResponse.data.id
$deadline = [DateTime]::UtcNow.AddMinutes(5)
$jobStatus = ""
$reportedStatus = ""
while ([DateTime]::UtcNow -lt $deadline) {
    $job = (Invoke-RestMethod -Uri "$firstOrigin/api/v1/analysis/jobs/$jobId" -TimeoutSec 10).data
    $jobStatus = [string]$job.status
    if ($jobStatus -ne $reportedStatus) {
        Write-Host "Installed analysis job status: $jobStatus"
        $reportedStatus = $jobStatus
    }
    if ($jobStatus -eq "succeeded") {
        break
    }
    if ($jobStatus -in @("failed", "cancelled", "superseded")) {
        throw "Installed analysis job ended as $jobStatus."
    }
    Start-Sleep -Seconds 1
}
if ($jobStatus -ne "succeeded") {
    throw "Installed analysis job did not complete within 5 minutes (last status: $jobStatus)."
}
$result = (Invoke-RestMethod -Uri "$firstOrigin/api/v1/analysis/result" -TimeoutSec 10).data
if (-not $result.available) {
    throw "Installed analysis completed without a published result."
}

Stop-App
$restarted = Start-App
Assert-PersistedState -Origin ([string]$restarted.Origin) -ExpectedSave $fixture -ExpectedBuildId $customBuildId

# Re-running the installer is the supported repair/update path. The selected
# save and custom build must survive installer repair/update without moving the
# durable per-user state into the installation directory.
Invoke-Installer
$updated = Start-App
Assert-PersistedState -Origin ([string]$updated.Origin) -ExpectedSave $fixture -ExpectedBuildId $customBuildId

Stop-App
$uninstaller = Join-Path $installRoot "unins000.exe"
if (-not (Test-Path $uninstaller)) {
    throw "Uninstaller is missing."
}
$process = Start-Process -FilePath $uninstaller -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"
) -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "Uninstaller failed while preserving user data."
}
if (-not (Test-Path $userStateRoot)) {
    throw "Silent uninstall unexpectedly deleted user-owned state."
}

Invoke-Installer
$uninstaller = Join-Path $installRoot "unins000.exe"
$process = Start-Process -FilePath $uninstaller -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DELETEUSERDATA"
) -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "Uninstaller failed while deleting user data."
}
if (Test-Path $userStateRoot) {
    throw "Explicit /DELETEUSERDATA uninstall did not remove user-owned state."
}

Remove-Item -Recurse -Force $fixtureRoot -ErrorAction SilentlyContinue
Write-Output "Windows installer smoke validation passed."
