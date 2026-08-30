# Testing and Quality Gates

## Install development dependencies

```powershell
python -m pip install -r tests\requirements.txt
```

## Routine development / task iteration

Run targeted tests for changed behavior and affected modules, followed by lint
and Ruff. Routine iteration excludes both `coverage_slow` and mutation testing.

Examples:

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest tests/unit/test_incremental_core.py -q
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -k advisor -q
.\run_tests.ps1 parser
```

Changed behavior must still have explicit regression coverage. This policy
changes when expensive gates run; it does not weaken correctness requirements.

## Pre-merge to main

Before merging to `main`, run the full normal suite excluding
`coverage_slow`, lint, and Ruff:

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
```

Pull requests targeting `main` run the same three gates in GitHub Actions as
the stable checks `tests`, `ruff`, and `pyflakes`.

Branch coverage is temporarily excluded from normal PR CI and the routine
pre-merge gate because its runtime is too high. The coverage tooling and
baseline remain intact for explicit local validation and pre-release work. This
temporary exception must be revisited when a safe optimization is selected.

Agent A additionally launches and waits for an independent Agent B Codex task
that reviews the exact current PR head SHA. This operational review does not
replace any of the three deterministic GitHub checks and is not itself a required
status check in the free single-account design. See `docs/AGENT_B_REVIEW.md`.

## Pre-release / pre-production

Before a release or production handoff, additionally run:

```powershell
.\run_tests.ps1
.\run_mutation.ps1 -Target <changed-or-high-risk-module>
```

`run_tests.ps1` includes `coverage_slow`, but the manually dispatched GitHub
**Release validation** workflow excludes that marker by default. It runs the
remaining reproducible tests, coverage, lint, and Ruff gates, then builds and
verifies the release ZIP and retains it as a downloadable artifact. Its stable
job results and run summary bind the outcome to the selected ref and exact
commit SHA. Real-save smoke tests remain local because private game data and
game files are not available in CI.

Neither `coverage_slow` nor mutation testing is invoked or required by that
workflow. Both remain separate, explicitly requested pre-release work. Mutation
campaigns target changed or high-risk areas; broader campaigns such as
`-Target all` run only when explicitly requested.

The reproducible slow-test performance baseline and its current optimization
contract are documented in `docs/SLOW_TEST_PERFORMANCE.md`.

## Static analysis

```powershell
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
```

Both must pass for changed Python code unless a documented repository-wide pre-existing failure exists. Do not introduce new warnings.

## Branch coverage

For parser, projection, scoring, classification, advisor, incremental, trait/permanent-injury, and other correctness-critical changes:

```powershell
.\run_coverage.ps1
```

Coverage excludes `coverage_slow` because tracing makes those combinatorial
tests too expensive. The shared configuration enforces the documented 89.4%
branch-aware v3.84 baseline whenever coverage is explicitly run.

Coverage percentage alone is not the goal. New branches affecting correctness need explicit assertions.

## Incremental cache verification

When modifying cache fingerprints, dependencies, identity, engine versions, projection semantics, classification, or advisor behavior, exercise:

```powershell
python .\bb_analyze.py <save.sav> --verify-cache --cache-debug
```

The invariant is:

```text
incremental == independent full recomputation
```

## Mutation testing (pre-release / pre-production only)

Mutation testing is not a per-task Definition of Done and must not be started
automatically during routine implementation or normal pre-merge validation.

List available targets, dependency counts, mutant counts, and qualitative cost:

```powershell
.\run_mutation.ps1 -ListTargets
```

Run the touched module:

```powershell
.\run_mutation.ps1 -Target projection/scoring
.\run_mutation.ps1 -Target incremental/cache
```

Mutation policy:

- fix every survivor in touched correctness logic or add the missing test that kills it;
- do not cherry-pick only "interesting" survivors;
- module/file-oriented campaigns are required for normal pre-release checks;
- `-Target all` is an orchestrator for an explicitly requested broad campaign.

## Release archive test

A release ZIP must pass:

```powershell
python tools\verify_release_zip.py <release.zip>
```

## Definition of done for a bug fix

A bug fix is done when:

1. the bug is reproduced by a test/fixture;
2. the implementation is corrected;
3. focused tests pass;
4. the applicable routine or pre-merge suite passes;
5. static analysis passes;
6. relevant tests are exercised, with branch coverage run when explicitly
   requested or required for pre-release work;
7. docs/specs are updated if the contract changed.

`coverage_slow` and targeted mutation testing are additional
pre-release/pre-production gates, not per-task completion requirements.
