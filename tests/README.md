# Test suite

The same pytest suite is used locally and by the assistant.

## Fast correctness run

From the toolkit root:

```powershell
python -m pytest -q
```

Or on Windows:

```powershell
.\run_tests.ps1
```

This always runs the complete suite, including `coverage_slow` tests.

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
python -m pytest -q -m "not coverage_slow" --cov=bbtool --cov-branch --cov-report=term-missing --cov-report=html
```

The terminal shows the branch-aware coverage percentage and missing lines. The navigable HTML report is generated at `htmlcov\index.html`.

`coverage_slow` tests are excluded only from instrumentation because tracing makes their combinatorial projection workloads extremely slow. They remain mandatory in the normal correctness suite.

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
