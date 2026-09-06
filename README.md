# Battle Brothers Save Toolkit

Read-only Battle Brothers save analyzer focused on level-11 archetype Fit, probabilistic development trajectories, strategic classification, Level-Up Advisor recommendations, recruitment/company planning, and conservative reuse of unchanged analysis artifacts.

## Windows application

For normal Windows use, install the current release from GitHub Releases. The v3.89 player download is:

```text
BB-Save-Toolkit-3.89-setup.exe
```

The application supports Windows 10/11 x64, installs per-user, serves its UI only on `127.0.0.1`, and keeps durable user state outside the installation directory. The primary workspaces are **Company**, **Level Up**, and **Recruitment**, with Brother drill-down and persistent Assigned Build intent.

On a first run with no saved selection, the application resolves the current Windows user's real Documents known folder and defaults to:

```text
<Windows Documents>\Battle Brothers\savegames\quicksave.sav
```

Windows folder redirection such as OneDrive-backed Documents is respected. A missing quicksave is reported as unavailable rather than triggering a directory scan or unrelated fallback. Any explicit save selected later remains authoritative across restarts.

The initial Windows installer may be unsigned because the repository has no approved Authenticode certificate; Windows may therefore show its normal publisher/reputation warning for the download. See [`docs/WINDOWS_DELIVERY.md`](docs/WINDOWS_DELIVERY.md) for lifecycle, update, repair, state-retention, and uninstall behavior.

## Development model

**Git is the source of truth.** Numbered ZIP handoffs are no longer the development workflow; ZIPs are produced only for explicit releases.

Start with:

- `AGENTS.md` — concise project adapter for the pinned shared agent workflow;
- `docs/AGENT_WORKFLOW_DEPENDENCY.md` — workflow version, policy boundary, and update procedure;
- `docs/INVARIANTS.md` — contracts that must not regress;
- `docs/ARCHITECTURE.md` — current architecture;
- `docs/DEVELOPMENT_WORKFLOW.md` — project-specific development and merge policy;
- `docs/TESTING.md` — required quality gates;
- `docs/target-ui/README.md` — validated Target UI product contract and repository-local implementation references;
- `docs/CURRENT_WORK.md` — compact orientation snapshot; live GitHub remains authoritative;
- `docs/specs/REMAINING_WORK_v3.84.md` — historical v3.84 remaining-work baseline, not the current backlog.

## Source / CLI usage

Analyze one save directly:

```powershell
python .\bb_analyze.py "C:\path\to\quicksave.sav"
```

Open the generated report automatically:

```powershell
python .\bb_analyze.py "C:\path\to\quicksave.sav" --open-report
```

Reports consume the seven public JSON files stored beside them. Because browsers do not reliably allow adjacent JSON reads from `file://`, opening is handled by a loopback-only local server. To reopen an extracted or moved report later:

```powershell
python .\bb_analyze.py --serve-report ".\output\my-report-folder" --open-report
```

The server binds only to `127.0.0.1`, requires no network connection, and runs until stopped with Ctrl+C. Opening an HTML file directly shows the equivalent launch instruction instead of a blank or partially populated report.

At completion, the console lists the generated report and data files with their sizes, the projection-validation result and artifact path, the final ZIP size and SHA-256 checksum, and whether report opening was requested, attempted, and successful.

Incremental diagnostics / safety controls:

```powershell
python .\bb_analyze.py <save.sav> --cache-debug
python .\bb_analyze.py <save.sav> --verify-cache --cache-debug
python .\bb_analyze.py <save.sav> --full-recompute
```

Generate only the HTML report from an existing versioned public JSON dataset:

```powershell
python .\bb_analyze.py --render-only .\tests\fixtures\reference_analysis --out .\output
```

Run the interactive loopback application from source:

```powershell
python .\bb_analyze.py --serve-app --open-report
```

The application binds only `127.0.0.1`; its API and security contract are in [`docs/LOCAL_APPLICATION_API.md`](docs/LOCAL_APPLICATION_API.md). It is the only browser surface that may perform validated durable-state mutations. Generated and served reports remain read-only.

Maintainers can also publish approved JSON scenarios as browser-accessible render-only previews; see [docs/WEB_PREVIEWS.md](docs/WEB_PREVIEWS.md). Manual approved-save full-application previews are documented in the same guide.

Render-only mode validates the complete dataset before creating output, then writes the canonical public JSON contract, generates the same data-free HTML shell and assets as a normal run, and archives the portable result. It does not read a save, prepare game references, or run projection, classification, cache, or Level-Up Advisor logic. Add `--open-report` to open the result. See `docs/REPORT_DATASET.md` for the input contract and compatibility policy.

## Development setup

```powershell
python -m pip install -r tests\requirements.txt
```

For routine autonomous tickets, GitHub PR CI owns the normal deterministic suite and static analysis on the exact pull-request head. Its stable checks are `tests`, `ruff`, and `pyflakes`; agents do not normally duplicate them locally. The commands below are manual/reference tooling for explicit local diagnosis or validation CI cannot perform:

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
```

Pull requests targeting `main` run those three gates in GitHub Actions. They are operational merge guards verified against the exact current PR head; GitHub-hosted branch protection/rulesets are intentionally not configured for this repository. See `docs/GITHUB_BRANCH_PROTECTION.md`.

Release validation is a separate explicit workflow. It runs the reproducible suite excluding `coverage_slow`, branch coverage, Pyflakes, Ruff, and verified tracked-file release-ZIP packaging against one exact candidate revision. `coverage_slow` and mutation testing remain separate explicitly requested pre-release/pre-production work; they are not started automatically by normal PR or release validation.

See `docs/TESTING.md`, `docs/RELEASE.md`, and `docs/MUTATION_TESTING.md` for policy.

## Repository layout

```text
bbtool/          parser, analysis, projection, incremental cache, report/local-app code
config/          human-editable archetypes/classification/perk model
references/      tracked reference seeds + vanilla reference generators
tests/           unit/integration/UI tests and mutation helpers
docs/            architecture, invariants, workflow, specs, changelog
tools/           release, packaging, preview, and validation tooling
packaging/       Windows packaging definitions
```

## Releases

Version numbers are release markers, not commit counters. Release publication follows `docs/RELEASE.md`. Starting with v3.89, the Windows installer is the primary player artifact and the verified tracked-file ZIP is the secondary source/archive artifact.
