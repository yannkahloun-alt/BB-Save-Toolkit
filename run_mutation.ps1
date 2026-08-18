param(
    [string]$Target = "progression",
    [string[]]$Tests,
    [switch]$All,
    [switch]$ListTargets,
    [switch]$OpenReport,
    [switch]$ReportOnly,
    [switch]$Restore,
    [switch]$AllChild
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

& python -c "import cosmic_ray" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Cosmic Ray is not installed." -ForegroundColor Yellow
    Write-Host "Install test/development dependencies with:" -ForegroundColor Yellow
    Write-Host "python -m pip install -r .\tests\requirements.txt"
    exit 2
}

$scriptsDir = (& python -c "import sysconfig; print(sysconfig.get_path('scripts', scheme='nt_user'))").Trim()

function Resolve-PythonTool([string]$Name) {
    $candidate = Join-Path $scriptsDir ($Name + ".exe")
    if (Test-Path $candidate) { return $candidate }

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Source }

    throw "Unable to locate $Name. Expected it under $scriptsDir or on PATH."
}

$cosmicRay = Resolve-PythonTool "cosmic-ray"
$crReport = Resolve-PythonTool "cr-report"
$crHtml = Resolve-PythonTool "cr-html"


function Get-MutationTargets {
    $items = @()

    Get-ChildItem "bbtool" -Directory -Recurse | ForEach-Object {
        $rel = $_.FullName.Substring((Resolve-Path ".").Path.Length + 1).Replace("\", "/")
        $alias = $rel.Substring("bbtool/".Length)
        $items += [PSCustomObject]@{
            Name = $alias
            Path = $rel
            Kind = "package"
        }
    }

    Get-ChildItem "bbtool" -File -Recurse -Filter "*.py" | Where-Object { $_.Name -ne "__init__.py" } | ForEach-Object {
        $rel = $_.FullName.Substring((Resolve-Path ".").Path.Length + 1).Replace("\", "/")
        $alias = $rel.Substring("bbtool/".Length)
        if ($alias.EndsWith(".py")) { $alias = $alias.Substring(0, $alias.Length - 3) }
        $items += [PSCustomObject]@{
            Name = $alias
            Path = $rel
            Kind = "module"
        }
    }

    return $items | Sort-Object Name
}

function Resolve-MutationTarget([string]$Requested) {
    $normalized = $Requested.Trim().Replace("\", "/")
    if ($normalized -eq "all") {
        return [PSCustomObject]@{ Name = "all"; Path = "bbtool"; Kind = "package" }
    }

    $targets = @(Get-MutationTargets)

    # Exact canonical alias, e.g. projection, projection/scoring, app/main.
    $exact = @($targets | Where-Object { $_.Name -eq $normalized })
    if ($exact.Count -eq 1) { return $exact[0] }

    # Accept bbtool/... and optional .py.
    $pathForm = $normalized
    if ($pathForm.StartsWith("bbtool/")) { $pathForm = $pathForm.Substring(7) }
    if ($pathForm.EndsWith(".py")) { $pathForm = $pathForm.Substring(0, $pathForm.Length - 3) }
    $exact = @($targets | Where-Object { $_.Name -eq $pathForm })
    if ($exact.Count -eq 1) { return $exact[0] }

    # Short basename alias if unique, e.g. "scoring" -> projection/scoring.
    $short = @($targets | Where-Object { ($_.Name.Split("/")[-1]) -eq $normalized })
    if ($short.Count -eq 1) { return $short[0] }
    if ($short.Count -gt 1) {
        $choices = ($short.Name -join ", ")
        throw "Ambiguous mutation target '$Requested'. Use one of: $choices"
    }

    throw "Unknown mutation target '$Requested'. Run .\run_mutation.ps1 -ListTargets to see valid targets."
}

if ($All) {
    $resolved = Resolve-MutationTarget "all"
} else {
    $resolved = Resolve-MutationTarget $Target
}

$profile = $resolved.Name.Replace("/", "__")
$source = $resolved.Path.Replace("/", "\")

# Build a per-run config dynamically so no repackaging is needed for new targets.
$configDir = "tests\mutation\generated"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
$config = Join-Path $configDir "$profile.toml"

function Find-NameMatchedTests([string]$TargetPath, [string]$TargetKind) {
    $matches = New-Object System.Collections.Generic.List[string]

    function Add-TestMatches([string]$Stem) {
        if (-not $Stem) { return }
        $patterns = @(
            "tests\unit\test_$Stem.py",
            "tests\unit\test_${Stem}_*.py",
            "tests\unit\test_*${Stem}*.py",
            "tests\integration\test_$Stem.py",
            "tests\integration\test_${Stem}_*.py",
            "tests\integration\test_*${Stem}*.py"
        )
        foreach ($pattern in $patterns) {
            Get-ChildItem $pattern -File -ErrorAction SilentlyContinue | ForEach-Object {
                $rel = $_.FullName.Substring((Resolve-Path ".").Path.Length + 1)
                if (-not $matches.Contains($rel)) { $matches.Add($rel) }
            }
        }
    }

    if ($TargetKind -eq "module") {
        Add-TestMatches ([System.IO.Path]::GetFileNameWithoutExtension($TargetPath))
    } else {
        Get-ChildItem $TargetPath -Recurse -File -Filter "*.py" |
            Where-Object { $_.Name -ne "__init__.py" } |
            ForEach-Object { Add-TestMatches ([System.IO.Path]::GetFileNameWithoutExtension($_.Name)) }
        Add-TestMatches (Split-Path $TargetPath -Leaf)
    }
    return @($matches | Sort-Object)
}

function Find-ImportMatchedTests([string]$TargetPath, [string]$TargetKind) {
    $selector = "tests\mutation\select_tests.py"
    if (-not (Test-Path $selector)) { return @() }

    $lines = @(& python $selector $TargetPath $TargetKind)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: import-based test discovery failed; continuing with name matching." -ForegroundColor Yellow
        return @()
    }
    return @($lines | Where-Object { $_ } | Sort-Object -Unique)
}


function Get-AutomaticSelectedTests([string]$TargetPath, [string]$TargetKind) {
    $importMatches = @(Find-ImportMatchedTests $TargetPath $TargetKind)
    $nameMatches = @(Find-NameMatchedTests $TargetPath $TargetKind)
    return @(
        $importMatches + $nameMatches |
            ForEach-Object { $_.Replace("\", "/") } |
            Sort-Object -Unique
    )
}

function Get-AllTestFileCount {
    return @(
        Get-ChildItem "tests\unit", "tests\integration" -Recurse -File -Filter "test_*.py" -ErrorAction SilentlyContinue
    ).Count
}


function Get-MutationHistoryPath { return "tests\mutation\mutation-history.json" }

function Read-MutationHistory {
    $path = Get-MutationHistoryPath
    if (-not (Test-Path $path)) { return @{} }
    try {
        $raw = Get-Content $path -Raw | ConvertFrom-Json
        $result = @{}
        foreach ($prop in $raw.PSObject.Properties) { $result[$prop.Name] = $prop.Value }
        return $result
    } catch {
        Write-Host "WARNING: mutation history is unreadable; ignoring it." -ForegroundColor Yellow
        return @{}
    }
}

function Write-MutationHistory([hashtable]$History) {
    $path = Get-MutationHistoryPath
    New-Item -ItemType Directory -Force -Path (Split-Path $path -Parent) | Out-Null
    $ordered = [ordered]@{}
    foreach ($key in @($History.Keys | Sort-Object)) { $ordered[$key] = $History[$key] }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        (Join-Path (Get-Location) $path),
        ($ordered | ConvertTo-Json -Depth 6),
        $utf8NoBom
    )
}

function Get-TimeScale([double]$Seconds) {
    if ($Seconds -lt 3600) { return "minutes" }
    if ($Seconds -lt 86400) { return "hours" }
    return "days"
}

function Get-EstimatedSeconds([string]$Name, [int]$Deps, [int]$Mutants, [hashtable]$History) {
    if ($History.ContainsKey($Name)) {
        $entry = $History[$Name]
        if ($null -ne $entry.elapsed_seconds -and [double]$entry.elapsed_seconds -gt 0) {
            return [double]$entry.elapsed_seconds
        }
    }
    return [Math]::Max(1.0, [double]$Mutants * [Math]::Max(1, $Deps) * 0.20)
}

if ($ListTargets) {
    $inventoryDir = "tests\mutation\generated"
    New-Item -ItemType Directory -Force -Path $inventoryDir | Out-Null
    $inventoryConfig = Join-Path $inventoryDir "_inventory.toml"
    $inventorySession = Join-Path $inventoryDir "_inventory.sqlite"

    $inventoryConfigText = @"
[cosmic-ray]
module-path = "bbtool"
timeout = 60.0
excluded-modules = []
test-command = "python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -q -x"

[cosmic-ray.distributor]
name = "local"
"@

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        (Join-Path (Get-Location) $inventoryConfig),
        $inventoryConfigText,
        $utf8NoBom
    )

    if (Test-Path $inventorySession) { Remove-Item -Force $inventorySession }

    Write-Host "Inventorying potential mutants..." -ForegroundColor DarkGray
    & $cosmicRay init $inventoryConfig $inventorySession | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "cosmic-ray inventory init failed with exit code $LASTEXITCODE"
    }

    $countsJson = & python "tests\mutation\inventory_session.py" $inventorySession
    if ($LASTEXITCODE -ne 0 -or -not $countsJson) {
        throw "Unable to read mutation inventory session."
    }
    $counts = $countsJson | ConvertFrom-Json

    $targets = @(
        [PSCustomObject]@{ Name = "all"; Path = "bbtool"; Kind = "package" }
    ) + @(Get-MutationTargets)
    $fullTestCount = Get-AllTestFileCount
    $history = Read-MutationHistory

    Write-Host "Available mutation targets:" -ForegroundColor Cyan
    foreach ($item in $targets) {
        $selected = @(Get-AutomaticSelectedTests $item.Path $item.Kind)
        $depsText = if ($selected.Count -gt 0) {
            [string]$selected.Count
        } else {
            "FULL/$fullTestCount"
        }

        $mutants = 0
        if ($item.Name -eq "all") {
            foreach ($prop in $counts.modules.PSObject.Properties) {
                if ($prop.Name.StartsWith("bbtool/")) { $mutants += [int]$prop.Value }
            }
        } elseif ($item.Kind -eq "module") {
            $moduleKey = $item.Path.Replace("\", "/")
            $prop = $counts.modules.PSObject.Properties[$moduleKey]
            if ($null -ne $prop) {
                $mutants = [int]$prop.Value
            }
        } else {
            $prefix = $item.Path.Replace("\", "/").TrimEnd("/") + "/"
            foreach ($prop in $counts.modules.PSObject.Properties) {
                if ($prop.Name.StartsWith($prefix)) {
                    $mutants += [int]$prop.Value
                }
            }
        }

        $estimate = Get-EstimatedSeconds $item.Name $selected.Count $mutants $history
        $scale = Get-TimeScale $estimate
        $basis = if ($history.ContainsKey($item.Name)) { "measured" } else { "estimated" }

        Write-Host (
            "  {0,-42} [{1,-7}] deps={2,-8} mutants={3,-6} scale={4,-7} ({5})" -f
            $item.Name, $item.Kind, $depsText, $mutants, $scale, $basis
        ) -ForegroundColor DarkCyan
    }

    Remove-Item -Force $inventorySession -ErrorAction SilentlyContinue
    Remove-Item -Force $inventoryConfig -ErrorAction SilentlyContinue
    exit 0
}


function Invoke-AllMutationTargets {
    if ($Tests -and $Tests.Count -gt 0) {
        throw "-Tests cannot be combined with -Target all/-All; each module selects its own dependencies."
    }
    if ($ReportOnly) {
        throw "-ReportOnly is target-specific and cannot be used with all."
    }

    $history = Read-MutationHistory
    $modules = @(Get-MutationTargets | Where-Object { $_.Kind -eq "module" })

    # One planning-only Cosmic Ray inventory. Execution itself remains per-module.
    $inventoryDir = "tests\mutation\generated"
    New-Item -ItemType Directory -Force -Path $inventoryDir | Out-Null
    $inventoryConfig = Join-Path $inventoryDir "_all_inventory.toml"
    $inventorySession = Join-Path $inventoryDir "_all_inventory.sqlite"
    $inventoryConfigText = @"
[cosmic-ray]
module-path = "bbtool"
timeout = 60.0
excluded-modules = []
test-command = "python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -q -x"

[cosmic-ray.distributor]
name = "local"
"@
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        (Join-Path (Get-Location) $inventoryConfig),
        $inventoryConfigText,
        $utf8NoBom
    )
    if (Test-Path $inventorySession) { Remove-Item -Force $inventorySession }

    Write-Host "Inventorying mutants for module-by-module plan..." -ForegroundColor DarkGray
    & $cosmicRay init $inventoryConfig $inventorySession | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "cosmic-ray all inventory init failed with exit code $LASTEXITCODE"
    }

    $countsJson = & python "tests\mutation\inventory_session.py" $inventorySession
    if ($LASTEXITCODE -ne 0 -or -not $countsJson) {
        throw "Unable to read all mutation inventory."
    }
    $counts = $countsJson | ConvertFrom-Json

    $plan = @()
    foreach ($item in $modules) {
        $deps = @(Get-AutomaticSelectedTests $item.Path $item.Kind)
        $moduleKey = $item.Path.Replace("\\", "/")
        $mutants = 0
        $prop = $counts.modules.PSObject.Properties[$moduleKey]
        if ($null -ne $prop) { $mutants = [int]$prop.Value }

        $estimate = Get-EstimatedSeconds $item.Name $deps.Count $mutants $history
        $plan += [PSCustomObject]@{
            Name = $item.Name
            Deps = $deps.Count
            Mutants = $mutants
            EstimatedSeconds = $estimate
            Scale = Get-TimeScale $estimate
        }
    }

    Remove-Item -Force $inventorySession -ErrorAction SilentlyContinue
    Remove-Item -Force $inventoryConfig -ErrorAction SilentlyContinue

    $plan = @($plan | Sort-Object EstimatedSeconds, Deps, Name)

    Write-Host "Mutation all: module-by-module orchestration" -ForegroundColor Cyan
    Write-Host ("Targets: {0}" -f $plan.Count) -ForegroundColor DarkCyan
    foreach ($item in $plan) {
        Write-Host (
            "  {0,-42} deps={1,-4} mutants={2,-6} scale={3}" -f
            $item.Name, $item.Deps, $item.Mutants, $item.Scale
        ) -ForegroundColor DarkCyan
    }

    $allWatch = [System.Diagnostics.Stopwatch]::StartNew()
    $failed = @()
    $index = 0

    foreach ($item in $plan) {
        $index++
        Write-Host ""
        Write-Host ("=== [{0}/{1}] {2} ===" -f $index, $plan.Count, $item.Name) -ForegroundColor Cyan

        $args = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", $PSCommandPath,
            "-Target", $item.Name,
            "-AllChild"
        )
        if ($OpenReport) { $args += "-OpenReport" }

        & powershell @args
        $childExit = $LASTEXITCODE
        if ($childExit -ne 0) {
            $failed += $item.Name
            Write-Host (
                "FAILED: {0} (exit {1}); continuing." -f $item.Name, $childExit
            ) -ForegroundColor Red
        }
    }

    $allWatch.Stop()
    Write-Host ""
    Write-Host ("All-module elapsed: {0:dd\.hh\:mm\:ss}" -f $allWatch.Elapsed) -ForegroundColor Cyan

    if ($failed.Count -gt 0) {
        Write-Host (
            "Failed targets ({0}): {1}" -f $failed.Count, ($failed -join ", ")
        ) -ForegroundColor Red
        exit 1
    }

    Write-Host ("Completed: {0}/{0}" -f $plan.Count) -ForegroundColor Green
    exit 0
}

if (($All -or $Target -eq "all") -and -not $AllChild) {
    Invoke-AllMutationTargets
}

if ($Tests -and $Tests.Count -gt 0) {
    $selectedTests = @($Tests)
    $testSelectionMode = "explicit -Tests"
} else {
    $importMatches = @(Find-ImportMatchedTests $source $resolved.Kind)
    $nameMatches = @(Find-NameMatchedTests $source $resolved.Kind)

    # Import dependency is the primary signal. Naming remains a documented
    # convention and complements it so well-named black-box tests are retained.
    $selectedTests = @(Get-AutomaticSelectedTests $source $resolved.Kind)

    if ($importMatches.Count -gt 0 -and $nameMatches.Count -gt 0) {
        $testSelectionMode = "automatic import dependency + name matching"
    } elseif ($importMatches.Count -gt 0) {
        $testSelectionMode = "automatic import dependency"
    } elseif ($nameMatches.Count -gt 0) {
        $testSelectionMode = "automatic name matching"
    } else {
        $testSelectionMode = "full-suite fallback"
    }
}

$testArgs = ""
$normalizedTests = @()
if ($selectedTests.Count -gt 0) {
    $normalizedTests = @(
        $selectedTests |
            ForEach-Object { $_.Replace("\", "/") } |
            Sort-Object -Unique
    )
    $testArgs = ($normalizedTests | ForEach-Object { '"' + $_ + '"' }) -join " "
}

$testCommand = "python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -q -x"
if ($testArgs) { $testCommand += " " + $testArgs }

Write-Host "Test selection: $testSelectionMode" -ForegroundColor Cyan
if ($normalizedTests.Count -gt 0) {
    Write-Host ("Selected tests ({0}):" -f $normalizedTests.Count) -ForegroundColor DarkCyan
    $normalizedTests | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkCyan }
} else {
    Write-Host "WARNING: no matching tests found; using the full pytest suite." -ForegroundColor Yellow
}

$configText = @"
[cosmic-ray]
module-path = "$($resolved.Path)"
timeout = 60.0
excluded-modules = []
test-command = "$($testCommand.Replace('"', '\"'))"

[cosmic-ray.distributor]
name = "local"
"@

# PowerShell 5.1 writes a BOM with Set-Content -Encoding utf8.
# Cosmic Ray/TOML treats that BOM as an invalid leading character, so write
# UTF-8 explicitly without BOM for cross-version PowerShell compatibility.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path (Get-Location) $config), $configText, $utf8NoBom)

$resultsRoot = "tests\mutation\results"
$results = Join-Path $resultsRoot $profile
$session = Join-Path $results "$profile.sqlite"
$textReport = Join-Path $results "$profile-report.txt"
$htmlReport = Join-Path $results "$profile-report.html"
$backupRoot = Join-Path "tests\mutation\.backup" $profile

New-Item -ItemType Directory -Force -Path $results | Out-Null

function Write-Reports {
    Write-Host "Generating mutation reports..." -ForegroundColor Cyan
    & $crReport $session --show-pending | Set-Content -Encoding utf8 $textReport
    if ($LASTEXITCODE -ne 0) { throw "cr-report failed with exit code $LASTEXITCODE" }

    & $crHtml $session | Set-Content -Encoding utf8 $htmlReport
    if ($LASTEXITCODE -ne 0) { throw "cr-html failed with exit code $LASTEXITCODE" }

    Write-Host "Text report: $textReport" -ForegroundColor Green
    Write-Host "HTML report: $htmlReport" -ForegroundColor Green

if ((Test-Path "tests\mutation\effective_score.py") -and (Test-Path $textReport)) {
    & python "tests\mutation\effective_score.py" $profile $textReport
}
}

function Backup-Source {
    if (Test-Path $backupRoot) { Remove-Item -Recurse -Force $backupRoot }
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    Set-Content -Encoding utf8 -Path (Join-Path $backupRoot "target-path.txt") -Value $source

    if (Test-Path $source -PathType Container) {
        Set-Content -Encoding utf8 -Path (Join-Path $backupRoot "target-kind.txt") -Value "directory"
        Copy-Item -Recurse -Force $source (Join-Path $backupRoot "source-tree")
    } else {
        Set-Content -Encoding utf8 -Path (Join-Path $backupRoot "target-kind.txt") -Value "file"
        Copy-Item -Force $source (Join-Path $backupRoot "source-file.py")
    }
}

function Restore-Source {
    $kind = (Get-Content (Join-Path $backupRoot "target-kind.txt") -Raw).Trim()
    if ($kind -eq "directory") {
        if (Test-Path $source) { Remove-Item -Recurse -Force $source }
        Copy-Item -Recurse -Force (Join-Path $backupRoot "source-tree") $source
    } elseif ($kind -eq "file") {
        Copy-Item -Force (Join-Path $backupRoot "source-file.py") $source
    } else {
        throw "Unknown mutation backup kind '$kind'."
    }
}


function Find-AbandonedBackup {
    $backupBase = "tests\mutation\.backup"
    if (-not (Test-Path $backupBase)) { return $null }
    $dirs = @(Get-ChildItem $backupBase -Directory -ErrorAction SilentlyContinue)
    if ($dirs.Count -eq 0) { return $null }
    return $dirs[0].FullName
}

function Restore-AbandonedBackup([string]$Path) {
    $meta = Join-Path $Path "target-path.txt"
    $kindMeta = Join-Path $Path "target-kind.txt"
    if (-not (Test-Path $meta) -or -not (Test-Path $kindMeta)) {
        throw "Backup metadata is incomplete: $Path"
    }

    $targetPath = (Get-Content $meta -Raw).Trim()
    $kind = (Get-Content $kindMeta -Raw).Trim()

    if ($kind -eq "directory") {
        $tree = Join-Path $Path "source-tree"
        if (-not (Test-Path $tree)) { throw "Directory backup is missing source-tree: $Path" }
        if (Test-Path $targetPath) { Remove-Item -Recurse -Force $targetPath }
        Copy-Item -Recurse -Force $tree $targetPath
    } elseif ($kind -eq "file") {
        $file = Join-Path $Path "source-file.py"
        if (-not (Test-Path $file)) { throw "File backup is missing source-file.py: $Path" }
        Copy-Item -Force $file $targetPath
    } else {
        throw "Unknown backup kind '$kind' in $Path"
    }

    Remove-Item -Recurse -Force $Path
    Write-Host "Abandoned mutation backup restored." -ForegroundColor Green
}

$abandoned = Find-AbandonedBackup
if ($Restore) {
    if ($null -eq $abandoned) {
        Write-Host "No abandoned mutation backup found." -ForegroundColor Green
    } else {
        Write-Host "Restoring abandoned mutation backup..." -ForegroundColor Yellow
        Restore-AbandonedBackup $abandoned
    }
    exit 0
}

if ($null -ne $abandoned) {
    Write-Host "Previous interrupted mutation run detected." -ForegroundColor Yellow
    Write-Host "Restoring sources before starting a new run..." -ForegroundColor Yellow
    Restore-AbandonedBackup $abandoned
}

if ($ReportOnly) {
    if (-not (Test-Path $session)) {
        Write-Host "No mutation session found at $session" -ForegroundColor Red
        exit 2
    }
    Write-Reports
    if ($OpenReport) { Start-Process $htmlReport }
    exit 0
}

Backup-Source
$watch = [System.Diagnostics.Stopwatch]::StartNew()
$execProcess = $null

try {
    if (Test-Path $session) { Remove-Item -Force $session }

    Write-Host "Mutation profile: $profile" -ForegroundColor Cyan
    Write-Host "Mutation target: $source" -ForegroundColor Cyan

    # Cosmic Ray 8.7 decodes captured pytest output as UTF-8. Force Python and
    # pytest to emit UTF-8 even on Windows consoles using a legacy code page.
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"

    Write-Host "Initializing Cosmic Ray session..." -ForegroundColor Cyan

    & $cosmicRay init $config $session
    if ($LASTEXITCODE -ne 0) { throw "cosmic-ray init failed with exit code $LASTEXITCODE" }

    # Initialization creates the full work queue. Report it before execution so
    # a global campaign immediately exposes its scale.
    $initSummary = (& $crReport $session --no-show-diff --no-show-output --no-show-pending | Select-Object -Last 3)
    $initSummary | ForEach-Object { Write-Host $_ -ForegroundColor DarkCyan }

    Write-Host "Running unmutated baseline..." -ForegroundColor Cyan
    & $cosmicRay baseline $config
    if ($LASTEXITCODE -ne 0) { throw "cosmic-ray baseline failed with exit code $LASTEXITCODE" }

    Write-Host "Executing mutants..." -ForegroundColor Cyan

    $execProcess = Start-Process -FilePath $cosmicRay `
        -ArgumentList @("exec", $config, $session) `
        -NoNewWindow -PassThru

    $lastComplete = -1
    $lastDisplay = [DateTime]::MinValue
    $lastSampleComplete = 0
    $lastSampleTime = Get-Date

    while (-not $execProcess.HasExited) {
        Start-Sleep -Seconds 5

        $statsJson = & python "tests\mutation\session_progress.py" $session

        if ($LASTEXITCODE -eq 0 -and $statsJson) {
            try {
                $stats = $statsJson | ConvertFrom-Json
                $complete = [int]$stats.complete
                $total = [int]$stats.total

                if ($total -gt 0) {
                    $elapsed = $watch.Elapsed
                    $pct = 100.0 * $complete / $total

                    if ($complete -gt 0) {
                        $secondsPerJob = $elapsed.TotalSeconds / $complete
                        $remainingSeconds = $secondsPerJob * ($total - $complete)
                        $eta = [TimeSpan]::FromSeconds($remainingSeconds)
                        $etaText = ("{0:hh\:mm\:ss}" -f $eta)
                    } else {
                        $etaText = "--:--:--"
                    }

                    if ($complete -ne $lastComplete -or ((Get-Date) - $lastDisplay).TotalSeconds -ge 30) {
                        $now = Get-Date
                        $sampleJobs = $complete - $lastSampleComplete
                        $sampleSeconds = ($now - $lastSampleTime).TotalSeconds
                        if ($sampleJobs -gt 0 -and $sampleSeconds -gt 0) {
                            $testSecondsPerJob = $sampleSeconds / $sampleJobs
                            $testTimeText = ("{0:N2}s/job" -f $testSecondsPerJob)
                            $lastSampleComplete = $complete
                            $lastSampleTime = $now
                        } else {
                            $testTimeText = "--"
                        }

                        Write-Host ("Progress: {0}/{1} ({2:N2}%) | Test {3} | Elapsed {4:hh\:mm\:ss} | ETA {5}" -f `
                            $complete, $total, $pct, $testTimeText, $elapsed, $etaText) -ForegroundColor DarkCyan
                        $lastComplete = $complete
                        $lastDisplay = $now
                    }
                }
            } catch {
                Write-Host "Progress: session readable, stats pending..." -ForegroundColor DarkGray
            }
        }

        $execProcess.Refresh()
    }

    $execProcess.WaitForExit()
    $execProcess.Refresh()

    # PowerShell 5.1 can expose a blank ExitCode for a Start-Process -PassThru
    # child even after WaitForExit(). The Cosmic Ray session itself is the
    # authoritative completion signal: every initialized work item must have a
    # work result. Only treat the run as failed when the session is incomplete.
    $finalStatsJson = & python "tests\mutation\session_progress.py" $session
    if ($LASTEXITCODE -ne 0 -or -not $finalStatsJson) {
        throw "Unable to read final Cosmic Ray session state."
    }
    $finalStats = $finalStatsJson | ConvertFrom-Json
    $finalComplete = [int]$finalStats.complete
    $finalTotal = [int]$finalStats.total

    if ($finalTotal -eq 0 -and $finalComplete -eq 0) {
        Write-Host "No mutants generated for target (0 jobs)." -ForegroundColor Green
    }
    elseif ($finalTotal -le 0 -or $finalComplete -ne $finalTotal) {
        $exitCodeText = if ($null -eq $execProcess.ExitCode) { "unknown" } else { [string]$execProcess.ExitCode }
        throw "cosmic-ray exec incomplete ($finalComplete/$finalTotal jobs, exit code $exitCodeText)"
    }
    else {
        Write-Host ("Cosmic Ray session complete: {0}/{1} jobs." -f $finalComplete, $finalTotal) -ForegroundColor Green
        Write-Reports
    }
}
finally {
    if ($null -ne $execProcess -and -not $execProcess.HasExited) {
        Write-Host "Stopping Cosmic Ray before source restoration..." -ForegroundColor Yellow
        Stop-Process -Id $execProcess.Id -Force -ErrorAction SilentlyContinue
        try { $execProcess.WaitForExit(5000) | Out-Null } catch {}
    }

    Restore-Source

    # Verify that every restored source file is byte-identical to the backup.
    $mismatch = $false
    $kind = (Get-Content (Join-Path $backupRoot "target-kind.txt") -Raw).Trim()

    if ($kind -eq "directory") {
        $backupTree = Join-Path $backupRoot "source-tree"
        $backupFiles = @(Get-ChildItem $backupTree -Recurse -File)
        $sourceRoot = (Resolve-Path $source).Path
        $backupRootResolved = (Resolve-Path $backupTree).Path

        foreach ($backupFile in $backupFiles) {
            $relative = $backupFile.FullName.Substring($backupRootResolved.Length).TrimStart('\')
            $restored = Join-Path $sourceRoot $relative
            if (-not (Test-Path $restored)) { $mismatch = $true; break }
            if ((Get-FileHash $backupFile.FullName -Algorithm SHA256).Hash -ne (Get-FileHash $restored -Algorithm SHA256).Hash) {
                $mismatch = $true
                break
            }
        }

        if (-not $mismatch) {
            $restoredCount = @(Get-ChildItem $source -Recurse -File).Count
            if ($restoredCount -ne $backupFiles.Count) { $mismatch = $true }
        }
    } elseif ($kind -eq "file") {
        $backupHash = (Get-FileHash (Join-Path $backupRoot "source-file.py") -Algorithm SHA256).Hash
        $restoredHash = (Get-FileHash $source -Algorithm SHA256).Hash
        $mismatch = ($backupHash -ne $restoredHash)
    } else {
        $mismatch = $true
    }

    if ($mismatch) {
        Write-Host "WARNING: source restoration hash mismatch." -ForegroundColor Red
    } else {
        Write-Host "Source restoration verified." -ForegroundColor Green
    }

    if (Test-Path $backupRoot) { Remove-Item -Recurse -Force $backupRoot }
    $watch.Stop()
    Write-Host ("Elapsed: {0:hh\:mm\:ss}" -f $watch.Elapsed) -ForegroundColor Cyan
}


$history = Read-MutationHistory
$statsTotal = 0
if (Test-Path $session) {
    $statsJson = & python "tests\mutation\session_progress.py" $session
    if ($LASTEXITCODE -eq 0 -and $statsJson) {
        try {
            $statsTotal = [int](($statsJson | ConvertFrom-Json).total)
        } catch {}
    }
}

$history[$resolved.Name] = [ordered]@{
    elapsed_seconds = [Math]::Round($watch.Elapsed.TotalSeconds, 3)
    scale = Get-TimeScale $watch.Elapsed.TotalSeconds
    deps = [int]$normalizedTests.Count
    mutants = [int]$statsTotal
    last_run = (Get-Date).ToString("s")
    exit_code = 0
}
Write-MutationHistory $history

if ($OpenReport) {
    Start-Process $htmlReport
}
