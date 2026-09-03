# Issue 70 projection performance

## Reproducible benchmark

Run the deterministic, network-free cold workload with:

```powershell
python tools/benchmark_projection_runtime.py --brothers 10
```

It uses the tracked 11-archetype configuration, ten distinct level-1 synthetic
brothers, no incremental manifest, and valid deterministic serialized rolls for
the separate projection-validation replay. It reports analysis, Fit trajectory,
validation, and total wall time along with projection and trajectory-cache calls.

## 2026-09-02 results

Python 3.12 on Windows, same machine and configuration for both measurements:

| Measurement | Before | After |
| --- | ---: | ---: |
| One brother × 11 archetypes, cold Fit matrix | 9.424 s | 1.417 s |
| Speedup | — | 6.65× |

The after-change representative ten-brother run measured:

| Measurement | Result |
| --- | ---: |
| Analysis / Strategic Classification | 9.614 s |
| Fit trajectories | 9.593 s |
| Projection validation | 0.093 s |
| Validation trajectory compute | 0.062 s |
| End-to-end analysis + validation | 9.707 s |
| Analysis projection calls | 110 |
| Seeded validation comparisons | 110 |
| Validation trajectory cache hits / misses | 137 / 110 |

The optimization preserves the exhaustive bounded drop-composition search but
uses fixed-arity arithmetic for the dominant four- and five-stat reductions.
Seeded validation remains an independent replay through the shared trajectory
engine. It now reuses the already-built blind choice-policy memoization when all
serialized rolls are within their vanilla ranges; malformed rolls deliberately
use a separate expanded policy so validation can still report them safely.
