# Release Process

Git commits are development history. Version numbers are release markers, not per-change counters.

## Release criteria

A release should represent a coherent, validated state intended for gameplay use.

Before release:

```powershell
.\run_tests.ps1
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
.\run_coverage.ps1
```

Run targeted mutation campaigns for correctness-critical modules changed since the previous release.

## Versioning

Update the displayed toolkit version only during release preparation. Add a release entry to `docs/CHANGELOG.md` summarizing user-visible and architectural changes.

## Build the ZIP

The release archive should contain the tracked runtime/source/test files required by the existing release contract, but no local caches, output directories, `.git`, `.sav`, `__pycache__`, or generated mutation/coverage artifacts.

Place release archives under `dist/` locally; `dist/` is ignored by Git.

After creating the archive:

```powershell
python tools\verify_release_zip.py dist\<release>.zip
```

## Tag

After validation and commit:

```powershell
git tag -a vX.Y.Z -m "Battle Brothers Save Toolkit vX.Y.Z"
```

Push the branch/tag only when the release is intentionally published.
