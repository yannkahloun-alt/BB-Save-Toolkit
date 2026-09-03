# Issue 131 cold Fit performance

## Root cause

The reported real-save run and the synthetic benchmark did not use equivalent
measurement conditions. Normal CLI analysis started `tracemalloc` before
projection, while `tools/benchmark_projection_runtime.py` did not. The Fit
policy is allocation-heavy by design: sampled paths repeatedly form bounded
tuples for memoized lookahead. Tracing every allocation therefore amplified the
cost that the existing `trajectory_s` timer attributed to the engine.

On the issue's public diagnostic bundle, the sanitized representative workload
reproduces both the state shape and the reported near-one-second slow example:

| Two brothers × 11 archetypes | Heap tracing | Analysis | Slowest projection |
| --- | --- | ---: | ---: |
| Before-equivalent diagnostic | enabled | 11.924 s | 1.043 s |
| Normal run after this change | disabled | 2.399 s | 0.166 s |

That is a 4.97× workload speedup and a 6.28× speedup for the slowest projection.
The production change is to make Python heap tracing explicit through
`--measure-python-heap`; normal run metadata reports the heap measurement as
disabled. The option remains useful when memory evidence is worth its measured
runtime cost.

## Complexity evidence

The slowest untraced representative projection was a level-3, four-Fit-stat
role that adaptively refined from 512 to 2,048 samples. It used 20,512 policy
choices, 7,483 distinct memo states, 74,565 memo hits, and spent 0.105 s in
policy evaluation out of 0.145 s of scenario simulation. Context construction
was 0.0002 s. This shows that real policy work is dominated by scenario/policy
evaluation, not effects or context construction, but that the observed 46 s
workload gap was caused by allocation tracing magnifying that work.

The bounded diagnostics stored with each slowest projection now report level,
remaining rounds, Fit-stat count, initial/refined samples, memo hits/misses and
state count, policy calls/evaluations, adaptive-refinement time, and context,
sampling, scenario, and policy time.

## Reproduction

The representative benchmark contains only sanitized numerical brother-state
shapes derived from the public issue attachment. It is deterministic,
network-free, and does not require or embed the save:

```powershell
python tools/benchmark_projection_runtime.py --workload representative
python tools/benchmark_projection_runtime.py --workload representative --measure-python-heap
```

The unchanged synthetic 10×11 command measured 9.315 s after the diagnostic
instrumentation was added, versus 9.768 s immediately before this change on the
same Python 3.12 runtime, so it did not materially regress:

```powershell
python tools/benchmark_projection_runtime.py --brothers 10
```

Projection outputs are unchanged: the optimization changes only whether an
external allocation observer is enabled by default. Sample coverage, adaptive
refinement, choice policy, incremental behavior, and validation semantics remain
unchanged.
