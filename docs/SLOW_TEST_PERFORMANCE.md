# Slow-test performance baseline

## Scope and command

Measured on Windows 11, Python 3.12, from a local SSD, with the same interpreter
and pytest options for every run:

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest `
  --basetemp=tests/cache/slow-tmp -m coverage_slow -q --durations=10
```

The temporary directory name was unique per run. No network access was used.
The measurements cover all 30 tests selected by `coverage_slow`.

## Results

| Profile | Run 1 | Run 2 | Run 3 | Median |
| --- | ---: | ---: | ---: | ---: |
| Before optimization | 885.10 s | 919.08 s | 900.59 s | 900.59 s |
| After optimization | 4.02 s | 3.73 s | 3.54 s | 3.73 s |

The median decreased by 99.6%. The slowest optimized run is 7.8% above the
optimized median, within the ticket's 20% variability limit.

The initial profile also exposed a stale golden assertion: it expected the old
v3.15 positive-only Fit values even though the repository contract now uses
bounded signed Fit. That assertion was updated to the current documented
semantics; the independent optimized-versus-generic trajectory tests remain in
place.

## Initial cost concentration

The five dominant calls in the median-scale initial runs accounted for more
than 99% of elapsed time:

| Test intent | Representative duration | Cause |
| --- | ---: | --- |
| Advisor ignores hidden future rolls | 430 s | Two level-2, all-role projection sets before comparing one invariant |
| HTML strategic/brother contracts | 363 s | Level-2 full analysis although only rendered structure is asserted |
| Advisor early guards | 57 s | Full role rows built before checking missing rolls or points |
| Advisor incomplete-roll guard | 23 s | Full role rows built before an early return |
| Fast/full payload equivalence | 23 s | Ten development rounds for every role although payload equivalence is level-independent |

## Optimization contract

The tests now use the smallest state that proves each existing assertion:

- early-return tests pass no unused role rows;
- hidden-future isolation uses one role and one remaining development round;
- presentation-only rendering and fast/full payload comparison use level 11;
- every original semantic assertion remains, including all-role fast/full
  payload comparison and deterministic 512-sample trajectory golden values.

No production projection, Fit, classification, Advisor, cache, or report logic
was changed. The `run_tests.ps1 slow` selector now includes both `slow` and
`coverage_slow`, making the focused pre-release profile directly runnable.

