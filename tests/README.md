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
.\run_tests.ps1 coverage
```

## Layout

- `unit/`: deterministic unit/business tests.
- `integration/`: cross-module tests.
- `fixtures/`: deterministic local fixtures; no machine-specific paths or network dependencies.
