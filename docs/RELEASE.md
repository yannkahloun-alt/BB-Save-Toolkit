# Release Process

Git commits are development history. Version numbers are release markers, not per-change counters.

## Release criteria

A release should represent a coherent, validated state intended for gameplay use.

Start the manual **Release validation** workflow from the GitHub Actions page,
select the exact branch or tag candidate, and enter its release version. The
workflow keeps release work separate from pull-request CI and records stable
`release-tests`, `release-quality`, `release-package`, and `release-summary`
jobs against the exact commit.

The workflow runs:

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
.\run_coverage.ps1
```

It then creates a ZIP from the validated commit's tracked files, runs
`tools/verify_release_zip.py`, and uploads the verified ZIP as a downloadable
workflow artifact retained for 30 days. The run summary records the requested
version, ref, full commit SHA, and every stage outcome, providing the audit trail
for the release candidate.

`coverage_slow` and mutation testing are deliberately not part of this workflow
and are not required for it to pass. Run either gate separately only when an
explicit pre-release decision calls for it.

## Versioning

Update the displayed toolkit version only during release preparation. Add a release entry to `docs/CHANGELOG.md` summarizing user-visible and architectural changes.

## Build the ZIP

The release archive should contain the tracked runtime/source/test files required by the existing release contract, but no local caches, output directories, `.git`, `.sav`, `__pycache__`, or generated mutation/coverage artifacts.

The GitHub workflow builds the archive from tracked files with `git archive`,
places it under `dist/` on the runner, verifies it, and uploads it. For an
explicit local build, place release archives under `dist/`; `dist/` is ignored
by Git.

After creating the archive:

```powershell
python tools\verify_release_zip.py dist\<release>.zip
```

## Tag

After validation and commit:

```powershell
git tag -a vX.Y.Z -m "Battle Brothers Save Toolkit vX.Y.Z"
```

Downloading a validated workflow artifact does not publish a GitHub Release or
push a tag. Push the branch/tag and create the GitHub Release only when the
release is intentionally published.
