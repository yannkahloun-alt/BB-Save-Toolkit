# Coverage enforcement baseline — v3.84

Reference command:

```powershell
.\run_coverage.ps1
```

The current v3.84 `main` baseline is **89.4% branch-aware total coverage** with
`coverage_slow` excluded. The shared coverage configuration enforces 89.4% as
the minimum, so both local pre-merge validation and GitHub Actions fail on a
regression. Raising this floor should accompany additional committed coverage.

The older measurements below are historical snapshots. They describe the code
at those releases and are not current enforcement thresholds.

---

# Coverage baseline — v3.37

Reference command:

```powershell
.\run_coverage.ps1
```

Fast branch-coverage profile (`coverage_slow` excluded):

- **370 passed**
- **32 deselected**
- **91.9% branch-aware total coverage**
- `save_parser.py`: **84.4%**
- `levelup_advisor.py`: **98.7%**
- `projection/trajectory.py`: **95.4%**
- `app/output.py`: **94.7%**
- `html_report.py`: **93.1%**

The 32 `coverage_slow` tests remain in the normal full suite and are excluded only from the fast coverage profile.

---

# Coverage baseline — v3.36

Reference command:

```powershell
.\run_coverage.ps1
```

Fast branch-coverage profile (`coverage_slow` excluded):

- **346 passed**
- **32 deselected**
- **88.2% branch-aware total coverage**
- `save_parser.py`: **79.7%**
- `html_report.py`: **93.1%**
- `app/config.py`: **100.0%**
- `projection/__init__.py`: **100.0%**

The 32 `coverage_slow` tests remain part of the normal full test suite. They are excluded only from the fast coverage profile because tracing makes the combinatorial projection tests disproportionately expensive.

---

# Branch coverage baseline — v3.29

## Reference commands

Fast correctness suite (all tests):

```powershell
python -m pytest -q
```

Expected v3.29 result: **327 passed**.

Branch-coverage profile:

```powershell
python -m pytest -q -m "not coverage_slow" --cov=bbtool --cov-branch --cov-report=term-missing --cov-report=html:tests/coverage/html --cov-report=json:tests/coverage/coverage.json
```

Equivalent Windows shortcut:

```powershell
.\run_coverage.ps1
```

## v3.29 measured baseline

- Instrumented tests: **295 passed**
- Tests excluded only from coverage tracing: **32 deselected**
- Statements: **2,150**
- Missed statements: **817**
- Branches: **720**
- Partial branches: **92**
- Combined branch-aware coverage: **60.0%**

The percentage shown by coverage.py combines statement and branch execution into one branch-aware score. `--cov-branch` is always enabled for this project.

## Why `coverage_slow` exists

Coverage tracing multiplies the cost of a few combinatorial Advisor / full-projection tests dramatically. Those tests remain part of the normal 327-test correctness suite; they are excluded only from the instrumented coverage profile. This keeps the coverage command usable while remaining conservative: code exercised only by those excluded tests does not receive coverage credit.

## Lowest-covered areas at baseline

The initial measurement deliberately records the current state rather than optimizing the number:

- application orchestration (`app/cli.py`, `app/console.py`, `app/main.py`, `app/runner.py`): near 0% in the coverage profile;
- `levelup_advisor.py`: 7.3% because the expensive end-to-end Advisor tests are excluded under tracing;
- `html_report.py`: 39.9%;
- `save_parser.py`: 58.9%;
- trajectory core: 89.0%;
- scoring/progression/classification core: 93–100%.

Use `tests/coverage/html/index.html` to inspect unexecuted lines and missing branches file by file.


## Machine-readable report

Every coverage run also writes `tests/coverage/coverage.json`, containing the global totals and per-file statement/branch details. This file is intended for automated comparison and sharing for analysis.


## v3.35 baseline

- Functional suite: `345 passed`
- Coverage profile: `313 passed, 32 deselected`
- Branch-aware total coverage: **76.0%**
- Previous v3.34 baseline: **64.0%**
- Major gains: `app/analysis.py` 100.0%, `levelup_advisor.py` 85.4%, `app/console.py` 92.5%, `app/main.py` 100.0%, `app/output.py` 87.9%, `html_report.py` 57.4%.
- Largest remaining coverage debt: `save_parser.py` 58.9% and the top-level `render_html_report()` path.
