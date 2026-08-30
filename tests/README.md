# Test suite

The same pytest suite is used locally and by the assistant.

## Pre-merge correctness run

From the toolkit root:

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
```

This is the functional-test gate used for pull requests into `main`. Routine
development may run narrower targeted tests. The complete suite is reserved for
pre-release/pre-production validation:

```powershell
.\run_tests.ps1
```

That command includes `coverage_slow` tests.

## Branch coverage

Install development dependencies once:

```powershell
python -m pip install -r tests\requirements.txt
```

Then run:

```powershell
.\run_coverage.ps1
```

Equivalent direct command:

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -q -m "not coverage_slow" --cov=bbtool --cov-branch --cov-report=term-missing --cov-report=html:tests/coverage/html --cov-report=json:tests/coverage/coverage.json
```

The terminal shows the branch-aware coverage percentage and missing lines. The
shared configuration enforces the current baseline. The navigable HTML report
is generated at `tests\coverage\html\index.html`.

`coverage_slow` tests are excluded from pre-merge and instrumented coverage
because tracing makes their combinatorial projection workloads extremely slow.
They remain mandatory at the pre-release/pre-production tier.

## Selectors

```powershell
.\run_tests.ps1 unit
.\run_tests.ps1 integration
.\run_tests.ps1 advisor
.\run_tests.ps1 slow
.\run_tests.ps1 coverage
```

The `slow` selector runs both tests explicitly marked `slow` and the
combinatorial `coverage_slow` correctness tests. It is intended for focused
pre-release performance validation; the normal PR gate still excludes
`coverage_slow`.

## Layout

- `unit/`: deterministic unit/business tests.
- `integration/`: cross-module tests.
- `fixtures/`: deterministic local fixtures; no machine-specific paths or network dependencies.

## Reference analysis JSON

`fixtures/reference_analysis/` is a maintained, versioned set of public analysis
JSON for report demonstrations and contract tests. It is synthetic: no private
save is stored or required. `manifest.json` declares the fixture schema, the
role of every file, and its SHA-256 digest. The set contains the four normal
public analysis artifacts plus snapshots of the two configurations needed to
interpret them. Debug, incremental-manifest, projection-validation, hidden
`FutureRolls`, timestamps, and machine-specific paths are deliberately excluded.
The committed JSON total is about 147 KiB: small enough for routine diffs and
tests while retaining every configured archetype for realistic report coverage.

Regenerate it offline from the repository root:

```powershell
python tests\fixtures\reference_analysis\generate.py
```

The source records are declared in `generate.py`; the current repository
configuration and analysis engines produce the outputs. Run the command twice
and verify a clean `git diff` to confirm determinism. The integration test
validates JSON syntax, fixture/schema compatibility, hashes, brother/role
relations, representative roster and recruit states, and forbidden data.

Regenerate and review the fixture whenever a public artifact field or format,
archetype/classification configuration, or covered analytical result changes.
Update the JSON and this documentation together when the fixture contract
changes. A digest change is expected only when its reviewed source or behavior
changes; do not normalize away meaningful analytical differences.
