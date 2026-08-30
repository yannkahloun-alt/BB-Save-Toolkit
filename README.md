# Battle Brothers Save Toolkit

Read-only Battle Brothers save analyzer focused on level-11 archetype Fit, probabilistic development trajectories, strategic classification, Level-Up Advisor recommendations, and incremental reuse of unchanged analysis artifacts.

## Development model

**Git is the source of truth.** Numbered ZIP handoffs are no longer the development workflow; ZIPs are produced only for explicit releases.

Start with:

- `AGENTS.md` — instructions for Codex/other coding agents;
- `docs/INVARIANTS.md` — contracts that must not regress;
- `docs/ARCHITECTURE.md` — current architecture;
- `docs/DEVELOPMENT_WORKFLOW.md` — branch/worktree workflow;
- `docs/TESTING.md` — required quality gates;
- `docs/specs/REMAINING_WORK_v3.84.md` — current open roadmap.

## Run the analyzer

```powershell
python .\bb_analyze.py "C:\path\to\quicksave.sav"
```

Open the generated report automatically:

```powershell
python .\bb_analyze.py "C:\path\to\quicksave.sav" --open-report
```

Reports consume the six public JSON files stored beside them. Because browsers
do not reliably allow adjacent JSON reads from `file://`, opening is handled by
a loopback-only local server. To reopen an extracted or moved report later:

```powershell
python .\bb_analyze.py --serve-report ".\output\my-report-folder" --open-report
```

The server binds only to `127.0.0.1`, requires no network connection, and runs
until stopped with Ctrl+C. Opening an HTML file directly shows the equivalent
launch instruction instead of a blank or partially populated report.

At completion, the console lists the generated report and data files with
their sizes, the projection-validation result and artifact path, the final ZIP
size and SHA-256 checksum, and whether report opening was requested, attempted,
and successful.

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

Maintainers can also publish the approved JSON scenarios as browser-accessible
render-only previews; see [docs/WEB_PREVIEWS.md](docs/WEB_PREVIEWS.md).

This mode validates the complete dataset before creating output, then writes
the canonical public JSON contract, generates the same data-free HTML shell
and assets as a normal run, and archives the portable result. It does not read
a save, prepare game references, or run
projection, classification, cache, or Level-Up Advisor logic. Add
`--open-report` to open the result. See `docs/REPORT_DATASET.md` for the input
contract and compatibility policy.

## Development setup

```powershell
python -m pip install -r tests\requirements.txt
```

Routine development uses targeted tests plus static analysis. The local
pre-merge gates are:

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
```

Pull requests targeting `main` run those same three gates in GitHub Actions.
Branch protection should require the checks `tests`, `ruff`, and `pyflakes`;
see `docs/GITHUB_BRANCH_PROTECTION.md`. Coverage remains available as an
explicit local validation and pre-release gate while its runtime is optimized.

Pre-release validation additionally runs the complete suite (including
`coverage_slow`) and targeted mutation testing:

```powershell
.\run_tests.ps1
.\run_mutation.ps1 -Target <changed-or-high-risk-module>
```

See `docs/TESTING.md` and `docs/MUTATION_TESTING.md` for policy.

## Repository layout

```text
bbtool/          parser, analysis, projection, incremental cache, report code
config/          human-editable archetypes/classification/perk model
references/      tracked reference seeds + vanilla reference generators
tests/           unit/integration tests and mutation helpers
docs/            architecture, invariants, workflow, specs, changelog
tools/           release/static tooling
```

## Releases

Version numbers are release markers, not commit counters. Follow `docs/RELEASE.md` when producing a gameplay ZIP.
