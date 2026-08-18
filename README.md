# Battle Brothers Save Toolkit — Python v3.84

v3.29 adds branch-coverage instrumentation on top of the v3.28 contract-complete test suite. Normal pytest still runs all 327 tests; the dedicated coverage profile excludes only tests marked `coverage_slow`, whose combinatorial projection workloads become pathologically slow under tracing.

The active development model is intentionally small:

- **Expected Fit** — expected level-11 match to an archetype.
- **Likely Fit range** — P5–P95 of simulated level-11 Fit.
- **Full Fit range** — explicit simulated min/max extremes.
- **Fit Feasibility** — `P(Fit >= 100%)`.
- **Level-Up Advisor** — evaluates current 3-pick choices through the same Fit trajectory engine; current rolls are injected as degenerate `X-X` ranges.
- **Strategic Classification** — derives Invest / Use / Fodder / Trash from Fit and its range only.

Removed in v3.9: Development Burden, Patch/Support/Core pick accounting, Current Readiness, role gates, viability `min`/`ready` configuration, the legacy deterministic allocation planner, Gifted special analysis, and the old compatibility projection facade.

## Human-editable archetypes

`config/archetypes.json` describes gameplay intent, not implementation details. A Fit stat uses:

```json
"MAtk": {
  "target": 90,
  "weight": 4.0,
  "baseline": 80
}
```

`target` is Fit 100% for that stat, `weight` is its relative importance, and `baseline` shapes the lower continuous Fit curve. A stat absent from an archetype is not evaluated for Fit.

Perk metadata (`required` / `recommended`) is stored for future use but does not currently alter Fit.

## Projection model

The engine simulates real level-up rounds with at most three selected attributes per round. Stars only affect future roll ranges. The normal pass uses 512 deterministic low-discrepancy trajectories and adaptively refines ambiguous cases to 2048. Known rolls are represented by degenerate ranges such as `4-4`. Blind projection and serialized-save ground truth therefore execute the exact same trajectory code; only their input ranges differ. The same inputs always produce the same outputs.

## Repository layout

- `bb_analyze.py` — CLI entry point.
- `bbtool/` — parser, projection, classification, Advisor and report code.
- `config/` — editable archetypes and classification thresholds.
- `references/` — vanilla reference data.
- `docs/` — architecture, changelog and design notes.

Every run emits the normal analysis JSON, HTML report, and a single `<save>-debug.json` diagnostic bundle.

## Open generated report

To open the generated HTML report automatically in the default browser after a normal analysis run, add:

```powershell
python .\bb_analyze.py <save.sav> --open-report
```

The default remains unchanged: without `--open-report`, the toolkit only writes the report to disk.

## Test dependencies

```powershell
python -m pip install -r .\tests\requirements.txt
```


## Static analysis

Install the development dependencies once:

```powershell
python -m pip install -r .\tests\requirements.txt
```

Run Pyflakes on the application code:

```powershell
.\run_lint.ps1
```

To include the test suite itself:

```powershell
.\run_lint.ps1 -Tests
```

Pyflakes is kept separate from pytest: pytest verifies behavior, coverage measures executed lines/branches, and Pyflakes performs static error analysis without importing application modules.


## Ruff static analysis

Ruff complements Pyflakes with bug-risk, modernization and simplification checks.

```powershell
.\run_ruff.ps1
```

Include tests:

```powershell
.\run_ruff.ps1 -Tests
```

Configuration lives in `tests\ruff.toml`. The first rule set is intentionally conservative: Pyflakes (`F`), selected pycodestyle runtime/layout errors (`E4`, `E7`, `E9`), flake8-bugbear (`B`), pyupgrade (`UP`), flake8-simplify (`SIM`) and stale suppression detection (`RUF100`). Formatting-only churn is intentionally excluded.

\n## Mutation testing\n\nThe first mutation-testing profile uses Cosmic Ray and deliberately targets only `bbtool\\projection\\progression.py`. This keeps the first experiment small and makes the result easy to interpret.\n\nInstall/update development dependencies once:\n\n```powershell\npython -m pip install -r .\\tests\\requirements.txt\n```\n\nRun the mutation session:\n\n```powershell\n.\\run_mutation.ps1\n```\n\nOpen the generated HTML report automatically:\n\n```powershell\n.\\run_mutation.ps1 -OpenReport\n```\n\nRegenerate reports from an existing session without rerunning mutations:\n\n```powershell\n.\\run_mutation.ps1 -ReportOnly -OpenReport\n```\n\nGenerated artifacts are kept under `tests\\mutation\\results\\`. The tracked configuration is `tests\\mutation\\cosmic-ray.toml`. The runner keeps a backup of `progression.py` and restores/verifies it after the run as an additional safety net.\n\n## Branch coverage

Fast correctness run:

```powershell
python -m pytest -q
```

Instrumented branch-coverage run:

```powershell
.\run_coverage.ps1
```

or directly:

```powershell
python -m pytest -q -m "not coverage_slow" --cov=bbtool --cov-branch --cov-report=term-missing --cov-report=html:tests/coverage/html --cov-report=json:tests/coverage/coverage.json
```

The HTML report is written to `tests\coverage\html\index.html` and a machine-readable report to `tests\coverage\coverage.json`. The v3.29 baseline is documented in `docs/COVERAGE_BASELINE.md`.


## Mutation testing profiles

Progression baseline (fast, known 100% mutation score):

```powershell
.\run_mutation.ps1
```

Full `bbtool` campaign:

```powershell
.\run_mutation.ps1 -All
```

Add `-OpenReport` to either command to open its HTML report automatically. Results are kept separately under `tests\mutation\results\progression\` and `tests\mutation\results\all\`.


During mutation execution, the launcher now prints live progress every few seconds:

```text
Progress: 512/9422 (5.43%) | Elapsed 00:08:12 | ETA 02:22:00
```

The ETA is recalculated from the observed average runtime per completed mutant.


If a mutation run is interrupted and leaves its safety backup behind, the next run restores it automatically before doing anything else. Manual recovery is also available:

```powershell
.\run_mutation.ps1 -Restore
```


## Dynamic mutation targets

The mutation launcher no longer has a fixed target list. Any Python module or package under `bbtool` can be selected without a new build.

List targets:

```powershell
.\run_mutation.ps1 -ListTargets
```

Examples:

```powershell
.\run_mutation.ps1 -Target projection -OpenReport
.\run_mutation.ps1 -Target projection/scoring -OpenReport
.\run_mutation.ps1 -Target scoring -OpenReport
.\run_mutation.ps1 -Target app -OpenReport
```

A short module name such as `scoring` works when it is unique. Canonical paths such as `projection/scoring` always work.

By default, arbitrary targets use the full pytest suite with `-x`. You can restrict the test set without rebuilding:

```powershell
.\run_mutation.ps1 -Target projection/scoring -Tests tests/unit/test_scoring.py,tests/unit/test_scoring_contract_full.py -OpenReport
```

`progression` retains its optimized dedicated test suite automatically.


### Cosmic Ray live progress

The live progress reader follows Cosmic Ray 8.7's SQLite schema: `work_items`
contains the complete work queue, while one row is added to `work_results` for
each finished mutation job. The launcher therefore reports:

```text
Progress: completed work_results / total work_items
```

and derives the rolling ETA from that observed completion rate.


### Automatic mutation test selection

When `-Tests` is omitted, the launcher derives relevant pytest files from the
target module names. For `classification.py`, for example, it searches
`test_classification.py`, `test_classification_*.py` under unit and integration
tests. Package targets use the union of matches for all contained modules.
The chosen files are printed before Cosmic Ray starts. If nothing matches, the
launcher explicitly warns before falling back to the full suite.

Live progress also includes the observed execution cost per newly completed
mutation job:

```text
Progress: 42/125 (33.60%) | Test 0.84s/job | Elapsed 00:00:48 | ETA 00:01:35
```


## Mutation test naming convention

When `run_mutation.ps1` is called with `-Target` and no explicit `-Tests`,
the launcher discovers relevant pytest files automatically from the target
module names.

For a module such as:

```text
bbtool/classification.py
```

it searches these patterns:

```text
tests/unit/test_classification.py
tests/unit/test_classification_*.py
tests/unit/test_*classification*.py
tests/integration/test_classification.py
tests/integration/test_classification_*.py
tests/integration/test_*classification*.py
```

For a package target such as:

```text
bbtool/projection
```

the launcher applies the same convention to every Python module contained in
that package and uses the union of all matching tests. It also considers tests
named after the package itself.

Examples:

```text
bbtool/projection/scoring.py
  -> test_scoring.py
  -> test_scoring_*.py
  -> test_*scoring*.py

bbtool/levelup_advisor.py
  -> test_levelup_advisor.py
  -> test_levelup_advisor_*.py
  -> test_*levelup_advisor*.py

bbtool/classification.py
  -> test_classification_contract_full.py
  -> test_planner_classification.py
```

This convention is intentional: a test file is automatically associated when the
production module basename appears anywhere after `test_` in the filename. This
keeps focused names such as `test_classification_contract_full.py` and contextual
names such as `test_planner_classification.py` both discoverable without a manual
mapping. If no
matching tests are found, the launcher prints a warning and falls back to the
full pytest suite. `-Tests` remains available as an explicit override for
cross-module or unusually named test sets.

Paths inserted into generated Cosmic Ray TOML are normalized to forward slashes
(`/`) so the configuration is portable and safe on Windows.



### Equivalent mutation registry

Semantically equivalent mutants are recorded in
`tests/mutation/equivalent_mutants.json`. Cosmic Ray's raw survivor count is
left untouched; the launcher additionally prints an effective mutation summary
that excludes only reviewed equivalent mutants. Do not weaken tests or alter
production behavior merely to force a raw 100% score.


### Classification equivalent-mutant cleanup

`perk_compatibility()` now expresses its final reachable branch as
`total == 1` rather than `total >= 1`. Earlier branches already exclude
all totals >= 2, and totals are integer sums, so this is behaviorally
equivalent while removing the structurally equivalent `>= -> ==` Cosmic Ray
mutation site. Negative totals remain `NEUTRAL`.


### Classification affinity intervals

`perk_compatibility()` now encodes affinity labels as explicit, non-overlapping
integer intervals:

- total < 1: NEUTRAL
- 1 <= total < 2: LOW
- 2 <= total < 5: MEDIUM
- total >= 5: HIGH

This removes the previous equivalent comparison pair (`>= 1` versus `== 1`).
Each boundary now represents an independently observable behavioral contract.


### Mutation console outcome summary

After report generation, the launcher prints KILLED, SURVIVED, INCOMPETENT,
and TOTAL counts. Every INCOMPETENT mutant is also listed by module, operator,
and occurrence directly in the console.

Mutation campaigns force Python UTF-8 mode (`PYTHONUTF8=1`) and UTF-8 standard
streams (`PYTHONIOENCODING=utf-8`). Cosmic Ray 8.7 decodes captured pytest
output as UTF-8; this avoids false INCOMPETENT outcomes on Windows when pytest
would otherwise emit legacy code-page bytes.


### Scoring first-point contract

`curve_value()` now names the first point explicitly (`first_x`, `first_y`) and
handles all values `<= first_x` in one early-return branch. This removes the
previous equivalent `<`/`<=` mutation site and makes the first-point contract
directly testable.

Regression tests use deliberately different first-point X/Y values so index
mutations cannot survive by coincidence.


### Mutation hardening: contract first

The scoring implementation remains the simpler v3.60 version. Mutation
hardening now focuses on observable contracts that a future developer could
accidentally break: endpoint clamping, exact knots, interpolation, monotonicity
for monotone curves, empty/single-point behavior, input immutability, weighted
averaging, non-fit skipping, zero-weight behavior, and lower-bound score
clamping.

The first-boundary `<=` -> `<` mutant is retained as a reviewed equivalent:
at the only differing input (`value == first_x`), both implementations return
the exact same `first_y`.


### Scoring lower-bound clamp

`curve_value()` now clamps the input value to the first curve abscissa before
interpolation instead of using a dedicated `value <= first_x` early return.

This preserves the public contract exactly:
- values below the first point return the first Y value;
- the exact first X returns the first Y value;
- later values are linearly interpolated or upper-clamped as before.

The change removes the redundant first-boundary comparison that produced the
reviewed equivalent `<` / `<=` mutant, while making the lower-clamp intent more
explicit for future maintainers.


### Perks mutation hardening

`projection/perks.py` is hardened against the first 211-job Cosmic Ray audit.
The initial run exposed 71 survivors plus one Cosmic Ray `ExceptionReplacer`
incompetent. Tests now lock operator dispatch, unknown-operator rejection,
negative/zero division, multiplier-property finalization, structural effect
filters, continue-vs-break behavior, file/JSON error contracts, explicit
effect-map behavior, and profile multiplier defaults. Postponed `| None` type
annotations were converted to `Optional[...]` so mutation testing targets runtime
behavior rather than inert annotation syntax.
