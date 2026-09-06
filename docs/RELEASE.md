# Release Process

Git commits are development history. Version numbers are release markers, not per-change counters.

## Release criteria

A release should represent a coherent, validated state intended for gameplay use.

Release publication is bound to one exact commit SHA. For releases that publish the Windows application (v3.89+), both the repository release-validation workflow and the Windows-installer workflow must succeed against that same candidate before tagging or publication.

### Release validation

Start the manual **Release validation** workflow from the GitHub Actions page, select the exact branch or tag candidate, and enter its release version. The workflow keeps release work separate from pull-request CI and records stable `release-tests`, `release-quality`, `release-package`, and `release-summary` jobs against the exact commit.

The entered version must exactly match the first release heading in `docs/CHANGELOG.md`; the workflow rejects a mismatch before packaging. This binds the artifact name and audit summary to version metadata in the selected commit.

The workflow runs:

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
.\run_coverage.ps1
```

It then creates a ZIP from the validated commit's tracked files, runs `tools/verify_release_zip.py`, and uploads the verified ZIP as a downloadable workflow artifact retained for 30 days. The run summary records the requested version, ref, full commit SHA, and every stage outcome, providing the audit trail for the release candidate.

`coverage_slow` and mutation testing are deliberately not part of this workflow and are not required for it to pass. Run either gate separately only when an explicit pre-release decision calls for it.

### Windows installer validation

For a release that publishes the installed Windows application, manually dispatch `.github/workflows/windows-installer.yml` on the **same exact candidate revision** and provide the release version when supported by the workflow. The candidate's `bbtool.app.telemetry.TOOLKIT_VERSION`, changelog heading, release-notes filename, source ZIP version, and installer version must agree.

The installer workflow builds the PyInstaller/Inno Setup package, installs it into a clean Windows runner profile, exercises the installed loopback application through the deterministic smoke path, verifies restart/update/uninstall state behavior, and uploads the validated installer workflow artifact.

Before publication, require all of the following to refer to one unchanged full commit SHA:

- successful Release validation workflow;
- successful Windows installer workflow when the installer is part of the release;
- the intended annotated release tag;
- the GitHub Release target commit;
- the downloaded artifacts selected for publication.

A green workflow on a different head is stale evidence and must not be reused.

## Versioning

Update the displayed toolkit version only during release preparation. Add a release entry to `docs/CHANGELOG.md` summarizing user-visible and architectural changes and add/update the version-specific release notes used for the GitHub Release body.

## Build the tracked-file ZIP

The release archive should contain the tracked runtime/source/test files required by the existing release contract, but no local caches, output directories, `.git`, `.sav`, `__pycache__`, or generated mutation/coverage artifacts.

The Release validation workflow builds the archive from tracked files with `git archive`, places it under `dist/` on the runner, verifies it, and uploads it. For an explicit local build, place release archives under `dist/`; `dist/` is ignored by Git.

After creating the archive:

```powershell
python tools\verify_release_zip.py dist\<release>.zip
```

## Release artifacts

For v3.89 and later local-application releases, publish the validated Windows installer as the **primary player artifact**. The verified tracked-file ZIP may be retained as a secondary source/archive artifact.

For v3.89 the intended public filenames are:

```text
BB-Save-Toolkit-3.89-setup.exe
BB-Save-Toolkit-v3.89.zip
```

Use the bytes from the successful exact-candidate workflow artifacts; do not rebuild different bytes after validation merely for publication. Record SHA-256 digests for the public assets in the release handoff/issue summary where practical.

Downloading a workflow artifact does not publish a GitHub Release. Likewise, creating a tag without attaching the validated assets is not completion of a Windows release.

## Tag and publish

After the release-preparation PR is merged and the exact resulting candidate passes every required release gate, create an annotated tag whose target is exactly that validated commit:

```powershell
git tag -a vX.Y.Z -m "Battle Brothers Save Toolkit vX.Y.Z"
```

Then create the GitHub Release targeting that tag, use the version-specific release notes as the release body, and attach the already-validated public assets. Re-fetch the release, tag, target commit, and asset metadata after publication before declaring the lifecycle complete.

Do not move an existing release tag or silently substitute a newer commit after validation. If the candidate changes for any reason, rerun every exact-candidate release gate on the new SHA before tagging or publishing.
